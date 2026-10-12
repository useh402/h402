"""Local-only automatic workers so the money path can be exercised before the Telegram bot exists."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Answer, Task, Worker, new_id
from .tasks import claim, submit

logger = logging.getLogger("humanapi.api.echo")

CANNED = {
    "verify": lambda p: ("yes", "echo worker: looks right"),
    "choose": lambda p: (0, "echo worker: first option"),
    "rate": lambda p: (4, "echo worker"),
    "read": lambda p: ("ECHO TEXT", ""),
    "label": lambda p: ([p.get("labels", ["none"])[0]], ""),
    "answer": lambda p: ("echo worker answer", ""),
    "do": lambda p: ({"text": "Done as instructed; confirmation page reached."}, ""),
}


def ensure_workers(session: Session, n: int) -> list[Worker]:
    out = []
    for i in range(1, n + 1):
        handle = f"echo-{i}"
        w = session.scalars(select(Worker).where(Worker.handle == handle)).first()
        if w is None:
            w = Worker(id=new_id("wk"), handle=handle, reputation=1.0, tier="gold")
            session.add(w)
            session.flush()
        out.append(w)
    return out


def run_once(session: Session, settings: Settings, limit: int = 50) -> int:
    tasks = session.scalars(select(Task).where(Task.state.in_(("open", "claimed", "submitted"))).limit(limit)).all()
    done = 0
    for t in tasks:
        workers = ensure_workers(session, t.workers_wanted)
        answered = {a.worker_id for a in session.scalars(select(Answer).where(Answer.task_id == t.id)).all()}
        for w in workers:
            if w.id in answered or t.state in ("done", "expired"):
                continue
            try:
                claim(session, t, w)
                value, note = CANNED[t.type](t.payload)
                submit(session, settings, t, w, value, note, confidence=0.9 if t.type == "answer" else None)
            except Exception as e:
                logger.warning("echo worker on %s: %s", t.id, str(e)[:200])
                break
        if t.state == "done":
            done += 1
    return done
