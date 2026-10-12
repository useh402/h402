"""Worker-facing service: heartbeat, feed, claim, answer, earnings."""

from __future__ import annotations

import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ledger
from .config import EXPLORER_TX, Settings
from .models import Answer, Claim, Payout, Task, Worker, new_id, now
from .pricing import TASK_TYPES
from .quality import answer_gold, check_answer_behaviour, due_gold, gold_card, reputation_for
from .tasks import ApiError, submit
from .tasks import claim as hold_slot


def heartbeat(session: Session, worker: Worker) -> None:
    worker.last_seen = now()


def online_counts(session: Session, settings: Settings) -> dict:
    since = now() - settings.online_window_seconds
    workers = session.scalars(select(Worker).where(Worker.last_seen >= since, Worker.paused.is_(False))).all()
    by_type = {t: 0 for t in TASK_TYPES}
    for w in workers:
        for t in w.qualified_types or []:
            if t in by_type:
                by_type[t] += 1
    return {"workersOnline": len(workers), "byType": by_type, "windowSeconds": settings.online_window_seconds}


def _live_claims(session: Session, task_id: str) -> list[Claim]:
    return [c for c in session.scalars(select(Claim).where(Claim.task_id == task_id, Claim.released.is_(False))).all() if c.expires_at > now()]


def qualified_types(worker: Worker, settings: Settings) -> list[str]:
    """The types of work this worker may take. With the qualification gate off, every type; otherwise the ones they passed."""
    if not settings.qualification_required:
        return list(TASK_TYPES)
    return list(worker.qualified_types or [])


def feed(session: Session, settings: Settings, worker: Worker, category: str | None = None, kind: str | None = None, min_price: int = 0, location: str | None = None) -> list[dict]:
    qualified = set(qualified_types(worker, settings))
    if kind:
        qualified = {kind} & qualified
    if not qualified:
        return []
    answered = {a.task_id for a in session.scalars(select(Answer).where(Answer.worker_id == worker.id)).all()}
    pool = ledger.balance(session, settings.house_rail, "house")  # a listed task the pool cannot cover is kept out of the feed
    tasks = session.scalars(
        select(Task).where(Task.state.in_(("open", "claimed", "submitted")), Task.moderation == "allowed", Task.deadline > now(), Task.type.in_(list(qualified)), Task.min_reputation <= worker.reputation).order_by(Task.price_per_worker.desc(), Task.created_at).limit(settings.feed_limit * 3)
    ).all()
    out = []
    gold = due_gold(session, settings, worker, list(qualified))
    if gold is not None and not category and not location and min_price <= gold.price:
        card = gold_card(gold)
        card.pop("payload", None)
        card["held"] = False
        out.append(card)
    here = (location or worker.location or "").strip().lower()
    for t in tasks:
        if t.id in answered or reputation_for(worker, t.type) < t.min_reputation:
            continue
        if t.chain_state == "listed" and t.price_per_worker * t.workers_wanted + t.fee > pool:
            continue
        if t.price_per_worker < min_price:
            continue
        if category and (t.payload or {}).get("category") != category:
            continue
        if location and t.location.lower() not in ("remote", here):
            continue
        # Tasks tied to a place only show to workers who said they are there, or to anyone when they set no location.
        if t.location != "Remote" and worker.location and t.location.lower() != worker.location.lower():
            continue
        n_answers = session.scalar(select(func.count()).select_from(Answer).where(Answer.task_id == t.id)) or 0
        live = _live_claims(session, t.id)
        mine = next((c for c in live if c.worker_id == worker.id), None)
        if n_answers + len(live) >= t.workers_wanted and mine is None:
            continue
        out.append(_card(t, mine, show_payload=mine is not None))
        if len(out) >= settings.feed_limit:
            break
    return out


def _card(t: Task, mine: Claim | None, show_payload: bool) -> dict:
    from .catalogue import CATEGORIES, category_of

    cat = category_of(t.payload or {})
    card = {
        "taskId": t.id,
        "type": t.type,
        "title": t.title or _preview(t),
        "location": t.location,
        "difficulty": t.difficulty,
        "effortMinutes": t.effort_minutes,
        "acceptance": t.acceptance or None,
        "category": cat,
        "categoryLabel": CATEGORIES[cat]["label"] if cat else None,
        "price": t.price_per_worker,
        "timeLeft": max(0, int(t.deadline - now())),
        "deadline": int(t.deadline),
        "workers": t.workers_wanted,
        "preview": _preview(t),
        "held": mine is not None,
        "holdExpiresAt": int(mine.expires_at) if mine else None,
    }
    if mine is not None and mine.code:
        card["captureCode"] = mine.code
    if show_payload:
        card["payload"] = t.payload
    return card


def _preview(t: Task) -> str:
    p = t.payload or {}
    text = p.get("question") or p.get("instructions") or p.get("item") or p.get("text") or ("image" if p.get("image") else "")
    text = str(text)
    return text[:90] + ("..." if len(text) > 90 else "")


def claim(session: Session, settings: Settings, worker: Worker, task_id: str, chain=None) -> dict:
    if task_id.startswith("gold_"):
        from .models import GoldTask

        g = session.get(GoldTask, task_id)
        if g is None or g.type not in qualified_types(worker, settings):
            raise ApiError(404, "not_found", "no such task")
        return gold_card(g)
    task = session.get(Task, task_id)
    if task is None or task.moderation != "allowed":
        raise ApiError(404, "not_found", "no such task")
    if task.type not in qualified_types(worker, settings):
        raise ApiError(403, "not_qualified", f"complete the {task.type} qualification first")
    if task.deadline <= now():
        raise ApiError(409, "closed", "the task deadline has passed")
    if task.chain_state == "releasing":
        raise ApiError(409, "try_again", "This task is being reset after someone dropped it. Try again in a moment.")
    if task.chain_state == "listed":
        # The money for a platform task is locked in the contract when the first person takes it, before any work starts.
        need = task.price_per_worker * task.workers_wanted + task.fee
        if settings.house_payout != "wallet":
            try:
                funded = chain is not None and chain.available() >= need
            except Exception as e:
                raise ApiError(503, "try_again", "could not confirm the reward is funded; try again in a moment") from e
            if not funded:
                raise ApiError(409, "not_funded", "This task cannot be funded right now. Please try another one.")
        from .tasks import fund_listed

        if not fund_listed(session, task, settings):
            raise ApiError(409, "not_funded", "This task cannot be funded right now. Please try another one.")
    c = hold_slot(session, task, worker)
    hold = task.time_limit_seconds if TASK_TYPES[task.type]["rule"] == "proof" else settings.claim_hold_seconds
    c.expires_at = min(task.deadline, now() + hold)
    if (task.payload or {}).get("proof") == "photos" and not c.code:
        c.code = capture_code()
    return _card(task, c, show_payload=True)


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, so it reads clearly from paper


def capture_code() -> str:
    import secrets

    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def add_photo(session: Session, settings: Settings, store, worker: Worker, task_id: str, data: bytes, lat: float | None, lng: float | None, accuracy: float | None) -> dict:
    """Keeps a proof photo for a task the worker currently holds. Checks the type, the size, and the place when the task has one."""
    from .models import Photo
    from .storage import sniff

    task = session.get(Task, task_id)
    if task is None:
        raise ApiError(404, "not_found", "no such task")
    mine = next((c for c in _live_claims(session, task_id) if c.worker_id == worker.id), None)
    if mine is None:
        raise ApiError(409, "no_hold", "take the task first; photos belong to a task you hold")
    if len(data) > settings.photo_max_bytes:
        raise ApiError(413, "too_large", f"photo must be under {settings.photo_max_bytes // 1_000_000} MB")
    kind = sniff(data)
    if kind is None:
        raise ApiError(400, "not_a_photo", "the file is not a JPEG, PNG, WebP or HEIC photo")
    have = session.query(Photo).filter(Photo.claim_id == mine.id, Photo.deleted.is_(False)).count()
    if have >= settings.photo_max_per_answer:
        raise ApiError(409, "too_many", f"at most {settings.photo_max_per_answer} photos per task")
    geo = (task.payload or {}).get("geo")
    dist = None
    if isinstance(geo, dict):
        if lat is None or lng is None:
            raise ApiError(400, "location_needed", "this task needs the photo's location; allow location access and try again")
        dist = distance_m(lat, lng, float(geo["lat"]), float(geo["lng"]))
        allowed = settings.geo_radius_m + (accuracy or 0)
        if dist > allowed:
            raise ApiError(409, "wrong_place", f"the photo was taken about {int(dist)} m from the place; it must be taken there")
    photo = Photo(id=new_id("ph"), task_id=task.id, worker_id=worker.id, claim_id=mine.id, content_type=kind, size=len(data), code=mine.code, lat=lat, lng=lng, accuracy_m=accuracy, distance_m=dist)
    session.add(photo)
    session.flush()
    store.put(photo.id, data, kind)
    return {"photoId": photo.id, "contentType": kind, "size": len(data), "distanceM": int(dist) if dist is not None else None, "code": mine.code}


def validate_photos(session: Session, worker: Worker, task: Task, ids) -> None:
    from .models import Photo

    if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or not all(isinstance(i, str) for i in ids):
        raise ApiError(400, "invalid_answer", "one to three photos taken now are required")
    mine = next((c for c in _live_claims(session, task.id) if c.worker_id == worker.id), None)
    rows = session.query(Photo).filter(Photo.id.in_(ids), Photo.deleted.is_(False)).all()
    if len(rows) != len(set(ids)) or any(p.worker_id != worker.id or p.task_id != task.id or (mine and p.claim_id != mine.id) for p in rows):
        raise ApiError(400, "invalid_answer", "those photos were not taken for this task")


def release(session: Session, worker: Worker, task_id: str) -> None:
    if task_id.startswith("gold_"):
        return
    for c in session.scalars(select(Claim).where(Claim.task_id == task_id, Claim.worker_id == worker.id, Claim.released.is_(False))).all():
        c.released = True
    task = session.get(Task, task_id)
    if task and task.state == "claimed" and not _live_claims(session, task_id):
        from .states import transition

        transition(session, task, "open", "holds released", actor=worker.handle)


def answer(session: Session, settings: Settings, worker: Worker, task_id: str, value, note: str, confidence: float | None) -> dict:
    if task_id.startswith("gold_"):
        from .models import GoldTask

        g = session.get(GoldTask, task_id)
        if g is None:
            raise ApiError(404, "not_found", "no such task")
        validate_answer(g.type, g.payload, value)
        return answer_gold(session, settings, worker, g, value)
    task = session.get(Task, task_id)
    if task is None:
        raise ApiError(404, "not_found", "no such task")
    mine = next((c for c in _live_claims(session, task_id) if c.worker_id == worker.id), None)
    if mine is None:
        raise ApiError(409, "no_hold", "claim the task first (or the hold expired)")
    validate_answer(task.type, task.payload, value)
    if task.type == "do" and (task.payload or {}).get("proof") == "photos":
        validate_photos(session, worker, task, value.get("photos"))
        value = {**value, "code": mine.code}
    seconds = round(now() - mine.claimed_at, 2)
    submit(session, settings, task, worker, value, note[:500], confidence)
    worker.answered += 1
    check_answer_behaviour(session, settings, worker, task.type, value, seconds)
    session.flush()
    out = {"taskId": task.id, "state": task.state, "accepted": True}
    if task.state == "done":
        a = session.scalars(select(Answer).where(Answer.task_id == task.id, Answer.worker_id == worker.id)).one()
        out["agreed"] = bool(a.agrees)
    return out


def validate_answer(kind: str, payload: dict, value) -> None:
    if kind == "choose":
        n = len(payload.get("options", []))
        if not isinstance(value, int) or not 0 <= value < n:
            raise ApiError(400, "invalid_answer", f"answer must be an option index 0 to {n - 1}")
    elif kind == "verify":
        if value not in ("yes", "no", "unsure"):
            raise ApiError(400, "invalid_answer", "answer must be yes, no or unsure")
    elif kind == "rate":
        if not isinstance(value, int | float) or not 1 <= value <= 5:
            raise ApiError(400, "invalid_answer", "answer must be a score 1 to 5")
    elif kind == "label":
        labels = set(payload.get("labels", []))
        if not isinstance(value, list) or not value or not set(value) <= labels:
            raise ApiError(400, "invalid_answer", "answer must be a non-empty list of the given labels")
    elif kind in ("read", "answer"):
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise ApiError(400, "invalid_answer", "answer must be a non-empty text")
    elif kind == "do":
        want = payload.get("proof", "text")
        if not isinstance(value, dict):
            raise ApiError(400, "invalid_answer", "proof must be an object with text and/or screenshot")
        text, shot = value.get("text"), value.get("screenshot")
        if want == "photos":
            if not isinstance(value.get("photos"), list):
                raise ApiError(400, "invalid_answer", "one to three photos taken now are required")
            if payload.get("write") and not (isinstance(text, str) and len(text.strip()) >= 5):
                raise ApiError(400, "invalid_answer", f"write what was asked as well: {payload['write']}")
            if isinstance(text, str) and len(text) > 4000:
                raise ApiError(400, "invalid_answer", "proof text is too long")
            return
        if want in ("text", "both") and not (isinstance(text, str) and len(text.strip()) >= 5):
            raise ApiError(400, "invalid_answer", "a short written proof is required")
        if want in ("screenshot", "both") and not isinstance(shot, str):
            raise ApiError(400, "invalid_answer", "a screenshot is required")
        if isinstance(shot, str):
            ok = shot.startswith("https://") and len(shot) <= 2000 or (shot.startswith("data:image/") and len(shot) <= 2_000_000)
            if not ok:
                raise ApiError(400, "invalid_answer", "screenshot must be an https link or an image under 1.5 MB")
        if isinstance(text, str) and len(text) > 4000:
            raise ApiError(400, "invalid_answer", "proof text is too long")


def earnings(session: Session, worker: Worker) -> dict:
    pending = ledger.balance(session, worker.rail, f"worker_due:{worker.id}")
    day = now() - 86400
    week = now() - 7 * 86400
    rows = session.execute(
        select(Answer.submitted_at, Task.price_per_worker).join(Task, Task.id == Answer.task_id).where(Answer.worker_id == worker.id, Answer.agrees.is_(True))
    ).all()
    today = sum(p for at, p in rows if at >= day)
    this_week = sum(p for at, p in rows if at >= week)
    payouts = session.scalars(select(Payout).where(Payout.worker_id == worker.id).order_by(Payout.created_at.desc()).limit(50)).all()
    sent = [p for p in payouts if p.status == "sent"]
    # Work that was refused: proofs and written answers the review or the operator found wrong. Shown so the worker knows why.
    refused_rows = session.execute(
        select(Answer, Task).join(Task, Task.id == Answer.task_id).where(Answer.worker_id == worker.id, Answer.agrees.is_(False), Task.type.in_(("do", "answer")), Task.state.in_(("expired", "rejected"))).order_by(Answer.submitted_at.desc()).limit(50)
    ).all()
    refused = [
        {"taskId": t.id, "title": t.title, "amount": t.price_per_worker, "at": int(a.submitted_at), "reason": (t.review or {}).get("reason") if (t.review or {}).get("verdict") == "wrong" else "refused after review"}
        for a, t in refused_rows
    ]
    # Rewards that were approved but taken back before they were claimed.
    for po in payouts:
        if po.status == "voided" and po.task_id:
            t = session.get(Task, po.task_id)
            v = ((t.verification or {}).get("rewardVoided") or {}) if t else {}
            refused.append({"taskId": po.task_id, "title": t.title if t else po.task_id, "amount": po.amount, "at": int(po.sent_at or po.created_at), "reason": f"Reward withdrawn before it was claimed: {v.get('reason') or 'returned to the pool'}"})
    refused.sort(key=lambda r: -r["at"])
    return {
        "rail": worker.rail,
        "wallet": worker.wallet,
        "pending": pending,
        "today": today,
        "thisWeek": this_week,
        "allTime": sum(p for _, p in rows),
        "paid": sum(p.amount for p in sent),
        "answered": worker.answered,
        "agreed": worker.agreed,
        "reputation": round(worker.reputation, 3),
        "tier": worker.tier,
        "gold": {"total": worker.gold_total, "correct": worker.gold_correct},
        "byType": worker.by_type or {},
        "payouts": [
            {"amount": p.amount, "status": p.status, "taskId": p.task_id, "transaction": p.batch_ref, "at": int(p.sent_at or p.created_at), "explorer": _explorer(session, p)}
            for p in payouts
        ],
        "refused": refused,
    }


def _explorer(session: Session, p: Payout) -> str | None:
    if not p.batch_ref:
        return None
    task = session.get(Task, p.task_id) if p.task_id else None
    from .models import Payment

    payment = session.get(Payment, task.payment_id) if task else None
    if payment and payment.network in EXPLORER_TX:
        return EXPLORER_TX[payment.network].format(tx=p.batch_ref)
    return None


def expire_holds(session: Session) -> int:
    """Release expired claims and reopen tasks that no longer have live holds."""
    from .states import transition

    expired = session.scalars(select(Claim).where(Claim.released.is_(False), Claim.expires_at <= now())).all()
    n = 0
    for c in expired:
        c.released = True
        n += 1
        task = session.get(Task, c.task_id)
        if task and task.state == "claimed" and not _live_claims(session, task.id):
            transition(session, task, "open", "hold expired")
    return n


__all__ = ["time"]


def claim_reward(session: Session, settings: Settings, sender, worker: Worker, task_id: str) -> dict:
    """Pays a worker's accepted reward for a task from the operator wallet, now, within the daily cap."""
    from . import ledger as _ledger

    rows = session.scalars(select(Payout).where(Payout.task_id == task_id, Payout.worker_id == worker.id, Payout.status == "claimable")).all()
    if not rows:
        raise ApiError(404, "nothing_to_claim", "there is no reward waiting for you on this task")
    amount = sum(p.amount for p in rows)
    task = session.get(Task, task_id)
    if task is not None and task.chain_state in ("pending", "open"):
        # Contract mode: the contract pays everyone accepted on this task in one settlement; this worker's claim triggers it.
        for p in session.scalars(select(Payout).where(Payout.task_id == task_id, Payout.status == "claimable")).all():
            p.status = "queued"
        return {"taskId": task_id, "amount": amount, "mode": "contract"}
    if sender is None:
        raise ApiError(503, "payouts_off", "rewards cannot be sent right now; your reward stays claimable")
    since = now() - 86400
    sent_today = sum(p.amount for p in session.scalars(select(Payout).where(Payout.status == "sent", Payout.sent_at >= since, Payout.batch_ref.like("0x%"))).all())
    if sent_today + amount > settings.wallet_payout_daily_cap:
        raise ApiError(429, "daily_cap", "today's reward budget is used up; your reward stays claimable and you can claim it tomorrow")
    try:
        if sender.balance() < amount:
            raise ApiError(503, "wallet_low", "the reward wallet is being topped up; your reward stays claimable")
        tx, raw = sender.prepare([(worker.wallet, amount)])
        sender.broadcast(raw)
    except ApiError:
        raise
    except Exception as e:
        raise ApiError(503, "send_failed", f"the transfer could not be sent: {str(e)[:120]}; your reward stays claimable") from e
    for p in rows:
        p.status, p.batch_ref, p.sent_at = "sent", tx, now()
        _ledger.post(session, p.rail, f"worker_due:{worker.id}", "escrow", p.amount, task_id=p.task_id, memo=f"claimed, paid from the wallet {tx}")
    from .config import EXPLORER_TX

    net = next((r["network"] for r in settings.rails() if r["name"] == worker.rail), "")
    return {"taskId": task_id, "amount": amount, "transaction": tx, "explorer": EXPLORER_TX.get(net, "{tx}").format(tx=tx)}
