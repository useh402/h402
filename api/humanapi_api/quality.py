"""Reputation, tiers, gold tasks and abuse flags."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ledger
from .config import Settings
from .consensus import _norm
from .models import Answer, GoldResult, GoldTask, Worker, WorkerFlag, new_id, now
from .pricing import TASK_TYPES
from .qualification import SAMPLES

logger = logging.getLogger("humanapi.api.quality")

TIERS = [  # (name, min answered, min reputation, min gold accuracy)
    ("gold", 300, 0.95, 0.95),
    ("silver", 100, 0.85, 0.85),
    ("bronze", 20, 0.70, 0.0),
    ("new", 0, 0.0, 0.0),
]
MIN_SECONDS = {"verify": 2.0, "choose": 2.5, "rate": 2.0, "label": 2.5, "read": 6.0, "answer": 10.0, "do": 30.0}


# -- reputation -----------------------------------------------------------------------------------


def record_outcome(worker: Worker, kind: str, agreed: bool) -> None:
    by = dict(worker.by_type or {})
    entry = dict(by.get(kind, {"answered": 0, "agreed": 0}))
    entry["answered"] += 1
    entry["agreed"] += 1 if agreed else 0
    by[kind] = entry
    worker.by_type = by
    recompute(worker)


def recompute(worker: Worker) -> None:
    answered = sum(v.get("answered", 0) for v in (worker.by_type or {}).values())
    agreed = sum(v.get("agreed", 0) for v in (worker.by_type or {}).values())
    agreement = (agreed + 2) / (answered + 2)  # Laplace: a new worker starts near 1.0 and earns it
    gold = (worker.gold_correct + 1) / (worker.gold_total + 1)
    worker.reputation = round(min(1.0, agreement * (0.5 + 0.5 * gold)), 4)
    gold_acc = worker.gold_correct / worker.gold_total if worker.gold_total else 1.0
    for name, min_answered, min_rep, min_gold in TIERS:
        if answered >= min_answered and worker.reputation >= min_rep and gold_acc >= min_gold:
            worker.tier = name
            break


def reputation_for(worker: Worker, kind: str) -> float:
    entry = (worker.by_type or {}).get(kind)
    if not entry or entry.get("answered", 0) < 5:
        return worker.reputation
    return round((entry["agreed"] + 2) / (entry["answered"] + 2), 4)


# -- gold tasks -----------------------------------------------------------------------------------


def seed_gold(session: Session) -> int:
    """Gold tasks start from the qualification samples; operators add more through the admin API."""
    if session.scalar(select(func.count()).select_from(GoldTask)):
        return 0
    n = 0
    for kind, samples in SAMPLES.items():
        if kind == "do":
            continue
        for s in samples:
            payload = {k: v for k, v in s["payload"].items() if k != "text_preview"}
            if kind == "read":
                payload["text"] = s["payload"].get("text_preview")
            session.add(GoldTask(id=new_id("gold"), type=kind, payload=payload, answer={"value": s["answer"], "tolerance": s.get("tolerance", 0)}, price=TASK_TYPES[kind]["base"]))
            n += 1
    return n


def due_gold(session: Session, settings: Settings, worker: Worker, qualified: list[str]) -> GoldTask | None:
    """A gold task is due every `gold_every` real answers, and never twice in a row."""
    if settings.gold_every <= 0 or not qualified:
        return None
    if (worker.answered + 1) % settings.gold_every != 0:
        return None
    seen = {r.gold_id for r in session.scalars(select(GoldResult).where(GoldResult.worker_id == worker.id)).all()}
    candidates = session.scalars(select(GoldTask).where(GoldTask.active.is_(True), GoldTask.type.in_(qualified))).all()
    fresh = [g for g in candidates if g.id not in seen] or candidates
    if not fresh:
        return None
    # The fee pool pays for gold tasks; without fee income there is no gold.
    if ledger.balance(session, worker.rail, "platform_fee") < max(g.price for g in fresh):
        return None
    return sorted(fresh, key=lambda g: g.id)[hash(worker.id) % len(fresh)]


def gold_card(g: GoldTask) -> dict:
    return {"taskId": g.id, "type": g.type, "price": g.price, "timeLeft": 600, "deadline": int(now()) + 600, "workers": 3, "preview": _preview(g.payload), "held": True, "holdExpiresAt": int(now()) + 120, "payload": g.payload}


def _preview(p: dict) -> str:
    text = str(p.get("question") or p.get("item") or p.get("text") or ("image" if p.get("image") else ""))
    return text[:90] + ("..." if len(text) > 90 else "")


def score_gold(g: GoldTask, value: Any) -> bool:
    want, tol = g.answer.get("value"), g.answer.get("tolerance", 0)
    if g.type == "rate":
        try:
            return abs(float(value) - float(want)) <= tol
        except (TypeError, ValueError):
            return False
    if g.type == "read":
        return re.sub(r"[^a-z0-9]", "", _norm(value)) == re.sub(r"[^a-z0-9]", "", _norm(want))
    return _norm(value) == _norm(want)


def answer_gold(session: Session, settings: Settings, worker: Worker, g: GoldTask, value: Any) -> dict:
    correct = score_gold(g, value)
    session.add(GoldResult(id=new_id("gr"), gold_id=g.id, worker_id=worker.id, answer={"value": value}, correct=correct))
    worker.gold_total += 1
    worker.gold_correct += 1 if correct else 0
    worker.answered += 1
    if correct:
        worker.agreed += 1
        ledger.post(session, worker.rail, "platform_fee", f"worker_due:{worker.id}", g.price, memo=f"gold task {g.id}")
        from .models import Payout

        session.add(Payout(id=new_id("po"), rail=worker.rail, worker_id=worker.id, task_id=None, amount=g.price, kind="bonus"))  # type: ignore[arg-type]
    else:
        flag(session, settings, worker, "gold_wrong", f"gold {g.id}")
        day = now() - 86400
        wrong_today = session.scalar(select(func.count()).select_from(GoldResult).where(GoldResult.worker_id == worker.id, GoldResult.correct.is_(False), GoldResult.at >= day)) or 0
        if wrong_today >= settings.gold_wrong_pause:
            pause(worker, f"{wrong_today} wrong gold answers today")
    recompute(worker)
    return {"taskId": g.id, "state": "done", "accepted": True, "agreed": correct}


# -- abuse flags ----------------------------------------------------------------------------------


def flag(session: Session, settings: Settings, worker: Worker, kind: str, detail: str = "") -> None:
    session.add(WorkerFlag(id=new_id("flag"), worker_id=worker.id, kind=kind, detail=detail[:300]))
    day = now() - 86400
    n = session.scalar(select(func.count()).select_from(WorkerFlag).where(WorkerFlag.worker_id == worker.id, WorkerFlag.at >= day, WorkerFlag.kind != "gold_wrong")) or 0
    if kind != "gold_wrong" and n >= settings.abuse_flags_pause:
        pause(worker, f"{n} abuse flags today ({kind})")


def pause(worker: Worker, reason: str) -> None:
    if not worker.paused:
        worker.paused = True
        worker.paused_reason = reason[:200]
        logger.warning("worker %s paused: %s", worker.id, reason)


def check_answer_behaviour(session: Session, settings: Settings, worker: Worker, kind: str, value: Any, seconds: float | None) -> None:
    if seconds is not None and seconds < MIN_SECONDS.get(kind, 2.0):
        flag(session, settings, worker, "fast_answer", f"{kind} in {seconds:.1f}s")
    minute = now() - 60
    recent = session.scalar(select(func.count()).select_from(Answer).where(Answer.worker_id == worker.id, Answer.submitted_at >= minute)) or 0
    if recent >= 10:
        flag(session, settings, worker, "burst", f"{recent} answers in a minute")
    if kind in ("read", "answer") and isinstance(value, str) and len(value.strip()) >= 8:
        day = now() - 86400
        same = [a for a in session.scalars(select(Answer).where(Answer.worker_id == worker.id, Answer.submitted_at >= day)).all() if _norm(a.answer.get("value")) == _norm(value)]
        if len(same) >= 2:
            flag(session, settings, worker, "duplicate_text", f"{len(same)} identical free-text answers")
