"""Double-entry ledger per rail. Every amount is an atomic-unit integer.

Accounts
  escrow                 the on-chain balance we hold, grows on payment, shrinks on payout/refund
  payer:<addr>           external counterparty for payments and refunds
  task:<id>              funds held for one task until it completes
  worker_due:<worker_id> owed to a worker, cleared by a payout
  platform_fee           earned fees
  refund_due:<addr>      owed back to a payer, cleared by a refund transfer
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import LedgerEntry


def post(session: Session, rail: str, debit: str, credit: str, amount: int, task_id: str | None = None, payment_id: str | None = None, memo: str = "") -> None:
    if amount <= 0:
        return
    session.add(LedgerEntry(rail=rail, debit=debit, credit=credit, amount=amount, task_id=task_id, payment_id=payment_id, memo=memo))


def balance(session: Session, rail: str, account: str) -> int:
    """Debits minus credits for asset accounts (escrow); credits minus debits for liabilities."""
    deb = session.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.rail == rail, LedgerEntry.debit == account)) or 0
    cred = session.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.rail == rail, LedgerEntry.credit == account)) or 0
    if account == "escrow" or (account.startswith("payer:") and account != "payer:house"):
        return int(deb) - int(cred)
    return int(cred) - int(deb)


def liabilities(session: Session, rail: str) -> dict[str, int]:
    """Sum of what escrow owes, grouped by account family."""
    out: dict[str, int] = {"task": 0, "worker_due": 0, "platform_fee": 0, "refund_due": 0, "house": 0, "payer": 0}
    rows = session.execute(
        select(LedgerEntry.credit, func.sum(LedgerEntry.amount)).where(LedgerEntry.rail == rail).group_by(LedgerEntry.credit)
    ).all()
    debits = dict(
        session.execute(
            select(LedgerEntry.debit, func.sum(LedgerEntry.amount)).where(LedgerEntry.rail == rail).group_by(LedgerEntry.debit)
        ).all()
    )
    for account, credited in rows:
        family = account.split(":")[0]
        if family == "payer" and account != "payer:house":
            continue  # external payers are not liabilities; the house flow-through account is
        if family in out:
            out[family] += int(credited) - int(debits.get(account, 0))
    return out


def check_invariant(session: Session, rail: str) -> dict:
    """escrow == every liability. True by construction unless a posting bypassed this module."""
    esc = balance(session, rail, "escrow")
    liab = liabilities(session, rail)
    total = sum(liab.values())
    return {"rail": rail, "escrow": esc, "liabilities": liab, "liabilitiesTotal": total, "balanced": esc == total}


def entries_for_task(session: Session, task_id: str) -> list[dict]:
    rows = session.scalars(select(LedgerEntry).where(LedgerEntry.task_id == task_id).order_by(LedgerEntry.id)).all()
    return [{"at": r.at, "debit": r.debit, "credit": r.credit, "amount": r.amount, "memo": r.memo} for r in rows]
