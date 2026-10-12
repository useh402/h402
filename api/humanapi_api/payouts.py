"""Batched payouts and refunds from each rail's escrow wallet.

Rows start `queued`; a round groups them per rail, signs a transfer, records the transaction id as
`sending` before broadcasting, then marks `sent` or `failed`. Ledger: a payout debits worker_due and
credits escrow; a refund debits refund_due and credits escrow. Recovery on start resolves `sending`
rows from the chain.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ledger
from .config import Settings
from .models import Payout, Refund, Worker, now

logger = logging.getLogger("humanapi.api.payouts")


class Sender(Protocol):
    """One per rail. `prepare` signs and returns the transaction id; `broadcast` sends it; `status` reads the chain."""

    rail: str

    def prepare(self, transfers: list[tuple[str, int]]) -> tuple[str, object]: ...
    def broadcast(self, prepared: object) -> None: ...
    def status(self, tx: str) -> str: ...  # sent | failed | unknown
    def max_per_tx(self) -> int: ...


def run_round(session: Session, settings: Settings, senders: dict[str, Sender]) -> dict:
    out = {"payouts": 0, "refunds": 0, "transactions": 0, "failed": 0}
    for rail, sender in senders.items():
        budget = settings.payout_round_cap
        # Group queued payouts per worker wallet so one worker gets one transfer per round.
        payouts = session.scalars(select(Payout).where(Payout.rail == rail, Payout.status == "queued").order_by(Payout.created_at)).all()
        by_wallet: dict[str, list[Payout]] = defaultdict(list)
        payouts = [p for p in payouts if not _on_contract(session, p)]
        for p in payouts:
            w = session.get(Worker, p.worker_id)
            if w and w.wallet:
                by_wallet[w.wallet].append(p)
        transfers: list[tuple[str, int, list[Payout]]] = []
        for wallet, rows in by_wallet.items():
            total = sum(r.amount for r in rows)
            if total < settings.payout_min_amount or total > budget:
                continue
            transfers.append((wallet, total, rows))
            budget -= total
        refunds = session.scalars(select(Refund).where(Refund.rail == rail, Refund.status == "queued").order_by(Refund.created_at)).all()
        refund_transfers: list[tuple[str, int, Refund]] = []
        refunds = [r for r in refunds if not _on_contract(session, r)]
        for r in refunds:
            if r.amount > budget:
                continue
            refund_transfers.append((r.payer, r.amount, r))
            budget -= r.amount

        items: list[tuple[str, int, object]] = [(w, a, rows) for w, a, rows in transfers] + [(p, a, r) for p, a, r in refund_transfers]
        size = max(1, sender.max_per_tx())
        for i in range(0, len(items), size):
            chunk = items[i : i + size]
            try:
                tx, prepared = sender.prepare([(to, amount) for to, amount, _ in chunk])
            except Exception as e:
                logger.error("prepare failed on %s: %s", rail, str(e)[:300])
                out["failed"] += len(chunk)
                continue
            for _, _, ref in chunk:
                _mark(ref, "sending", tx)
            session.flush()
            try:
                sender.broadcast(prepared)
                ok = _wait(sender, tx)
            except Exception as e:
                logger.error("broadcast failed on %s: %s", rail, str(e)[:300])
                ok = False
            for to, amount, ref in chunk:
                if ok:
                    _mark(ref, "sent", tx, settled_at=now())
                    _post(session, rail, ref, to, amount, tx)
                    if isinstance(ref, Refund):
                        out["refunds"] += 1
                    else:
                        out["payouts"] += len(ref)
                else:
                    _mark(ref, "failed", tx)
                    out["failed"] += 1
            out["transactions"] += 1
            session.flush()
    return out


def _on_contract(session: Session, row) -> bool:
    """A task's own settlement is paid by the escrow contract when the task lives there; this job leaves it alone."""
    if row.kind != "task" or not row.task_id:
        return False
    from .models import Task

    t = session.get(Task, row.task_id)
    return t is not None and t.chain_state is not None


def _mark(ref: object, status: str, tx: str, settled_at: float | None = None) -> None:
    rows = ref if isinstance(ref, list) else [ref]
    for r in rows:
        r.status = status
        if isinstance(r, Payout):
            r.batch_ref = tx
        else:
            r.transaction = tx
        if status in ("sending",):
            r.attempts += 1
        if settled_at:
            r.sent_at = settled_at
        if status == "failed" and r.attempts < 5:
            r.status = "queued"  # retried next round


def _post(session: Session, rail: str, ref: object, to: str, amount: int, tx: str) -> None:
    if isinstance(ref, Refund):
        ledger.post(session, rail, f"refund_due:{ref.payer}", "escrow", amount, task_id=ref.task_id, memo=f"refund {tx}")
        return
    for p in ref:  # type: ignore[union-attr]
        ledger.post(session, rail, f"worker_due:{p.worker_id}", "escrow", p.amount, task_id=p.task_id, memo=f"payout {tx}")


def _wait(sender: Sender, tx: str, timeout: float = 120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = sender.status(tx)
        if st == "sent":
            return True
        if st == "failed":
            return False
        time.sleep(2)
    return False


def recover(session: Session, senders: dict[str, Sender]) -> int:
    """Resolve rows left in `sending` by asking the chain."""
    n = 0
    for model in (Payout, Refund):
        for row in session.scalars(select(model).where(model.status == "sending")).all():
            sender = senders.get(row.rail)
            tx = row.batch_ref if isinstance(row, Payout) else row.transaction
            if sender is None or not tx:
                continue
            st = sender.status(tx)
            if st == "unknown" and now() - row.created_at < 600:
                continue
            if st == "sent":
                row.status, row.sent_at = "sent", now()
                to = session.get(Worker, row.worker_id).wallet if isinstance(row, Payout) else row.payer
                _post(session, row.rail, [row] if isinstance(row, Payout) else row, to, row.amount, tx)
            else:
                _mark(row, "failed", tx)
            n += 1
    return n
