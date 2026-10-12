"""Scouts: each model proposes work a person should do, through the Vercel AI Gateway.

The model's output is untrusted data. It is parsed, validated as a task, moderated, checked for
invented facts and duplicates, and priced by our formula (never by the model). What survives waits
for an operator, or is posted from the house pool when auto-post is on.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalogue import CATEGORIES
from .config import Settings
from .models import Proposal, ScoutRun, Task, new_id, now
from .moderation import classify
from .pricing import REQUESTERS, TASK_TYPES, TaskRequest, parse_task, standard_price

logger = logging.getLogger("humanapi.api.scouts")

PHONE = re.compile(r"(?<!\d)(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
STREET = re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+(\s[A-Z][a-z]+)*\s(St|Street|Ave|Avenue|Blvd|Road|Rd|Dr|Drive|Way|Lane|Ln)\b")
URL = re.compile(r"https?://\S+")

SYSTEM = (
    "You propose small paid tasks for a marketplace where real people in the United States do work that software "
    "cannot do alone: phone a business and ask something, go and look at something in person, open a page that blocks "
    "automated visitors, check whether something is real or current, read a hard image, give a human judgement, share local knowledge. "
    "Reply with JSON only."
)


def models(settings: Settings) -> dict[str, str]:
    out = {}
    for part in settings.scout_models.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() in REQUESTERS:
                out[k.strip()] = v.strip()
    return out


def prompt(open_titles: list[str], n: int) -> str:
    cats = "\n".join(f"- {k}: {v['need']}" for k, v in CATEGORIES.items())
    types = "do (an action with proof), verify (yes/no about a text), choose (pick one option), rate (score 1-5), label (tag an item), answer (short written answer)"
    return f"""Propose {n} new tasks. Each must be something a program cannot reliably do itself and a person can finish in under 45 minutes.

Categories:
{cats}

Task types: {types}

Rules:
- United States only. Name a real US city or a well known US business or public service by name.
- Do NOT include phone numbers, street addresses or links. The person doing the task looks those up. Invented details are rejected.
- No passwords, logins, codes, purchases, payments, private individuals, or anything sexual or violent.
- Do not repeat these open tasks: {json.dumps(open_titles[:40])}

Return: {{"tasks": [{{"title": "under 100 characters", "category": "one category key", "type": "one task type", "location": "Remote or City, ST",
"instructions": "for do: exact steps and what to write back, 40 to 600 characters", "question": "for verify, choose, answer", "text": "for verify: the text to check",
"options": ["for choose: 2 to 5"], "item": "for rate or label", "rubric": "for rate", "labels": ["for label: 2 to 8"],
"proof": "for do: text, screenshot or both", "acceptance": "what a good result contains", "effortMinutes": 10, "why": "why a person is needed, one sentence"}}]}}"""


def call_gateway(settings: Settings, http: httpx.Client, model: str, user: str) -> tuple[list[dict], int, int]:
    import time

    r = None
    for attempt in range(3):  # a failed name lookup or a dropped connection is retried; a refusal from the gateway is not
        try:
            r = http.post(
                f"{settings.ai_gateway_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_gateway_api_key}"},
                json={"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], "temperature": 0.9, "max_tokens": 2500},
                timeout=90,
            )
            break
        except httpx.TransportError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    assert r is not None
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"] or ""
    usage = data.get("usage") or {}
    return extract_tasks(text), int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def extract_tasks(text: str) -> list[dict]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    tasks = data.get("tasks") if isinstance(data, dict) else None
    return [t for t in tasks if isinstance(t, dict)][:10] if isinstance(tasks, list) else []


def price_for(settings: Settings, req: TaskRequest) -> int:
    """Our formula, never the model's number. See pricing.standard_price."""
    return max(settings.min_reward, standard_price(req))


def to_body(raw: dict) -> dict:
    """Map the model's flat object onto our task body. Only known keys are copied."""
    kind = str(raw.get("type", "")).strip().lower()
    # Models often label a call or a visit as "verify" or "answer". If it reads as steps to carry out, it is an action task.
    has_question = isinstance(raw.get("question"), str) and raw["question"].strip()
    if kind in ("verify", "answer", "choose") and not has_question and isinstance(raw.get("instructions"), str) and len(raw["instructions"]) >= 20:
        kind = "do"
    payload: dict = {}
    if raw.get("category") in CATEGORIES:
        payload["category"] = raw["category"]
    for key in ("instructions", "question", "text", "item", "rubric"):
        if isinstance(raw.get(key), str) and raw[key].strip():
            payload[key] = raw[key].strip()[:2000]
    for key in ("options", "labels"):
        if isinstance(raw.get(key), list):
            payload[key] = [str(x)[:300] for x in raw[key]][:30]
    if kind == "do":
        payload["proof"] = raw.get("proof") if raw.get("proof") in ("text", "screenshot", "both") else "text"
    body: dict = {"type": kind, "payload": payload, "title": str(raw.get("title", ""))[:140], "location": str(raw.get("location") or "Remote"), "acceptance": str(raw.get("acceptance") or "")[:500]}
    try:
        body["effortMinutes"] = max(1, min(240, int(raw.get("effortMinutes") or 0))) or None
    except (TypeError, ValueError):
        body["effortMinutes"] = None
    return body


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 2}


def is_duplicate(title: str, others: list[str]) -> bool:
    a = _tokens(title)
    if not a:
        return True
    for o in others:
        b = _tokens(o)
        if b and len(a & b) / len(a | b) >= 0.6:
            return True
    return False


def check(session: Session, settings: Settings, raw: dict, requester: str, seen: list[str], http: httpx.Client | None = None) -> tuple[dict | None, int, str | None]:
    """Returns (body, price, rejection reason)."""
    body = to_body(raw)
    if body["type"] not in TASK_TYPES or body["type"] == "read":
        return None, 0, "unsupported type of work"
    text = json.dumps(raw, ensure_ascii=False)
    if PHONE.search(text):
        return None, 0, "contains a phone number; the worker must look it up"
    if STREET.search(text):
        return None, 0, "contains a street address; the worker must look it up"
    if URL.search(text):
        return None, 0, "contains a link; links from a model are not trusted"
    try:
        req = parse_task({**body, "requester": requester})
    except ValueError as e:
        return None, 0, f"not a valid task: {str(e)[:200]}"
    if len(req.title) < 12:
        return None, 0, "title too short"
    decision, reason = classify(settings, req.type, req.payload)
    if decision != "allow":
        return None, 0, f"moderation: {reason}"
    if is_duplicate(req.title, seen):
        return None, 0, "too similar to an existing task"
    if settings.gate_enabled and http is not None:
        from .gate import chatbot_can_do

        can, why = chatbot_can_do(settings, http, req.title or "", req.payload or {})
        if can:
            return None, 0, why
    price = price_for(settings, req)
    body.update({"requester": requester, "pricePerWorker": max(price, TASK_TYPES[req.type]["base"]), "title": req.title, "location": req.location, "timeLimitSeconds": 1800 if req.type == "do" else None})
    return body, body["pricePerWorker"], None


def calls_today(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ScoutRun).where(ScoutRun.at >= now() - 86400)) or 0


def known_titles(session: Session) -> list[str]:
    open_titles = [t for (t,) in session.execute(select(Task.title).where(Task.state.in_(("paid", "open", "claimed", "submitted")))).all()]
    recent = [t for (t,) in session.execute(select(Proposal.title).where(Proposal.created_at >= now() - 7 * 86400, Proposal.status != "rejected")).all()]
    return open_titles + recent


def run_model(db, settings: Settings, http: httpx.Client, requester: str, model: str) -> int:
    """One search by one model. The database is not held open while waiting for the gateway."""
    with db.session() as session:
        seen = known_titles(session)
    error, raws, tin, tout = None, [], 0, 0
    try:
        raws, tin, tout = call_gateway(settings, http, model, prompt(seen, settings.scout_proposals_per_run))
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:250]}"
        logger.warning("scout %s failed: %s", requester, error)
    with db.session() as session:
        run = ScoutRun(id=new_id("run"), requester=requester, model=model, ok=error is None, error=error, input_tokens=tin, output_tokens=tout)
        session.add(run)
        session.flush()
        seen = known_titles(session)
        for raw in raws[: settings.scout_proposals_per_run + 2]:
            body, price, reason = check(session, settings, raw, requester, seen, http)
            p = Proposal(id=new_id("prop"), run_id=run.id, requester=requester, title=str(raw.get("title", ""))[:200], raw=raw, body=body, why=str(raw.get("why", ""))[:400], price=price, status="rejected" if reason else "review", reason=reason, decided_at=now() if reason else None)
            session.add(p)
            session.flush()
            run.proposed += 1
            if not reason:
                seen.append(p.title)
                if settings.scout_auto_post:
                    try:
                        post(session, settings, p)
                    except ValueError as e:
                        p.reason = f"waiting: {e}"[:300]
        return run.proposed


def post(session: Session, settings: Settings, p: Proposal) -> Proposal:
    """Turn an approved proposal into a live task, paid from the house pool."""
    from .house import post_tasks

    if p.status != "review" or not p.body:
        raise ValueError(f"proposal is {p.status}")
    req = parse_task({k: v for k, v in p.body.items() if v is not None}).model_copy(update={"listSeconds": settings.house_list_seconds})
    tasks = post_tasks(session, settings, [req], settings.house_rail)  # raises ValueError when the pool is short
    p.status, p.task_id, p.decided_at, p.reason = "posted", tasks[0].id, now(), None
    return p


def reject(p: Proposal, reason: str) -> Proposal:
    if p.status != "review":
        raise ValueError(f"proposal is {p.status}")
    p.status, p.reason, p.decided_at = "rejected", (reason or "rejected by an operator")[:300], now()
    return p


def run_round(db, settings: Settings, http: httpx.Client) -> dict:
    out = {"runs": 0, "proposed": 0, "skipped": ""}
    if not settings.ai_gateway_api_key:
        out["skipped"] = "no gateway key"
        return out
    for requester, model in models(settings).items():
        with db.session() as session:
            if calls_today(session) >= settings.scout_daily_calls:
                out["skipped"] = "daily call limit reached"
                break
        out["proposed"] += run_model(db, settings, http, requester, model)
        out["runs"] += 1
    return out


def view(session: Session, settings: Settings, limit: int = 60) -> dict:
    scouts = []
    for requester, model in models(settings).items():
        last = session.scalars(select(ScoutRun).where(ScoutRun.requester == requester).order_by(ScoutRun.at.desc())).first()
        counts = dict(session.execute(select(Proposal.status, func.count()).where(Proposal.requester == requester).group_by(Proposal.status)).all())
        tokens = session.execute(select(func.coalesce(func.sum(ScoutRun.input_tokens), 0), func.coalesce(func.sum(ScoutRun.output_tokens), 0)).where(ScoutRun.requester == requester)).one()
        scouts.append({"requester": requester, "label": REQUESTERS[requester], "model": model, "lastRunAt": int(last.at) if last else None, "lastOk": last.ok if last else None, "lastError": last.error if last else None, "proposed": sum(counts.values()), "posted": counts.get("posted", 0), "waiting": counts.get("review", 0), "rejected": counts.get("rejected", 0), "inputTokens": int(tokens[0]), "outputTokens": int(tokens[1])})
    rows = session.scalars(select(Proposal).order_by(Proposal.created_at.desc()).limit(min(limit, 200))).all()
    feed = [{"id": p.id, "requester": p.requester, "title": p.title, "type": (p.body or p.raw).get("type"), "category": ((p.body or {}).get("payload") or {}).get("category") or p.raw.get("category"), "location": (p.body or p.raw).get("location"), "price": p.price, "why": p.why, "status": p.status, "reason": p.reason, "taskId": p.task_id, "createdAt": int(p.created_at)} for p in rows]
    return {"enabled": settings.scouts_enabled and bool(settings.ai_gateway_api_key), "autoPost": settings.scout_auto_post, "intervalSeconds": settings.scout_interval_seconds, "callsToday": calls_today(session), "dailyCalls": settings.scout_daily_calls, "scouts": scouts, "proposals": feed}
