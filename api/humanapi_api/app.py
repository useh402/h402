"""HTTP surface of the task API."""

from __future__ import annotations

import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from . import __version__, ledger
from . import admin as admin_mod
from . import auth as auth_mod
from . import workers as workers_mod
from .config import EXPLORER_TX, Settings
from .db import Database
from .geo import maps_url, place_of
from .jobs import Jobs
from .models import (
    Buyer,
    Dispute,
    GoldTask,
    IdempotencyKey,
    Payment,
    Payout,
    Report,
    Task,
    Webhook,
    Worker,
    new_id,
)
from .pricing import parse_task, pricing_table
from .qualification import EXPLAIN, results_for, samples_for, score
from .quality import seed_gold
from .tasks import (
    PICTURE_PROOFS,
    ApiError,
    create_tasks,
    find_quote,
    get_or_create_buyer,
    make_quote,
    parse_batch,
    receipt_view,
    record_payment,
    task_view,
)
from .webhooks import new_secret
from .x402 import (
    FacilitatorClient,
    b64json,
    canonical_hash,
    decode_b64json,
    match_accept,
    payment_required,
    requirements_for,
)

logger = logging.getLogger("humanapi.api")


def create_app(settings: Settings | None = None, facilitator_transport: httpx.BaseTransport | None = None, jobs_http: httpx.Client | None = None, senders: dict | None = None, chain=None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    db = Database(settings.database_url)
    db.create_all()
    facilitator = FacilitatorClient(settings, transport=facilitator_transport)
    if senders is None and settings.payouts_enabled:
        from .payout_chain import build_senders

        senders = build_senders(settings)
    jobs = Jobs(settings, db, http=jobs_http, senders=senders)
    if chain is None and settings.escrow_contract:
        from .escrow_chain import build as build_chain

        chain = build_chain(settings)
    jobs.chain = chain
    if settings.house_payout == "wallet" and settings.escrow_operator_private_key and settings.robinhood_enabled:
        from .payout_chain import EvmSender, _default_rpc

        rail = next(r for r in settings.rails() if r["name"] == "robinhood")
        jobs.reward_sender = EvmSender(rail["rpc_url"] or _default_rpc(rail["network"]), settings.escrow_operator_private_key, rail["asset"])
    from .storage import build as build_store

    store = build_store(settings.redis_url)
    jobs.store = store

    with db.session() as s0:
        seed_gold(s0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if jobs.senders:
            try:
                logger.info("payout recovery resolved %d rows", jobs.recover_payouts())
            except Exception as e:
                logger.error("payout recovery failed: %s", str(e)[:300])
        if settings.jobs_enabled:
            jobs.start()
        yield
        jobs.shutdown()

    app = FastAPI(title="H402", version=__version__, lifespan=lifespan)
    from .pricing import TASK_TYPES as _task_types

    _task_types["do"]["accept_window"] = settings.do_accept_window_seconds  # the written-proof fallback window is a setting
    from .tasks import OPERATOR_DECIDES_ALL

    OPERATOR_DECIDES_ALL["on"] = bool(settings.operator_decides_all)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()], allow_methods=["*"], allow_headers=["*"])
    app.state.db, app.state.jobs, app.state.facilitator, app.state.settings = db, jobs, facilitator, settings
    base = settings.public_base_url.rstrip("/")

    def err(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": code, "message": message}, headers=headers or {})

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return err(e.status, e.code, e.message)

    @app.get("/")
    def root():
        return {"service": "humanapi", "version": __version__, "docs": "/docs", "pricing": "/v1/pricing"}

    @app.get("/v1/catalogue")
    def catalogue():
        from .catalogue import catalogue_view

        return {"categories": catalogue_view()}

    @app.get("/v1/catalogue/templates")
    def catalogue_templates(category: str | None = None):
        """Seed problems kept as templates. A template is never a live task until a client funds a concrete case."""
        from .templates import templates_view

        return {"templates": templates_view(category), "note": "templates, not live tasks"}

    @app.get("/v1/pricing")
    def pricing():
        table = pricing_table(settings.platform_fee_bps)
        table["minReward"] = settings.min_reward
        for spec in table["types"].values():
            spec["basePricePerWorker"] = max(spec["basePricePerWorker"], settings.min_reward)
        table["rails"] = [{"network": r["network"], "asset": r["asset"], "payTo": r["pay_to"]} for r in settings.rails()]
        with db.session() as s:
            table["availability"] = workers_mod.online_counts(s, settings)
        return table

    # -- paying for tasks ------------------------------------------------------------------------

    def _quote_and_requirements(session, kind: str, body: dict, reqs: list, url: str):
        quote = make_quote(session, settings, kind, body, reqs)
        accepts = requirements_for(settings, facilitator, quote.total, url)
        return quote, accepts

    def _402(quote, accepts, url: str, description: str, error: str = "Payment required", extra_headers: dict | None = None) -> JSONResponse:
        pr = payment_required(accepts, url, description, error)
        body = {
            "error": "payment_required",
            "message": error,
            "quote": {"id": quote.id, "total": quote.total, "workerPool": quote.worker_pool, "fee": quote.fee, "expiresAt": int(quote.expires_at)},
            "x402": pr,
        }
        headers = {"PAYMENT-REQUIRED": b64json(pr), "Cache-Control": "no-store"}
        headers.update(extra_headers or {})
        return JSONResponse(status_code=402, content=body, headers=headers)

    def _idempotent(request: Request, body: dict):
        key = request.headers.get("idempotency-key")
        if not key:
            return None, None
        key = key[:120]
        h = canonical_hash(body)
        with db.session() as s:
            row = s.get(IdempotencyKey, key)
            if row is None:
                return key, None
            if row.body_hash != h:
                raise ApiError(422, "idempotency_key_reused", "this Idempotency-Key was used with a different body")
            return key, JSONResponse(status_code=row.status, content=row.response, headers=dict(row.headers))

    def _remember(key: str | None, body: dict, response: JSONResponse) -> None:
        if not key:
            return
        import json

        with db.session() as s:
            if s.get(IdempotencyKey, key) is None:
                s.add(IdempotencyKey(key=key, body_hash=canonical_hash(body), status=response.status_code, response=json.loads(response.body), headers={k: v for k, v in response.headers.items() if k.upper().startswith("PAYMENT")}))

    async def _paid_flow(request: Request, kind: str) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return err(400, "invalid_request", "body must be JSON")
        if not isinstance(body, dict):
            return err(400, "invalid_request", "body must be a JSON object")
        if kind == "task":
            try:
                reqs = [parse_task(body)]
            except ValueError as e:
                return err(400, "invalid_request", str(e))
        else:
            reqs = parse_batch(body, settings.batch_max)
        # The minimum reward: raise the default, refuse an explicit lower price.
        items = [body] if kind == "task" else body.get("tasks", [])
        for i, r in enumerate(reqs):
            if (r.pricePerWorker or 0) < settings.min_reward:
                if isinstance(items[i], dict) and items[i].get("pricePerWorker") is not None:
                    return err(400, "invalid_request", f"pricePerWorker must be at least {settings.min_reward} ({settings.min_reward / 1e6:.2f})")
                reqs[i] = r.model_copy(update={"pricePerWorker": settings.min_reward})
        key, cached = _idempotent(request, body)
        if cached is not None:
            return cached
        url = f"{base}/v1/tasks" + ("/batch" if kind == "batch" else "")
        description = f"H402 {kind}: {', '.join(r.type for r in reqs[:5])}{'...' if len(reqs) > 5 else ''}"
        header = request.headers.get("payment-signature") or request.headers.get("x-payment")

        with db.session() as s:
            quote, accepts = _quote_and_requirements(s, kind, body, reqs, url)
            quote_total = quote.total
        if not header:
            return _402(quote, accepts, url, description)
        try:
            payload = decode_b64json(header)
        except Exception:
            return _402(quote, accepts, url, description, "PAYMENT-SIGNATURE header could not be decoded")
        req = match_accept(payload, accepts)
        if req is None:
            return _402(quote, accepts, url, description, "the accepted payment requirement was not offered for this request")
        rail = next(r for r in settings.rails() if r["network"] == req["network"])

        verify = facilitator.verify(payload, req)
        if not verify.get("isValid"):
            reason = verify.get("invalidReason", "invalid_payment")
            return _402(quote, accepts, url, description, f"payment rejected: {reason}")
        settle = facilitator.settle(payload, req)
        settle_header = {"PAYMENT-RESPONSE": b64json(settle)}
        if not settle.get("success"):
            reason = settle.get("errorReason", "settlement_failed")
            status = 402
            return _402(quote, accepts, url, description, f"settlement failed: {reason}", settle_header) if status == 402 else err(500, reason, "settlement failed")

        with db.session() as s:
            existing = s.scalars(select(Payment).where(Payment.network == req["network"], Payment.transaction == settle["transaction"])).first()
            if existing:
                tasks = s.scalars(select(Task).where(Task.payment_id == existing.id)).all()
                views = [task_view(s, t, base) for t in tasks]
                content: dict[str, Any] = {"tasks": views, "batchId": tasks[0].batch_id, "payment": views[0]["payment"]} if kind == "batch" else views[0]
                return JSONResponse(status_code=200, content=content, headers=settle_header)
            live = find_quote(s, body, int(req["amount"])) or s.get(type(quote), quote.id)
            payment = record_payment(s, rail["name"], req, settle, live)
            buyer = get_or_create_buyer(s, rail["name"], payment.payer)
            default_hook = s.scalars(select(Webhook).where(Webhook.buyer_id == buyer.id, Webhook.active.is_(True))).first()
            batch_id = new_id("batch") if kind == "batch" else None
            tasks = create_tasks(s, settings, reqs, payment, buyer, batch_id, default_hook)
            live.consumed_by = payment.id
            s.flush()
            views = [task_view(s, t, base) for t in tasks]
            for t, v in zip(tasks, views, strict=True):
                if t.webhook_secret and t.webhook_secret.startswith("whsec_"):
                    v["webhookSecret"] = t.webhook_secret
                v["buyerToken"] = t.buyer_token
            if kind == "batch":
                content = {"batchId": batch_id, "tasks": views, "payment": views[0]["payment"], "cost": {"total": quote_total}}
            else:
                content = views[0]
        response = JSONResponse(status_code=202, content=content, headers=settle_header)
        _remember(key, body, response)
        logger.info("paid %s on %s tx=%s tasks=%d amount=%s", kind, req["network"], settle["transaction"], len(tasks), req["amount"])
        return response

    @app.post("/v1/tasks")
    async def create_task(request: Request):
        return await _paid_flow(request, "task")

    @app.post("/v1/tasks/batch")
    async def create_batch(request: Request):
        return await _paid_flow(request, "batch")

    # Public pages poll these three; a short cache keeps them fast when the database is far away.
    _cache: dict[str, tuple[float, object]] = {}

    def cached(key: str, seconds: float, make):
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        value = make()
        _cache[key] = (time.time() + seconds, value)
        return value

    @app.get("/v1/tasks/open")
    def open_board(limit: int = 60, category: str | None = None):
        """Public board: what is open right now, without payloads. Sign in to take one."""
        return cached(f"board:{limit}:{category}", settings.public_cache_seconds, lambda: _open_board(limit, category))

    def _open_board(limit: int, category: str | None):
        from .catalogue import CATEGORIES, category_of
        from .models import Answer

        with db.session() as s:
            rows = s.scalars(select(Task).where(Task.state.in_(("open", "claimed", "submitted")), Task.moderation == "allowed", Task.deadline > time.time()).order_by(Task.created_at.desc()).limit(min(limit, 200))).all()
            board = []
            from sqlalchemy import func as _fn

            answered = dict(s.execute(select(Answer.task_id, _fn.count()).where(Answer.task_id.in_([t.id for t in rows])).group_by(Answer.task_id)).all()) if rows else {}
            # A listed task the pool cannot pay for right now is not shown: nobody should take a task and be told it cannot be funded.
            pool = ledger.balance(s, settings.house_rail, "house")
            for t in rows:
                if t.chain_state == "listed" and t.price_per_worker * t.workers_wanted + t.fee > pool:
                    continue
                cat = category_of(t.payload or {})
                p = t.payload or {}
                image = p.get("image") if isinstance(p.get("image"), str) else None
                board.append({"taskId": t.id, "title": t.title, "type": t.type, "category": cat, "categoryLabel": CATEGORIES[cat]["label"] if cat else None, "location": t.location, "difficulty": t.difficulty, "effortMinutes": t.effort_minutes, "price": t.price_per_worker, "workers": t.workers_wanted, "deadline": int(t.deadline), "postedAt": int(t.created_at), "slotsLeft": max(0, t.workers_wanted - answered.get(t.id, 0)), "image": image, "proof": p.get("proof") if t.type == "do" else None, "requester": t.requester, "place": place_of(t.location, p), "mapsUrl": maps_url(place_of(t.location, p), t.location)})
            if category:
                board = [b for b in board if b["category"] == category]
            total_value = sum(b["price"] * b["slotsLeft"] for b in board)
            return {"tasks": board, "count": len(board), "openValue": total_value}

    @app.get("/v1/tasks/map")
    def tasks_map():
        """Open tasks that have a place: the task's own coordinates, or the centre of its city."""
        return cached("map", settings.public_cache_seconds, _tasks_map)

    def _tasks_map():
        from .catalogue import CATEGORIES, category_of

        with db.session() as s:
            rows = s.scalars(select(Task).where(Task.state.in_(("open", "claimed", "submitted")), Task.moderation == "allowed", Task.deadline > time.time()).order_by(Task.created_at.desc()).limit(300)).all()
            out = []
            for t in rows:
                p = t.payload or {}
                place = place_of(t.location, p)
                if place is None:
                    continue
                cat = category_of(p)
                out.append({"taskId": t.id, "title": t.title, "type": t.type, "categoryLabel": CATEGORIES[cat]["label"] if cat else None, "location": t.location, "price": t.price_per_worker, "requester": t.requester, "deadline": int(t.deadline), "lat": place["lat"], "lng": place["lng"], "exact": place["exact"], "photos": p.get("proof") == "photos", "mapsUrl": maps_url(place, t.location)})
            remote = sum(1 for t in rows if place_of(t.location, t.payload or {}) is None)
            return {"tasks": out, "remote": remote}

    @app.get("/v1/tasks/open/{task_id}")
    def open_task_detail(task_id: str):
        """Public listing page for one task: everything a person needs to decide, before taking it."""
        from .catalogue import CATEGORIES, category_of
        from .models import Answer
        from .pricing import TASK_TYPES as _TT

        with db.session() as s:
            t = s.get(Task, task_id)
            if t is None or t.moderation != "allowed":
                raise ApiError(404, "not_found", "no such task")
            cat = category_of(t.payload or {})
            p = dict(t.payload or {})
            spec = _TT[t.type]
            answered = s.query(Answer).filter_by(task_id=t.id).count()
            return {
                "taskId": t.id, "title": t.title, "type": t.type, "state": t.state, "category": cat, "categoryLabel": CATEGORIES[cat]["label"] if cat else None, "categoryNeed": CATEGORIES[cat]["need"] if cat else None,
                "location": t.location, "difficulty": t.difficulty, "effortMinutes": t.effort_minutes, "price": t.price_per_worker, "workers": t.workers_wanted, "slotsLeft": max(0, t.workers_wanted - answered),
                "deadline": int(t.deadline), "postedAt": int(t.created_at), "timeLimitSeconds": t.time_limit_seconds, "requester": t.requester, "place": place_of(t.location, p), "mapsUrl": maps_url(place_of(t.location, p), t.location), "image": p.get("image") if isinstance(p.get("image"), str) else None,
                "payload": p, "acceptance": t.acceptance or None, "minReputation": t.min_reputation,
                "requirements": {
                    "qualification": t.type,
                    "consensus": spec["rule"],
                    "proof": p.get("proof") if t.type == "do" else None,
                    "paidWhen": "the operator checks your answer and approves it" if settings.operator_decides_all else (("the operator looks at your photos and the text you typed, and approves them" if p.get("proof", "text") in PICTURE_PROOFS else "the client accepts your proof, or automatically after an hour") if spec["rule"] == "proof" else ("your answer is accepted" if spec["rule"] == "single" else "your answer agrees with the other workers")),
                    "holdSeconds": t.time_limit_seconds if spec["rule"] == "proof" else settings.claim_hold_seconds,
                    "location": t.location,
                },
                "open": t.state in ("open", "claimed", "submitted") and t.deadline > time.time() and answered < t.workers_wanted,
            }

    @app.get("/v1/tasks/{task_id}/comments")
    def task_comments(task_id: str, request: Request):
        """Every response to a task, kept as a comment. Shown to everyone once the task is decided;
        before that a signed-in worker sees only their own, so answers stay independent."""
        import hashlib

        from .models import Answer, Payout

        with db.session() as s:
            t = s.get(Task, task_id)
            if t is None:
                raise ApiError(404, "not_found", "no such task")
            me = None
            header = request.headers.get("authorization", "")
            if header.lower().startswith("bearer wks_"):
                try:
                    me = auth_mod.authenticate(s, header[7:])
                except ApiError:
                    me = None
            decided = t.state in ("done", "expired", "disputed")
            rows = s.scalars(select(Answer).where(Answer.task_id == t.id).order_by(Answer.submitted_at)).all()
            out = []
            for a in rows:
                mine = me is not None and a.worker_id == me.id
                if not decided and not mine:
                    continue
                w = s.get(Worker, a.worker_id)
                value = None if t.purged else a.answer.get("value")
                if isinstance(value, dict) and isinstance(value.get("photos"), list):
                    # Photos are for the task's client and the operator, never public. The page shows that they exist.
                    value = {"text": value.get("text"), "photoCount": len(value["photos"]), "photos": value["photos"] if mine else None}
                po = s.query(Payout).filter_by(task_id=t.id, worker_id=a.worker_id, kind="task").first()
                paid_tx = po.batch_ref if (po and po.status == "sent" and (po.batch_ref or "").startswith("0x")) else None
                out.append({
                    "reward": po.amount if po else 0, "rewardPaid": bool(po and po.status == "sent"), "rewardTransaction": paid_tx, "claimable": bool(po and po.status == "claimable"), "canClaim": bool(mine and po and po.status == "claimable"),
                    "rewardExplorer": EXPLORER_TX.get(next((r["network"] for r in settings.rails() if r["name"] == t.rail), ""), "{tx}").format(tx=paid_tx) if paid_tx else None,
                    "team": bool(w and w.team),
                    "id": a.id, "author": "You" if mine else f"Worker {hashlib.sha256(a.worker_id.encode()).hexdigest()[:4]}", "tier": w.tier if w else "new", "mine": mine,
                    "wallet": (w.wallet if (w and decided and a.agrees) else None),  # the wallet that is paid, once the task is decided
                    "response": value, "note": a.note, "confidence": a.answer.get("confidence"), "at": int(a.submitted_at),
                    "seconds": a.seconds, "outcome": "accepted" if a.agrees else ("not accepted" if a.agrees is False else "waiting"),
                })
            return {"taskId": t.id, "state": t.state, "decided": decided, "total": len(rows), "hidden": len(rows) - len(out), "comments": out}

    def _catalogue_list():
        from .house import catalogue as _cat

        return _cat()

    # Who is on the site right now: every open page reports itself every 30 seconds; anyone seen in the last two minutes counts.
    presence: dict[str, float] = {}
    presence_lock = threading.Lock()

    def people_online() -> int:
        cutoff = time.time() - 120
        with presence_lock:
            for k in [k for k, t in presence.items() if t < cutoff]:
                del presence[k]
            return len(presence)

    @app.post("/v1/presence")
    async def report_presence(request: Request):
        body = await request.json()
        pid = str(body.get("id", ""))
        if not (8 <= len(pid) <= 64) or not pid.replace("-", "").isalnum():
            raise ApiError(400, "invalid_request", "id must be 8 to 64 letters or digits")
        with presence_lock:
            if len(presence) < 50_000 or pid in presence:
                presence[pid] = time.time()
        return {"online": people_online()}

    @app.get("/v1/stats")
    def public_stats():
        """Collection-style numbers for the board: what is open, what was paid, who is around."""
        return cached("stats", settings.public_cache_seconds, _public_stats)

    def _public_stats():
        from sqlalchemy import func as _f

        from .models import Payout, Worker

        with db.session() as s:
            open_q = s.query(Task).filter(Task.state.in_(("open", "claimed", "submitted")), Task.moderation == "allowed", Task.deadline > time.time())
            open_tasks = open_q.all()
            open_value = sum(t.price_per_worker * t.workers_wanted for t in open_tasks)
            prices = [t.price_per_worker for t in open_tasks]
            day = time.time() - 86400
            # The team's own test runs are counted on their own line, never in the public totals.
            team_ids = [w.id for w in s.query(Worker).filter(Worker.team.is_(True)).all()]
            real = Payout.worker_id.notin_(team_ids) if team_ids else True
            paid_24h = s.query(_f.coalesce(_f.sum(Payout.amount), 0)).filter(Payout.created_at >= day, real).scalar() or 0
            paid_total = s.query(_f.coalesce(_f.sum(Payout.amount), 0)).filter(real).scalar() or 0
            paid_team = (s.query(_f.coalesce(_f.sum(Payout.amount), 0)).filter(Payout.worker_id.in_(team_ids)).scalar() or 0) if team_ids else 0
            done_24h = s.query(Task).filter(Task.state == "done", Task.completed_at >= day, Task.team_run.is_(False)).count()
            done_total = s.query(Task).filter(Task.state == "done", Task.team_run.is_(False)).count()
            done_team = s.query(Task).filter(Task.state == "done", Task.team_run.is_(True)).count()
            online = s.query(Worker).filter(Worker.last_seen >= time.time() - settings.online_window_seconds, Worker.paused.is_(False), Worker.team.is_(False)).count()
            workers_total = s.query(Worker).filter(Worker.handle.notlike("echo-%"), Worker.team.is_(False)).count()
            return {
                "open": len(open_tasks), "openValue": open_value, "lowestPrice": min(prices) if prices else 0, "highestPrice": max(prices) if prices else 0,
                "paid24h": int(paid_24h), "paidTotal": int(paid_total), "done24h": done_24h, "doneTotal": done_total, "teamRuns": {"done": done_team, "paid": int(paid_team)},
                "workersOnline": online, "online": people_online(), "workersTotal": workers_total, "catalogueSize": len(_catalogue_list()), "feeBps": settings.platform_fee_bps,
            }

    @app.get("/v1/rewards")
    def public_rewards():
        """Everything about the money, in one place: rewards paid, tasks, and what is in the pool right now."""
        return cached("rewards", max(settings.public_cache_seconds, 20.0), _public_rewards)

    def _public_rewards():
        from sqlalchemy import func as _f

        from .models import Payout, Worker

        rail = settings.house_rail
        network = next((r["network"] for r in settings.rails() if r["name"] == rail), "")
        link = EXPLORER_TX.get(network, "{tx}")
        with db.session() as s:
            team_ids = {w.id for w in s.query(Worker).filter(Worker.team.is_(True)).all()}
            sent = s.query(Payout).filter(Payout.status == "sent").order_by(Payout.sent_at.desc()).all()
            paid_total = sum(p.amount for p in sent)
            paid_team = sum(p.amount for p in sent if p.worker_id in team_ids)
            by_state = dict(s.execute(select(Task.state, _f.count()).group_by(Task.state)).all())
            open_rows = s.query(Task).filter(Task.state.in_(("open", "claimed", "submitted")), Task.moderation == "allowed", Task.deadline > time.time()).all()
            titles = {t.id: t.title for t in s.query(Task).filter(Task.id.in_({p.task_id for p in sent[:25] if p.task_id})).all()} if sent else {}
            wallets = {w.id: w.wallet for w in s.query(Worker).filter(Worker.id.in_({p.worker_id for p in sent[:25]})).all()} if sent else {}
            recent = [{"amount": p.amount, "taskId": p.task_id, "title": titles.get(p.task_id or "", "Bonus"), "wallet": wallets.get(p.worker_id, ""), "team": p.worker_id in team_ids, "at": int(p.sent_at or p.created_at), "transaction": p.batch_ref if (p.batch_ref or "").startswith("0x") else None, "explorer": link.format(tx=p.batch_ref) if (p.batch_ref or "").startswith("0x") else None} for p in sent[:25]]
            out = {
                "rewardsPaid": int(paid_total), "rewardsPaidToWorkers": int(paid_total - paid_team), "rewardsPaidTeamRuns": int(paid_team), "payments": len(sent), "peoplePaid": len({p.worker_id for p in sent}),
                "tasks": {"total": sum(by_state.values()), "open": len(open_rows), "completed": by_state.get("done", 0), "expired": by_state.get("expired", 0)},
                "openRewards": sum(t.price_per_worker * t.workers_wanted for t in open_rows), "poolAvailable": ledger.balance(s, rail, "house"), "feesEarned": int(s.scalar(select(_f.coalesce(_f.sum(Task.fee), 0)).where(Task.state == "done")) or 0),
                "feeBps": settings.platform_fee_bps, "asset": "USDG", "network": network, "recent": recent, "contract": None,
            }
            locked_books = sum(t.price_per_worker * t.workers_wanted + t.fee for t in s.query(Task).filter(Task.chain_state == "open").all())
        if jobs.chain is not None:
            try:
                info = jobs.chain.info()
                out["contract"] = {"address": info["contract"], "balance": info["balance"], "locked": info["allocated"], "explorer": link.replace("/tx/{tx}", f"/address/{info['contract']}")}
            except Exception:
                out["contract"] = {"address": settings.escrow_contract, "balance": locked_books, "locked": locked_books, "explorer": link.replace("/tx/{tx}", f"/address/{settings.escrow_contract}")}
        return out

    @app.get("/v1/activity")
    def public_activity(limit: int = 30):
        """Recent completions, anonymised: what was done, for how much, how it was decided."""
        return cached(f"activity:{limit}", settings.public_cache_seconds, lambda: _public_activity(limit))

    def _public_activity(limit: int):
        from .catalogue import CATEGORIES, category_of
        from .models import Payout

        with db.session() as s:
            rows = s.scalars(select(Task).where(Task.state.in_(("done", "expired"))).order_by(Task.completed_at.desc()).limit(min(limit, 100))).all()
            out = []
            from sqlalchemy import func as _fn

            paid_by_task = dict(s.execute(select(Payout.task_id, _fn.sum(Payout.amount)).where(Payout.task_id.in_([t.id for t in rows]), Payout.kind == "task").group_by(Payout.task_id)).all()) if rows else {}
            for t in rows:
                cat = category_of(t.payload or {})
                out.append({"taskId": t.id, "title": t.title, "type": t.type, "categoryLabel": CATEGORIES[cat]["label"] if cat else None, "location": t.location, "price": t.price_per_worker, "workers": t.workers_wanted, "state": t.state, "agreement": t.agreement, "completedAt": int(t.completed_at or 0), "method": (t.verification or {}).get("method"), "teamRun": bool(t.team_run), "requester": t.requester, "settlement": t.chain_close_tx, "settlementExplorer": EXPLORER_TX.get(next((r["network"] for r in settings.rails() if r["name"] == t.rail), ""), "{tx}").format(tx=t.chain_close_tx) if (t.chain_close_tx or "").startswith("0x") else None, "paid": int(paid_by_task.get(t.id, 0))})
            return {"activity": out}

    @app.get("/v1/tasks/{task_id}")
    def get_task(task_id: str):
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            return task_view(s, task, base)

    @app.get("/v1/batches/{batch_id}")
    def get_batch(batch_id: str):
        with db.session() as s:
            tasks = s.scalars(select(Task).where(Task.batch_id == batch_id).order_by(Task.created_at)).all()
            if not tasks:
                raise ApiError(404, "not_found", "no such batch")
            return {"batchId": batch_id, "tasks": [task_view(s, t, base) for t in tasks]}

    @app.get("/v1/receipts/{task_id}")
    def get_receipt(task_id: str):
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            return receipt_view(s, task, base)

    @app.post("/v1/webhooks")
    async def register_webhook(request: Request):
        body = await request.json()
        url, payer, network = body.get("url"), body.get("payer"), body.get("network")
        if not (isinstance(url, str) and url.startswith("https://") or (settings.env != "mainnet" and isinstance(url, str) and url.startswith("http://"))):
            raise ApiError(400, "invalid_request", "url must be https")
        rail = next((r for r in settings.rails() if r["network"] == network), None)
        if rail is None or not isinstance(payer, str):
            raise ApiError(400, "invalid_request", "payer and a supported network are required")
        with db.session() as s:
            buyer = get_or_create_buyer(s, rail["name"], payer)
            for old in s.scalars(select(Webhook).where(Webhook.buyer_id == buyer.id, Webhook.active.is_(True))).all():
                old.active = False
            hook = Webhook(id=new_id("wh"), buyer_id=buyer.id, url=url, secret="whbs_" + new_secret()[6:])
            s.add(hook)
            s.flush()
            return JSONResponse(status_code=201, content={"id": hook.id, "url": url, "secret": hook.secret, "note": "buyer-level webhooks carry state changes only; fetch results with GET /v1/tasks/{id}"})

    @app.get("/health")
    def health():
        out: dict[str, Any] = {"ok": True, "env": settings.env, "version": __version__, "rails": {}}
        try:
            with db.session() as s:
                for rail in settings.rails():
                    inv = ledger.check_invariant(s, rail["name"])
                    entry: dict[str, Any] = {"network": rail["network"], "ledgerEscrow": inv["escrow"], "liabilities": inv["liabilities"], "balanced": inv["balanced"]}
                    try:
                        from .chain import escrow_balance

                        chain = escrow_balance(rail)
                        entry["chainEscrow"] = chain
                        entry["drift"] = None if chain is None else chain - inv["escrow"]
                    except Exception as e:
                        entry["chainEscrow"] = None
                        entry["chainError"] = str(e)[:120]
                    out["rails"][rail["name"]] = entry
                    out["ok"] = out["ok"] and inv["balanced"]
                out["tasks"] = {state: s.query(Task).filter(Task.state == state).count() for state in ("open", "claimed", "submitted", "done", "expired", "cancelled")}
                out["buyers"] = s.query(Buyer).count()
            out["database"] = "ok"
        except Exception as e:
            out["ok"], out["database"] = False, f"error: {str(e)[:120]}"
        try:
            facilitator.supported()
            out["facilitator"] = "ok"
        except Exception as e:
            out["ok"], out["facilitator"] = False, f"unreachable: {str(e)[:120]}"
        return JSONResponse(status_code=200 if out["ok"] else 503, content=out)

    # -- clients -----------------------------------------------------------------------------------

    def _client_token(request: Request) -> str | None:
        header = request.headers.get("authorization", "")
        return header[7:] if header.lower().startswith("bearer ") else None

    def _client_or_token(request: Request, s, task: Task, body: dict):
        """A task's client is whoever holds its buyerToken or a client session for its buyer."""
        import secrets as _secrets

        tok = str(body.get("buyerToken", ""))
        if task.buyer_token and tok and _secrets.compare_digest(task.buyer_token, tok):
            return
        ct = _client_token(request)
        if ct and ct.startswith("cls_"):
            buyer = auth_mod.authenticate_client(s, ct)
            if buyer.id == task.buyer_id:
                return
        raise ApiError(403, "forbidden", "a valid buyerToken or a client session for this task is required")

    @app.post("/v1/clients/nonce")
    async def client_nonce(request: Request):
        body = await request.json()
        with db.session() as s:
            auth_mod.cleanup(s)
            return auth_mod.issue_nonce(s, settings, str(body.get("wallet", "")), str(body.get("network", "")))

    @app.post("/v1/clients/session")
    async def client_session(request: Request):
        body = await request.json()
        with db.session() as s:
            return auth_mod.create_client_session(s, settings, str(body.get("wallet", "")), str(body.get("network", "")), str(body.get("nonce", "")), str(body.get("signature", "")))

    @app.post("/v1/clients/dev-session")
    async def client_dev_session(request: Request):
        body = await request.json()
        with db.session() as s:
            return auth_mod.dev_client_session(s, settings, str(body.get("wallet", "")), str(body.get("network", "")))

    @app.get("/v1/clients/me")
    def client_me(request: Request):
        with db.session() as s:
            b = auth_mod.authenticate_client(s, _client_token(request))
            return auth_mod.client_view(b)

    @app.post("/v1/clients/profile")
    async def client_profile(request: Request):
        body = await request.json()
        with db.session() as s:
            b = auth_mod.authenticate_client(s, _client_token(request))
            if isinstance(body.get("name"), str):
                b.name = body["name"][:80]
            return auth_mod.client_view(b)

    @app.get("/v1/clients/tasks")
    def client_tasks(request: Request, state: str | None = None, limit: int = 50):
        with db.session() as s:
            b = auth_mod.authenticate_client(s, _client_token(request))
            q = select(Task).where(Task.buyer_id == b.id)
            if state:
                q = q.where(Task.state == state)
            rows = s.scalars(q.order_by(Task.created_at.desc()).limit(min(limit, 200))).all()
            out = []
            for t in rows:
                v = task_view(s, t, base)
                v["buyerToken"] = t.buyer_token
                out.append(v)
            counts = {st: s.query(Task).filter(Task.buyer_id == b.id, Task.state == st).count() for st in ("open", "claimed", "submitted", "done", "expired", "rejected", "cancelled", "disputed")}
            from . import ledger as _ledger

            spent = sum(t.price_per_worker * t.workers_wanted + t.fee for t in s.scalars(select(Task).where(Task.buyer_id == b.id)).all())
            refunds = _ledger.balance(s, b.rail, f"refund_due:{b.payer}")
            return {"tasks": out, "counts": counts, "spent": spent, "refundsDue": refunds}

    @app.get("/v1/clients/tasks/{task_id}")
    def client_task(task_id: str, request: Request):
        with db.session() as s:
            b = auth_mod.authenticate_client(s, _client_token(request))
            t = s.get(Task, task_id)
            if t is None or t.buyer_id != b.id:
                raise ApiError(404, "not_found", "no such task")
            v = task_view(s, t, base)
            v["buyerToken"] = t.buyer_token
            v["payload"] = t.payload
            v["acceptance"] = t.acceptance
            v["receipt"] = receipt_view(s, t, base)
            return v

    @app.post("/v1/tasks/{task_id}/cancel")
    async def cancel(task_id: str, request: Request):
        body = await request.json()
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            _client_or_token(request, s, task, body)
            from .tasks import cancel_task

            return cancel_task(s, settings, task, str(body.get("reason", "")))

    # -- workers -----------------------------------------------------------------------------------

    def _worker(request: Request, s):
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else None
        return auth_mod.authenticate(s, token)

    @app.post("/v1/workers/nonce")
    async def worker_nonce(request: Request):
        body = await request.json()
        with db.session() as s:
            auth_mod.cleanup(s)
            return auth_mod.issue_nonce(s, settings, str(body.get("wallet", "")), str(body.get("network", "")))

    @app.post("/v1/workers/session")
    async def worker_session(request: Request):
        body = await request.json()
        with db.session() as s:
            return auth_mod.create_session(s, settings, str(body.get("wallet", "")), str(body.get("network", "")), str(body.get("nonce", "")), str(body.get("signature", "")))

    @app.post("/v1/workers/dev-session")
    async def worker_dev_session(request: Request):
        body = await request.json()
        with db.session() as s:
            return auth_mod.dev_session(s, settings, str(body.get("wallet", "")), str(body.get("network", "")))

    @app.get("/v1/workers/me")
    def worker_me(request: Request):
        with db.session() as s:
            w = _worker(request, s)
            return auth_mod.worker_view(w, settings)

    @app.post("/v1/workers/profile")
    async def worker_profile(request: Request):
        body = await request.json()
        with db.session() as s:
            w = _worker(request, s)
            langs = body.get("languages")
            if isinstance(langs, list):
                w.languages = [str(x)[:8] for x in langs][:10]
            if body.get("acceptTerms") is True and not w.terms_accepted_at:
                w.terms_accepted_at = time.time()
            if "location" in body:
                from .pricing import normalize_location

                try:
                    loc = normalize_location(str(body.get("location") or ""))
                except ValueError as e:
                    raise ApiError(400, "invalid_request", str(e)) from None
                w.location = "" if loc == "Remote" else loc
            return auth_mod.worker_view(w, settings)

    @app.post("/v1/workers/heartbeat")
    def worker_heartbeat(request: Request):
        with db.session() as s:
            w = _worker(request, s)
            workers_mod.heartbeat(s, w)
            return {"ok": True, "online": workers_mod.online_counts(s, settings)["workersOnline"]}

    @app.get("/v1/workers/qualification/{kind}")
    def worker_qualification(kind: str, request: Request):
        with db.session() as s:
            _worker(request, s)
        try:
            return {"type": kind, "samples": samples_for(kind), "needed": 2}
        except ValueError:
            raise ApiError(404, "not_found", "unknown task type") from None

    @app.post("/v1/workers/qualification/{kind}")
    async def worker_qualify(kind: str, request: Request):
        body = await request.json()
        answers = body.get("answers")
        if not isinstance(answers, list) or len(answers) != 3:
            raise ApiError(400, "invalid_request", "answers must list three answers")
        with db.session() as s:
            w = _worker(request, s)
            if not w.terms_accepted_at:
                raise ApiError(403, "terms_required", "accept the worker terms first")
            try:
                correct, passed = score(kind, answers)
                results = results_for(kind, answers)
            except KeyError:
                raise ApiError(404, "not_found", "unknown task type") from None
            if passed and kind not in (w.qualified_types or []):
                w.qualified_types = [*(w.qualified_types or []), kind]
            return {"type": kind, "correct": correct, "passed": passed, "results": results, "explanations": EXPLAIN.get(kind, []), "qualifiedTypes": w.qualified_types}

    @app.get("/v1/workers/tasks")
    def worker_feed(request: Request, category: str | None = None, type: str | None = None, minPrice: int = 0, location: str | None = None):
        with db.session() as s:
            w = _worker(request, s)
            workers_mod.heartbeat(s, w)
            return {"tasks": workers_mod.feed(s, settings, w, category=category, kind=type, min_price=minPrice, location=location)}

    @app.post("/v1/tasks/{task_id}/claim")
    def worker_claim(task_id: str, request: Request):
        with db.session() as s:
            w = _worker(request, s)
            return workers_mod.claim(s, settings, w, task_id, chain=jobs.chain)

    @app.post("/v1/tasks/{task_id}/release")
    def worker_release(task_id: str, request: Request):
        with db.session() as s:
            w = _worker(request, s)
            workers_mod.release(s, w, task_id)
            return {"ok": True}

    @app.post("/v1/tasks/{task_id}/photos")
    async def worker_photo(task_id: str, request: Request):
        """A proof photo for a task the worker holds: the raw image bytes, with optional location headers."""
        data = await request.body()

        def num(name: str) -> float | None:
            v = request.headers.get(name)
            try:
                return float(v) if v not in (None, "") else None
            except ValueError:
                return None

        with db.session() as s:
            w = _worker(request, s)
            return workers_mod.add_photo(s, settings, store, w, task_id, data, num("x-photo-lat"), num("x-photo-lng"), num("x-photo-accuracy"))

    @app.get("/v1/photos/{photo_id}")
    def get_photo(photo_id: str, request: Request):
        """The photo itself. Only the worker who took it, the task's client, or the operator may see it."""
        from fastapi.responses import Response

        from .models import Photo

        with db.session() as s:
            ph = s.get(Photo, photo_id)
            if ph is None or ph.deleted:
                raise ApiError(404, "not_found", "no such photo")
            header = request.headers.get("authorization", "")
            tok = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("token", "")
            allowed = False
            if settings.admin_token and tok and secrets.compare_digest(tok, settings.admin_token):
                allowed = True
            elif tok.startswith("wks_"):
                try:
                    allowed = auth_mod.authenticate(s, tok).id == ph.worker_id
                except ApiError:
                    allowed = False
            elif tok.startswith("cls_"):
                try:
                    t = s.get(Task, ph.task_id)
                    allowed = t is not None and auth_mod.authenticate_client(s, tok).id == t.buyer_id
                except ApiError:
                    allowed = False
            elif tok.startswith("bt_"):
                t = s.get(Task, ph.task_id)
                allowed = t is not None and bool(t.buyer_token) and secrets.compare_digest(t.buyer_token, tok)
            if not allowed:
                raise ApiError(403, "forbidden", "this photo is for the task's client and the operator")
        hit = store.get(photo_id)
        if hit is None:
            raise ApiError(404, "not_found", "the photo has expired")
        return Response(content=hit[0], media_type=hit[1], headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})

    @app.post("/v1/admin/gate")
    async def admin_gate(request: Request):
        """Run the gate over a task body, or over the whole catalogue (`{"catalogue": true}`) to see what a chatbot could do alone."""
        _admin(request)
        body = await request.json()
        from starlette.concurrency import run_in_threadpool

        from .gate import chatbot_can_do
        from .house import catalogue as _catalogue

        http = jobs.scout_http or httpx.Client()

        def work():
            if body.get("catalogue"):
                out = []
                for c in _catalogue():
                    can, why = chatbot_can_do(settings, http, c.get("title", ""), c.get("payload", {}))
                    out.append({"title": c.get("title"), "type": c.get("type"), "chatbotCanDo": can, "reason": why})
                return {"checked": len(out), "refused": sum(1 for o in out if o["chatbotCanDo"]), "results": out}
            can, why = chatbot_can_do(settings, http, str(body.get("title", "")), body.get("payload") or {})
            return {"chatbotCanDo": can, "reason": why}

        return await run_in_threadpool(work)

    @app.post("/v1/tasks/{task_id}/answer")
    async def worker_answer(task_id: str, request: Request):
        body = await request.json()
        if "answer" not in body:
            raise ApiError(400, "invalid_request", "answer is required")
        conf = body.get("confidence")
        with db.session() as s:
            w = _worker(request, s)
            return workers_mod.answer(s, settings, w, task_id, body["answer"], str(body.get("note", "")), float(conf) if conf is not None else None)

    @app.post("/v1/tasks/{task_id}/dispute")
    async def dispute(task_id: str, request: Request):
        body = await request.json()
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            _client_or_token(request, s, task, body)
            return admin_mod.open_dispute(s, settings, task, task.buyer_token or "", str(body.get("reason", "")))

    @app.post("/v1/tasks/{task_id}/accept")
    async def accept(task_id: str, request: Request):
        body = await request.json()
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            _client_or_token(request, s, task, body)
            from .tasks import accept_proof, reject_proof

            if body.get("reject"):
                return reject_proof(s, settings, task, str(body.get("reason", "")))
            return accept_proof(s, settings, task)

    @app.post("/v1/tasks/{task_id}/report")
    async def report(task_id: str, request: Request):
        body = await request.json()
        with db.session() as s:
            w = _worker(request, s)
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            return admin_mod.report_task(s, settings, task, w, str(body.get("reason", "")))

    # -- admin ---------------------------------------------------------------------------------------

    def _admin(request: Request) -> None:
        if not settings.admin_token:
            raise ApiError(404, "not_found", "not found")
        if request.headers.get("authorization", "") != f"Bearer {settings.admin_token}":
            raise ApiError(401, "unauthorized", "admin token required")

    @app.get("/v1/admin/review")
    def admin_review(request: Request):
        _admin(request)
        with db.session() as s:
            return {"tasks": admin_mod.review_queue(s, base)}

    @app.post("/v1/admin/review/{task_id}")
    async def admin_decide(task_id: str, request: Request):
        _admin(request)
        body = await request.json()
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            return admin_mod.decide_review(s, settings, task, str(body.get("decision", "")), str(body.get("note", "")))

    @app.post("/v1/admin/login")
    async def admin_login(request: Request):
        """The /admin page signs in with an id and a password and gets the admin token back."""
        if not settings.admin_token:
            raise ApiError(404, "not_found", "admin is off")
        body = await request.json()
        user, password = str(body.get("user", "")).strip(), str(body.get("password", ""))
        expected = settings.admin_password or settings.admin_token
        if not (secrets.compare_digest(user, settings.admin_user) and secrets.compare_digest(password, expected)):
            raise ApiError(401, "wrong_login", "wrong id or password")
        return {"token": settings.admin_token, "user": settings.admin_user}

    @app.post("/v1/translate")
    async def translate_texts(request: Request):
        """The given English strings in another language, translated once through the AI gateway and kept. Public, capped per day."""
        from . import translate as translate_mod

        body = await request.json()
        lang = str(body.get("lang", ""))
        texts = body.get("texts")
        if lang not in translate_mod.LANGUAGES:
            raise ApiError(400, "invalid_request", f"lang must be one of {', '.join(translate_mod.LANGUAGES)}")
        if not isinstance(texts, list) or not texts or len(texts) > translate_mod.MAX_TEXTS or not all(isinstance(t, str) and len(t) <= translate_mod.MAX_CHARS for t in texts):
            raise ApiError(400, "invalid_request", f"texts must be 1 to {translate_mod.MAX_TEXTS} strings of at most {translate_mod.MAX_CHARS} characters")
        from starlette.concurrency import run_in_threadpool

        def work():
            with db.session() as s:
                return translate_mod.translate(s, settings, jobs.scout_http or httpx.Client(), lang, texts)

        return {"lang": lang, "translations": await run_in_threadpool(work)}

    @app.get("/v1/admin/responses")
    def admin_responses(request: Request, status: str = "all", limit: int = 100):
        """Everything people sent back, with the photos, for the operator only. `status`: all, waiting, disputed, approved, refused."""
        _admin(request)
        with db.session() as s:
            rows = admin_mod.responses(s, base, status, max(1, min(limit, 300)))
            return {"responses": rows, "waiting": sum(1 for r in rows if r["decision"] in ("waiting", "disputed")) if status in ("all", "waiting") else None}

    @app.post("/v1/admin/responses/{task_id}")
    async def admin_decide_response(task_id: str, request: Request):
        """Approve a response (the worker is paid) or refuse it (nobody is paid, the money goes back)."""
        _admin(request)
        body = await request.json()
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise ApiError(404, "not_found", "no such task")
            return admin_mod.decide_response(s, settings, task, str(body.get("decision", "")), str(body.get("note", "")))

    @app.get("/v1/admin/disputes")
    def admin_disputes(request: Request):
        _admin(request)
        with db.session() as s:
            rows = s.scalars(select(Dispute).where(Dispute.status == "open").order_by(Dispute.created_at)).all()
            return {"disputes": [{"disputeId": d.id, "taskId": d.task_id, "reason": d.reason, "createdAt": int(d.created_at), "task": task_view(s, s.get(Task, d.task_id), base)} for d in rows]}

    @app.post("/v1/admin/disputes/{dispute_id}")
    async def admin_resolve(dispute_id: str, request: Request):
        _admin(request)
        body = await request.json()
        with db.session() as s:
            d = s.get(Dispute, dispute_id)
            if d is None:
                raise ApiError(404, "not_found", "no such dispute")
            return admin_mod.resolve_dispute(s, settings, d, str(body.get("outcome", "")), str(body.get("note", "")))

    @app.get("/v1/admin/reports")
    def admin_reports(request: Request):
        _admin(request)
        with db.session() as s:
            rows = s.scalars(select(Report).where(Report.status == "open").order_by(Report.created_at)).all()
            return {"reports": [{"reportId": r.id, "taskId": r.task_id, "workerId": r.worker_id, "reason": r.reason, "createdAt": int(r.created_at)} for r in rows]}

    @app.post("/v1/admin/gold")
    async def admin_gold(request: Request):
        _admin(request)
        body = await request.json()
        with db.session() as s:
            g = admin_mod.add_gold(s, str(body.get("type", "")), body.get("payload") or {}, body.get("answer"), float(body.get("tolerance", 0)), body.get("price"))
            return {"goldId": g.id}

    @app.get("/v1/admin/workers/{worker_id}")
    def admin_worker(worker_id: str, request: Request):
        _admin(request)
        with db.session() as s:
            w = s.get(Worker, worker_id)
            if w is None:
                raise ApiError(404, "not_found", "no such worker")
            from .models import WorkerFlag

            flags = s.scalars(select(WorkerFlag).where(WorkerFlag.worker_id == w.id).order_by(WorkerFlag.at.desc()).limit(50)).all()
            return {**auth_mod.worker_view(w, settings), "flags": [{"kind": f.kind, "detail": f.detail, "at": int(f.at)} for f in flags], "gold": {"total": w.gold_total, "correct": w.gold_correct}}

    @app.post("/v1/admin/workers/{worker_id}")
    async def admin_worker_update(worker_id: str, request: Request):
        _admin(request)
        body = await request.json()
        with db.session() as s:
            w = s.get(Worker, worker_id)
            if w is None:
                raise ApiError(404, "not_found", "no such worker")
            if "paused" in body:
                w.paused = bool(body["paused"])
                w.paused_reason = str(body.get("reason", "")) if w.paused else None
            return auth_mod.worker_view(w, settings)

    @app.get("/v1/scouts")
    def scouts_public():
        from .scouts import view as scouts_view

        with db.session() as s:
            return scouts_view(s, settings)

    @app.post("/v1/admin/escrow/run")
    def admin_escrow_run(request: Request):
        _admin(request)
        return jobs.chain_round()

    @app.get("/v1/admin/escrow")
    def admin_escrow(request: Request):
        _admin(request)
        if jobs.chain is None:
            raise ApiError(404, "not_found", "no escrow contract configured")
        with db.session() as s:
            counts = {st: s.query(Task).filter(Task.chain_state == st).count() for st in ("pending", "open", "closed")}
        return {**jobs.chain.info(), "tasks": counts}

    @app.post("/v1/admin/verifier/run")
    def admin_verifier_run(request: Request):
        _admin(request)
        return jobs.verifier_round()

    @app.post("/v1/admin/scouts/run")
    def admin_scouts_run(request: Request):
        _admin(request)
        return jobs.scout_round()

    @app.post("/v1/admin/scouts/proposals/{proposal_id}")
    async def admin_scouts_decide(proposal_id: str, request: Request):
        _admin(request)
        body = await request.json()
        from . import scouts as scouts_mod
        from .models import Proposal

        with db.session() as s:
            p = s.get(Proposal, proposal_id)
            if p is None:
                raise ApiError(404, "not_found", "no such proposal")
            try:
                if body.get("decision") == "post":
                    scouts_mod.post(s, settings, p)
                elif body.get("decision") == "reject":
                    scouts_mod.reject(p, str(body.get("reason", "")))
                else:
                    raise ApiError(400, "invalid_request", "decision must be post or reject")
            except ValueError as e:
                raise ApiError(409, "not_possible", str(e)) from None
            return {"id": p.id, "status": p.status, "taskId": p.task_id, "reason": p.reason}

    @app.get("/v1/admin/house")
    def admin_house(request: Request):
        _admin(request)
        from .house import status as house_status

        with db.session() as s:
            return house_status(s, settings)

    @app.post("/v1/admin/house/deposit")
    async def admin_house_deposit(request: Request):
        """Record money deposited into the escrow wallet for house tasks. `transaction` is the on-chain id."""
        _admin(request)
        body = await request.json()
        from .house import deposit

        rail = str(body.get("rail", settings.house_rail))
        amount = int(body.get("amount", 0))
        tx = str(body.get("transaction", ""))
        if settings.env != "local" and not tx:
            raise ApiError(400, "invalid_request", "transaction is required outside local")
        with db.session() as s:
            try:
                return deposit(s, rail, amount, tx or "local", str(body.get("memo", "")))
            except ValueError as e:
                raise ApiError(400, "invalid_request", str(e)) from None

    @app.post("/v1/admin/team/run")
    async def admin_team_run(request: Request):
        """Post tasks for the team's own test of the payment path, and mark the team's wallets. Both are labelled as such everywhere."""
        _admin(request)
        body = await request.json()
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(_post_tasks_body, body)

    def _post_tasks_body(body: dict):
        from .house import post_tasks
        from .models import Worker
        from .pricing import parse_task, standard_price

        with db.session() as s:
            marked = 0
            for w in s.query(Worker).filter(Worker.wallet.in_([str(x).lower() for x in body.get("wallets", [])] + [str(x) for x in body.get("wallets", [])])).all():
                w.team, marked = True, marked + 1
            try:
                reqs = [parse_task({"listSeconds": settings.house_list_seconds, **t}) for t in body.get("tasks", [])]
                # A task posted without a price gets the platform's standard reward, never the bare minimum.
                reqs = [r if t.get("pricePerWorker") else r.model_copy(update={"pricePerWorker": max(settings.min_reward, standard_price(r))}) for r, t in zip(reqs, body.get("tasks", []), strict=True)]
                marks = ["claude", "chatgpt", "gemini", "grok", "deepseek"]
                reqs = [r if r.requester else r.model_copy(update={"requester": marks[i % len(marks)]}) for i, r in enumerate(reqs)]
                if settings.gate_enabled and not body.get("skipGate"):
                    from .gate import chatbot_can_do

                    http = jobs.scout_http or httpx.Client()
                    for r in reqs:
                        can, why = chatbot_can_do(settings, http, r.title or "", r.payload or {})
                        if can:
                            raise ApiError(422, "chatbot_can_do", f"refused '{r.title}': {why}")
                tasks_ = post_tasks(s, settings, reqs, settings.house_rail) if reqs else []
            except ValueError as e:
                raise ApiError(400, "invalid_request", str(e)) from e
            for t in tasks_:
                t.team_run = bool(body.get("teamRun", True))
            return {"posted": [t.id for t in tasks_], "markedWallets": marked}

    @app.post("/v1/admin/house/from-fees")
    async def admin_house_from_fees(request: Request):
        """Move earned fees into the pool for platform tasks (the fees were withdrawn to the operator wallet, which funds the pool)."""
        _admin(request)
        body = await request.json()
        from . import ledger as _ledger
        from .house import balance

        rail, amount = str(body.get("rail", settings.house_rail)), int(body.get("amount", 0))
        with db.session() as s:
            if amount <= 0 or _ledger.balance(s, rail, "platform_fee") < amount:
                raise ApiError(400, "invalid_request", "amount must be positive and no more than the fees earned")
            _ledger.post(s, rail, "platform_fee", "house", amount, memo=str(body.get("memo", "fees moved to the pool"))[:200])
            return {"moved": amount, "houseBalance": balance(s, rail), "feesLeft": _ledger.balance(s, rail, "platform_fee")}

    @app.post("/v1/admin/tasks/{task_id}/close")
    async def admin_close_task(task_id: str, request: Request):
        """Decides a task now with the answers it has, instead of waiting for the rest or the deadline."""
        _admin(request)
        from .models import Answer
        from .tasks import try_complete

        with db.session() as s:
            t = s.get(Task, task_id)
            if t is None:
                raise ApiError(404, "not_found", "no such task")
            if t.state not in ("open", "claimed", "submitted"):
                raise ApiError(409, "closed", f"task is {t.state}")
            if not s.query(Answer).filter_by(task_id=t.id).count():
                raise ApiError(409, "no_answers", "nobody has answered yet; cancel it instead")
            try_complete(s, settings, t, force=True)
            return task_view(s, t, base)

    @app.get("/v1/admin/unclaimed")
    def admin_unclaimed(request: Request):
        """Approved rewards nobody has claimed yet, oldest first."""
        _admin(request)
        with db.session() as s:
            return {"tasks": admin_mod.unclaimed_rewards(s)}

    @app.post("/v1/admin/tasks/{task_id}/void-reward")
    async def admin_void_reward(task_id: str, request: Request):
        """Takes back an approved reward nobody claimed: refunds the task on the contract if it is locked there, returns the
        money to the pool, and marks the payout voided. The operator's decision; the worker sees it on their earnings page."""
        _admin(request)
        body = await request.json() if int(request.headers.get("content-length") or 0) > 0 else {}
        reason = str(body.get("reason") or "not claimed; returned to the pool")
        from .escrow_chain import OPEN, chain_ref

        with db.session() as s:
            t = s.get(Task, task_id)
            if t is None:
                raise ApiError(404, "not_found", "no such task")
            if not s.query(Payout).filter(Payout.task_id == t.id, Payout.kind == "task", Payout.status == "claimable").count():
                raise ApiError(409, "nothing_to_void", "this task has no unclaimed reward")
            chain_state, ref = t.chain_state, chain_ref(t)
        tx = None
        if chain_state in ("pending", "open"):
            if jobs.chain is None:
                raise ApiError(503, "chain_off", "the contract is not connected; the locked money cannot be released right now")
            try:
                if jobs.chain.status(ref) == OPEN:
                    tx = jobs.chain.refund(ref)
            except Exception as e:
                raise ApiError(503, "refund_failed", f"the contract refund could not be sent: {str(e)[:120]}") from e
        with db.session() as s:
            return admin_mod.void_reward(s, s.get(Task, task_id), reason, tx)

    @app.post("/v1/admin/tasks/{task_id}/cancel")
    async def admin_cancel_task(task_id: str, request: Request):
        """Takes a task off the board. Unused money returns to where it came from; anyone who already answered keeps their claim."""
        _admin(request)
        body = await request.json() if int(request.headers.get("content-length") or 0) > 0 else {}
        from .tasks import cancel_task

        with db.session() as s:
            t = s.get(Task, task_id)
            if t is None:
                raise ApiError(404, "not_found", "no such task")
            try:
                return cancel_task(s, settings, t, str(body.get("reason", "taken off the board by the operator")))
            except ApiError:
                raise
            except Exception as e:
                raise ApiError(409, "cannot_cancel", str(e)[:200]) from e

    @app.post("/v1/admin/house/post")
    async def admin_house_post(request: Request):
        """Post one house batch now."""
        _admin(request)
        return jobs.house_round()

    @app.get("/v1/admin/gold")
    def admin_gold_list(request: Request):
        _admin(request)
        with db.session() as s:
            return {"gold": [{"goldId": g.id, "type": g.type, "active": g.active, "price": g.price} for g in s.scalars(select(GoldTask)).all()]}

    @app.post("/v1/tasks/{task_id}/claim-reward")
    def worker_claim_reward(task_id: str, request: Request):
        """The Claim button: pays this worker's accepted reward for the task from the operator wallet."""
        with db.session() as s:
            w = _worker(request, s)
            out = workers_mod.claim_reward(s, settings, jobs.reward_sender, w, task_id)
        if out.get("mode") != "contract":
            return out
        from .escrow_chain import settle_one

        if jobs.chain is None:
            raise ApiError(503, "payouts_off", "the contract is not connected; your reward stays queued and will be paid shortly")
        try:
            tx = settle_one(db, settings, jobs.chain, task_id)
        except Exception as e:
            # Left queued: the contract loop settles it on its next pass.
            raise ApiError(503, "settle_failed", f"the settlement could not be sent right now ({str(e)[:100]}); it will be paid automatically shortly") from e
        net = next((r["network"] for r in settings.rails() if r["name"] == "robinhood"), "")
        return {"taskId": task_id, "amount": out["amount"], "transaction": tx, "explorer": EXPLORER_TX.get(net, "{tx}").format(tx=tx)}

    @app.post("/v1/workers/gas")
    def worker_gas(request: Request):
        """Covers the gas for a withdrawal: a little ETH to the worker's wallet, once a day, for wallets we have paid."""
        with db.session() as s:
            w = _worker(request, s)
            if w.rail != "robinhood":
                raise ApiError(400, "unsupported", "gas help is for Robinhood Chain wallets")
            paid = s.query(Payout).filter(Payout.worker_id == w.id, Payout.status == "sent").count()
            if paid == 0:
                raise ApiError(403, "not_yet", "gas help starts after your first paid task")
            if w.gas_granted_at and time.time() - w.gas_granted_at < 86400:
                raise ApiError(429, "already_granted", "gas was covered for this wallet in the last 24 hours")
            wallet = w.wallet
        result = facilitator.gas(wallet)
        if result.get("granted"):
            with db.session() as s:
                w = _worker(request, s)
                w.gas_granted_at = time.time()
        elif result.get("reason") not in (None, "", "the wallet already has enough gas"):
            raise ApiError(503, "gas_unavailable", result.get("message") or "gas help is not available right now")
        return result

    @app.get("/v1/workers/earnings")
    def worker_earnings(request: Request):
        with db.session() as s:
            w = _worker(request, s)
            return workers_mod.earnings(s, w)

    @app.middleware("http")
    async def _timing(request: Request, call_next):
        t0 = time.time()
        response: Response = await call_next(request)
        response.headers["X-Response-Time-Ms"] = str(int((time.time() - t0) * 1000))
        return response

    return app
