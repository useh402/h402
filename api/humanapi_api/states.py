"""The task state machine. Nothing else writes Task.state."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Task, TaskEvent, now

TRANSITIONS: dict[str, set[str]] = {
    "paid": {"open", "rejected", "cancelled"},
    "open": {"claimed", "expired", "rejected", "cancelled"},
    "claimed": {"open", "submitted", "expired"},
    "submitted": {"done", "expired", "claimed", "disputed"},
    "done": {"disputed"},
    "disputed": {"done", "expired"},
    "expired": set(),
    "rejected": set(),
    "cancelled": set(),
}
TERMINAL = {"done", "expired", "rejected", "cancelled"}


class IllegalTransition(Exception):
    pass


def transition(session: Session, task: Task, to: str, reason: str = "", actor: str = "system") -> None:
    if to not in TRANSITIONS.get(task.state, set()):
        raise IllegalTransition(f"{task.id}: {task.state} -> {to} is not allowed")
    session.add(TaskEvent(task_id=task.id, from_state=task.state, to_state=to, reason=reason, actor=actor))
    task.state = to
    task.updated_at = now()
    if to in TERMINAL:
        task.completed_at = now()
        task.purge_after = now() + 30 * 86400


def create_state(session: Session, task: Task, reason: str = "payment settled") -> None:
    task.state = "paid"
    session.add(TaskEvent(task_id=task.id, from_state=None, to_state="paid", reason=reason))
