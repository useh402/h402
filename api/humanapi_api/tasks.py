"""Task service: quotes, payment, creation, answers, completion, expiry, receipts."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ledger
from .config import EXPLORER_TX, Settings
from .consensus import can_still_decide, decide
from .models import (
    Answer,
    Buyer,
    Claim,
    Payment,
    Payout,
    Quote,
    Refund,
    Task,
    TaskEvent,
    Webhook,
    Worker,
    new_id,
    now,
)
from .moderation import classify
from .pricing import TASK_TYPES, TaskRequest, parse_task, quote_task
from .quality import record_outcome
from .states import create_state, transition
from .webhooks import enqueue, new_secret
from .x402 import canonical_hash

logger = logging.getLogger("humanapi.api.tasks")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# -- quotes ------------------------------------------------------------------------------------


def parse_batch(body: dict, batch_max: int) -> list[TaskRequest]:
    items = body.get("tasks")
    if not isinstance(items, list) or not 1 <= len(items) <= batch_max:
        raise ApiError(400, "invalid_request", f"tasks must list 1 to {batch_max} tasks")
    out = []
    for i, item in enumerate(items):
        try:
            out.append(parse_task(item))
        except ValueError as e:
            raise ApiError(400, "invalid_request", f"tasks[{i}]: {e}") from e
    return out


def make_quote(session: Session, settings: Settings, kind: str, body: dict, reqs: list[TaskRequest]) -> Quote:
    body_hash = canonical_hash(body)
    live = session.scalars(select(Quote).where(Quote.body_hash == body_hash, Quote.consumed_by.is_(None), Quote.expires_at > now())).first()
    if live:
        return live
    pool = fee = 0
    for r in reqs:
        q = quote_task(r, settings.platform_fee_bps)
        pool += q["workerPool"]
        fee += q["fee"]
    quote = Quote(id=new_id("qt"), body_hash=body_hash, kind=kind, body=body, total=pool + fee, worker_pool=pool, fee=fee, expires_at=now() + settings.quote_ttl_seconds)
    session.add(quote)
    session.flush()
    return quote


def find_quote(session: Session, body: dict, amount: int) -> Quote | None:
    body_hash = canonical_hash(body)
    return session.scalars(
        select(Quote).where(Quote.body_hash == body_hash, Quote.consumed_by.is_(None), Quote.expires_at > now(), Quote.total == amount).order_by(Quote.created_at.desc())
    ).first()


# -- creation after settlement ----------------------------------------------------------------


def get_or_create_buyer(session: Session, rail: str, payer: str) -> Buyer:
    payer_n = payer.lower() if rail == "robinhood" else payer
    buyer = session.scalars(select(Buyer).where(Buyer.rail == rail, Buyer.payer == payer_n)).first()
    if buyer is None:
        buyer = Buyer(id=new_id("by"), rail=rail, payer=payer_n)
        session.add(buyer)
        session.flush()
    return buyer


def record_payment(session: Session, rail: str, req: dict, settle: dict, quote: Quote) -> Payment:
    existing = session.scalars(select(Payment).where(Payment.network == req["network"], Payment.transaction == settle["transaction"])).first()
    if existing:
        raise ApiError(409, "payment_already_used", f"settlement {settle['transaction']} already funded {existing.id}")
    payer = settle.get("payer") or ""
    if rail == "robinhood":
        payer = payer.lower()
    payment = Payment(
        id=new_id("pay"), rail=rail, network=req["network"], asset=req["asset"], payer=payer, pay_to=req["payTo"], amount=int(req["amount"]), transaction=settle["transaction"], quote_id=quote.id
    )
    session.add(payment)
    session.flush()
    ledger.post(session, rail, "escrow", f"payer:{payment.payer}", payment.amount, payment_id=payment.id, memo="x402 settlement")
    return payment


def create_tasks(session: Session, settings: Settings, reqs: list[TaskRequest], payment: Payment, buyer: Buyer, batch_id: str | None, default_webhook: Webhook | None) -> list[Task]:
    import secrets

    tasks = []
    for r in reqs:
        q = quote_task(r, settings.platform_fee_bps)
        hook_url = (r.webhook or {}).get("url") or (default_webhook.url if default_webhook else None)
        secret = new_secret() if (r.webhook or {}).get("url") else (default_webhook.secret if default_webhook else None)
        listed = is_listed_only(settings, payment)
        task = Task(
            id=new_id("task"),
            batch_id=batch_id,
            buyer_id=buyer.id,
            payment_id=payment.id,
            rail=payment.rail,
            type=r.type,
            title=r.title or "",
            location=r.location or "Remote",
            acceptance=r.acceptance or "",
            difficulty=r.difficulty or "easy",
            effort_minutes=r.effortMinutes or 1,
            template_id=r.templateId,
            reference=r.reference,
            requester=r.requester,
            payload=r.payload,
            price_per_worker=r.pricePerWorker,  # type: ignore[arg-type]
            workers_wanted=r.workers,  # type: ignore[arg-type]
            fee=q["fee"],
            min_reputation=r.minReputation,
            time_limit_seconds=r.timeLimitSeconds,  # type: ignore[arg-type]
            deadline=now() + (r.listSeconds or r.timeLimitSeconds),  # type: ignore[operator]
            state="paid",
            webhook_url=hook_url,
            webhook_secret=secret,
            buyer_token="bt_" + secrets.token_urlsafe(24),
            chain_state="listed" if listed else ("pending" if (settings.escrow_contract and payment.rail == "robinhood") else None),
        )
        session.add(task)
        create_state(session, task)
        session.flush()
        if not listed:
            ledger.post(session, payment.rail, f"payer:{payment.payer}", f"task:{task.id}", q["total"], task_id=task.id, payment_id=payment.id, memo=f"hold for {r.type}")
        if buyer.blocked and buyer.payer != "house":  # the platform's own pool is never blocked by its own rules
            reject_task(session, settings, task, "buyer blocked after repeated rejections")
        else:
            decision, reason = classify(settings, r.type, r.payload)
            if decision == "reject":
                reject_task(session, settings, task, f"moderation: {reason}")
            elif decision == "review" and buyer.payer != "house":  # the pool's own catalogue is written by the operator; only outside clients wait for review
                task.moderation, task.moderation_reason = "review", reason
            else:
                transition(session, task, "open", "routed")
        tasks.append(task)
    buyer.tasks_paid += len(tasks)
    session.flush()
    return tasks


def reject_task(session: Session, settings: Settings, task: Task, reason: str) -> None:
    """Full refund of what is held; a paid or open task goes to rejected, a running one expires."""
    task.moderation = "rejected"
    task.moderation_reason = reason[:200]
    if task.state in ("paid", "open"):
        payment = session.get(Payment, task.payment_id)
        assert payment is not None
        held = task.price_per_worker * task.workers_wanted + task.fee
        _refund(session, task, payment, held, "rejected", reason[:100])
        transition(session, task, "rejected", reason, actor="moderation")
        notify(session, task, "task.rejected")
        buyer = session.get(Buyer, task.buyer_id)
        if buyer and not buyer.blocked and buyer.payer != "house":
            count = len(session.scalars(select(Task.id).where(Task.buyer_id == buyer.id, Task.moderation == "rejected")).all())
            if count >= settings.moderation_block_after:
                buyer.blocked = True
    elif task.state in ("claimed", "submitted"):
        expire(session, settings, task, "rejected while running")


# -- answers and completion -------------------------------------------------------------------


def claim(session: Session, task: Task, worker: Worker) -> Claim:
    if task.state not in ("open", "claimed", "submitted"):
        raise ApiError(409, "not_claimable", f"task is {task.state}")
    if worker.reputation < task.min_reputation or worker.paused:
        raise ApiError(403, "not_qualified", "worker does not meet the task's minimum reputation")
    held = [c for c in session.scalars(select(Claim).where(Claim.task_id == task.id, Claim.released.is_(False))).all() if c.expires_at > now()]
    if any(c.worker_id == worker.id for c in held):
        return next(c for c in held if c.worker_id == worker.id)
    if len(held) >= task.workers_wanted:
        raise ApiError(409, "fully_claimed", "all slots are held")
    hold = task.time_limit_seconds if TASK_TYPES[task.type]["rule"] == "proof" else 120
    # A worker who dropped this task earlier takes it again on their old hold: one hold row per worker and task.
    c = session.scalars(select(Claim).where(Claim.task_id == task.id, Claim.worker_id == worker.id)).first()
    if c is not None:
        c.released, c.claimed_at, c.expires_at = False, now(), min(task.deadline, now() + hold)
    else:
        c = Claim(id=new_id("clm"), task_id=task.id, worker_id=worker.id, expires_at=min(task.deadline, now() + hold))
        session.add(c)
    if task.state == "open":
        transition(session, task, "claimed", "first claim", actor=worker.handle)
    return c


def submit(session: Session, settings: Settings, task: Task, worker: Worker, answer: Any, note: str = "", confidence: float | None = None) -> Task:
    if task.state not in ("open", "claimed", "submitted"):
        raise ApiError(409, "closed", f"task is {task.state}")
    if session.scalars(select(Answer).where(Answer.task_id == task.id, Answer.worker_id == worker.id)).first():
        raise ApiError(409, "already_answered", "this worker already answered")
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id)).all()
    if len(answers) >= task.workers_wanted:
        raise ApiError(409, "full", "enough answers already")
    a = Answer(id=new_id("ans"), task_id=task.id, worker_id=worker.id, answer={"value": answer, "confidence": confidence}, note=note)
    session.add(a)
    for c in session.scalars(select(Claim).where(Claim.task_id == task.id, Claim.worker_id == worker.id)).all():
        if not c.released:
            a.seconds = round(now() - c.claimed_at, 2)
        c.released = True
    session.flush()
    if task.state != "submitted":
        transition(session, task, "submitted", "answer received", actor=worker.handle)
    else:
        session.add(TaskEvent(task_id=task.id, from_state="submitted", to_state="submitted", reason="answer received", actor=worker.handle))
    try_complete(session, settings, task)
    return task


PICTURE_PROOFS = ("photos", "both", "screenshot")

# Set from the settings when the app starts: True means every response of every type waits for the operator.
OPERATOR_DECIDES_ALL = {"on": False}


def operator_decides_all() -> bool:
    return OPERATOR_DECIDES_ALL["on"]


def needs_operator(task: Task) -> bool:
    """Proof with a picture in it is accepted by the operator, never by the clock: a photo or screenshot has to be looked at by a person.
    With the operator deciding everything, every task waits for them."""
    return operator_decides_all() or (task.type == "do" and (task.payload or {}).get("proof", "text") in PICTURE_PROOFS)


def _answer_dicts(answers: list[Answer]) -> list[dict]:
    return [{"answer": a.answer.get("value"), "note": a.note, "confidence": a.answer.get("confidence")} for a in answers]


def try_complete(session: Session, settings: Settings, task: Task, force: bool = False, accept: bool = False, by: str | None = None) -> bool:
    """Compute consensus; on success pay agreeing workers, book the fee, refund unfilled slots.

    Action tasks (`proof` rule) complete only when the client accepts the proof or the acceptance
    window passes (`accept=True`); the deadline without any proof expires them. `by` names who accepted:
    client, operator, assistant or window.
    """
    rule = TASK_TYPES[task.type]["rule"]
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id).order_by(Answer.submitted_at)).all()
    # With the operator deciding everything, a task with answers in it completes only on their word.
    hold = operator_decides_all() and by != "operator"
    if rule == "proof":
        if not answers:
            if force:
                expire(session, settings, task, "no proof submitted")
                return True
            return False
        if not accept or hold:
            return False
        a = answers[0]
        for each in answers:
            each.agrees = True
        task.result = {"proof": a.answer.get("value"), "note": a.note, "acceptedAt": int(now())}
        if len(answers) > 1:
            task.result["proofs"] = [x.answer.get("value") for x in answers]
        task.agreement = 1.0
        task.verification = record("client acceptance", "approved", [
            ("proof submitted", True, f"by one worker, {int(now() - a.submitted_at)}s before acceptance"),
            ("proof format", True, f"matches the requested kind ({(task.payload or {}).get('proof', 'text')})"),
            ("decision", True, _accepted_by(task, by)),
            *_review_check(task),
        ])
        settle_money(session, task, answers)
        transition(session, task, "done", "proof accepted")
        notify(session, task, "task.done")
        return True
    # Every paid slot gets its chance: decide when all wanted answers are in, or at the deadline
    # among the answers that arrived (a lone answer at the deadline is paid: nobody disagreed).
    if len(answers) < task.workers_wanted and not force:
        return False
    # A single written answer waits for the assistant's review when the verifier is on; the deadline is the fallback.
    if rule == "single" and verifier_on(settings) and not accept and not force:
        return False
    wanted = task.workers_wanted if not force else max(1, len(answers))
    decision = decide(rule, _answer_dicts(answers), wanted) if answers else None
    if decision is None:
        if force or not can_still_decide(rule, _answer_dicts(answers), task.workers_wanted):
            if answers and hold:
                return False  # the operator approves whoever is right, or refuses it
            expire(session, settings, task, "no consensus" if answers else "no answers")
            return True
        return False
    if hold:
        return False  # agreement found; the operator confirms it on the admin page before anyone is paid
    result, agreement, flags = decision
    for a, f in zip(answers, flags, strict=False):
        a.agrees = bool(f)
    task.result = result
    task.agreement = round(agreement, 3)
    task.verification = record(f"independent agreement ({rule})", "approved", [
        ("answers received", True, f"{len(answers)} of {task.workers_wanted} wanted" + (" (deadline reached)" if force else "")),
        ("answers valid for the type", True, "every answer matched the task's answer format"),
        ("agreement", True, f"{sum(flags)} of {len(answers)} agree; {task.agreement:.0%}"),
        ("paid", True, f"{sum(flags)} agreeing worker(s) paid, {len(flags) - sum(flags)} not"),
        *_review_check(task),
    ])
    settle_money(session, task, answers)
    transition(session, task, "done", f"consensus {task.agreement}")
    notify(session, task, "task.done")
    return True


def verifier_on(settings: Settings) -> bool:
    return bool(settings.verifier_enabled and settings.ai_gateway_api_key)


def _review_check(task: Task) -> list[tuple[str, bool, str]]:
    r = task.review
    if not r:
        return []
    return [("assistant review", r.get("verdict") == "right", f"{r.get('verdict')}: {r.get('reason', '')}"[:200])]


def _accepted_by(task: Task, by: str | None) -> str:
    if by == "operator":
        return "approved by the operator" + (" after looking at the pictures" if needs_operator(task) else "")
    if by == "assistant" or (by is None and task.review and task.review.get("verdict") == "right"):
        return "approved after the assistant's review"
    if by == "window":
        return "accepted automatically after the window"
    return "accepted by the client" if by == "client" else "accepted by the client or automatically after the window"


def record(method: str, outcome: str, checks: list[tuple[str, bool, str]], by: str = "system") -> dict:
    return {
        "method": method,
        "outcome": outcome,
        "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks],
        "decidedAt": int(now()),
        "by": by,
    }


def settle_money(session: Session, task: Task, answers: list[Answer]) -> None:
    payment = session.get(Payment, task.payment_id)
    assert payment is not None
    held = task.price_per_worker * task.workers_wanted + task.fee
    paid_out = 0
    filled = 0
    for a in answers:
        if a.agrees:
            ledger.post(session, task.rail, f"task:{task.id}", f"worker_due:{a.worker_id}", task.price_per_worker, task_id=task.id, memo="agreed with consensus")
            session.add(Payout(id=new_id("po"), rail=task.rail, worker_id=a.worker_id, task_id=task.id, amount=task.price_per_worker, status="claimable" if (payment.payer == "house" and task.chain_state in ("funded", "pending", "open")) else "queued"))
            a.paid = False
            paid_out += task.price_per_worker
            w = session.get(Worker, a.worker_id)
            if w is not None:
                w.agreed += 1
                record_outcome(w, task.type, True)
        else:
            w = session.get(Worker, a.worker_id)
            if w is not None:
                record_outcome(w, task.type, False)
        filled += 1
    fee_earned = (task.fee * filled + task.workers_wanted - 1) // task.workers_wanted if task.workers_wanted else task.fee
    fee_earned = min(fee_earned, task.fee)
    ledger.post(session, task.rail, f"task:{task.id}", "platform_fee", fee_earned, task_id=task.id, memo="platform fee")
    refund = held - paid_out - fee_earned
    if refund > 0:
        _refund(session, task, payment, refund, "unfilled_slots", "unfilled or disagreeing slots")


def expire(session: Session, settings: Settings, task: Task, reason: str) -> None:
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id)).all()
    # With no consensus nobody is paid; everything held goes back to the payer.
    for a in answers:
        a.agrees = False
    payment = session.get(Payment, task.payment_id)
    assert payment is not None
    held = task.price_per_worker * task.workers_wanted + task.fee
    _refund(session, task, payment, held, reason.replace(" ", "_"), f"expired: {reason}")
    task.result = None
    task.verification = record("independent agreement" if TASK_TYPES[task.type]["rule"] != "proof" else "client acceptance", "inconclusive" if answers else "no_answers", [
        ("answers received", bool(answers), f"{len(answers)} of {task.workers_wanted} wanted"),
        ("agreement", False, reason),
        ("refund", True, "everything held was returned to the client"),
    ])
    transition(session, task, "expired", reason)
    notify(session, task, "task.expired")


def is_listed_only(settings: Settings, payment: Payment) -> bool:
    """Platform tasks are listed without money behind them; the pool funds a task when someone takes it."""
    if payment.payer != "house" or payment.rail != "robinhood":
        return False
    return settings.house_payout == "wallet" or (bool(settings.escrow_contract) and settings.escrow_lock_on_claim)


def fund_listed(session: Session, task: Task, settings: Settings | None = None) -> bool:
    """Draws a listed task's money from the pool at the moment it is taken. False when the pool cannot cover it."""
    payment = session.get(Payment, task.payment_id)
    assert payment is not None
    total = task.price_per_worker * task.workers_wanted + task.fee
    if ledger.balance(session, task.rail, "house") < total:
        return False
    ledger.post(session, task.rail, "house", f"payer:{payment.payer}", total, task_id=task.id, payment_id=payment.id, memo="pool funds the task on take")
    ledger.post(session, task.rail, f"payer:{payment.payer}", f"task:{task.id}", total, task_id=task.id, payment_id=payment.id, memo=f"hold for {task.type}")
    # "funded": the reward is reserved in the books and paid from the wallet on claim. "pending": the contract locks it next.
    task.chain_state = "funded" if (settings is None or settings.house_payout == "wallet") else "pending"
    return True


def _refund(session: Session, task: Task, payment: Payment, amount: int, reason: str, memo: str) -> None:
    """External payers get a refund row paid out on chain; the house gets its money back in the pool."""
    if task.chain_state == "listed":
        return  # nothing was ever held for a task nobody took
    if payment.payer == "house":
        ledger.post(session, task.rail, f"task:{task.id}", "house", amount, task_id=task.id, memo=f"back to the house: {memo}"[:200])
        return
    ledger.post(session, task.rail, f"task:{task.id}", f"refund_due:{payment.payer}", amount, task_id=task.id, memo=memo[:200])
    session.add(Refund(id=new_id("rf"), rail=task.rail, payer=payment.payer, task_id=task.id, amount=amount, reason=reason))


def notify(session: Session, task: Task, event: str) -> None:
    if task.webhook_url and task.webhook_secret:
        body = task_view(session, task)
        if task.webhook_secret.startswith("whbs_"):
            # Buyer-level hooks were registered without a payment proof: state only, never the answer.
            body.pop("result", None)
            body.pop("agreement", None)
        enqueue(session, task.id, task.webhook_url, task.webhook_secret, event, body)


def expire_overdue(session: Session, settings: Settings, limit: int = 200) -> int:
    overdue = session.scalars(select(Task).where(Task.state.in_(("open", "claimed", "submitted")), Task.deadline <= now()).limit(limit)).all()
    n = 0
    for t in overdue:
        if TASK_TYPES[t.type]["rule"] == "proof" and t.state == "submitted":
            continue  # proof is in; the acceptance window decides, not the deadline
        try_complete(session, settings, t, force=True)
        n += 1
    return n


def auto_accept_proofs(session: Session, settings: Settings, limit: int = 200) -> int:
    """Action tasks whose written proof the client neither accepted nor disputed within the window. Pictures wait for the operator."""
    n = 0
    rows = session.scalars(select(Task).where(Task.state == "submitted", Task.type == "do").limit(limit)).all()
    for t in rows:
        if needs_operator(t):
            continue
        a = session.scalars(select(Answer).where(Answer.task_id == t.id)).first()
        if a and now() - a.submitted_at >= TASK_TYPES["do"]["accept_window"]:
            try_complete(session, settings, t, accept=True, by="window")
            n += 1
    return n


def cancel_task(session: Session, settings: Settings, task: Task, reason: str = "") -> dict:
    """The client withdraws a task nobody has answered yet; everything held goes back."""
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id)).all()
    if task.state not in ("paid", "open", "claimed") or answers:
        raise ApiError(409, "not_cancellable", "a task can be cancelled only before anyone has answered")
    payment = session.get(Payment, task.payment_id)
    assert payment is not None
    held = task.price_per_worker * task.workers_wanted + task.fee
    _refund(session, task, payment, held, "cancelled", "cancelled by the client")
    for c in session.scalars(select(Claim).where(Claim.task_id == task.id, Claim.released.is_(False))).all():
        c.released = True
    if task.state == "claimed":
        transition(session, task, "open", "holds released on cancel")
    task.verification = record("none", "cancelled", [("cancelled by the client", True, reason[:200] or "no reason given"), ("refund", True, "everything held was returned")])
    transition(session, task, "cancelled", reason[:200] or "cancelled by the client", actor="buyer")
    notify(session, task, "task.cancelled")
    return task_view(session, task)


def accept_proof(session: Session, settings: Settings, task: Task) -> dict:
    if task.type != "do" or task.state != "submitted":
        raise ApiError(409, "not_acceptable", f"task is {task.state}")
    try_complete(session, settings, task, accept=True, by="client")
    return task_view(session, task)


def reject_proof(session: Session, settings: Settings, task: Task, reason: str) -> dict:
    """The client disputes the proof before accepting it; an admin decides who is right."""
    from .models import Dispute

    if task.type != "do" or task.state != "submitted":
        raise ApiError(409, "not_rejectable", f"task is {task.state}")
    if not reason or len(reason.strip()) < 10:
        raise ApiError(400, "invalid_request", "give a reason of at least 10 characters")
    d = Dispute(id=new_id("dsp"), task_id=task.id, buyer_id=task.buyer_id, reason=reason[:2000])
    session.add(d)
    transition(session, task, "disputed", "client rejected the proof", actor="buyer")
    session.flush()
    return {"disputeId": d.id, "taskId": task.id, "status": "open"}


# -- views -------------------------------------------------------------------------------------


def task_view(session: Session, task: Task, base_url: str = "") -> dict:
    payment = session.get(Payment, task.payment_id)
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id)).all()
    out: dict[str, Any] = {
        "taskId": task.id,
        "batchId": task.batch_id,
        "type": task.type,
        "title": task.title,
        "location": task.location,
        "difficulty": task.difficulty,
        "effortMinutes": task.effort_minutes,
        "templateId": task.template_id,
        "reference": task.reference,
        "requester": task.requester,
        "teamRun": bool(task.team_run),
        "review": task.review,
        "state": task.state,
        "workers": {"wanted": task.workers_wanted, "answered": len(answers)},
        "cost": {"pricePerWorker": task.price_per_worker, "fee": task.fee, "total": task.price_per_worker * task.workers_wanted + task.fee},
        "deadline": int(task.deadline),
        "createdAt": int(task.created_at),
        "completedAt": int(task.completed_at) if task.completed_at else None,
        "resultUrl": f"{base_url}/v1/tasks/{task.id}",
        "receiptUrl": f"{base_url}/v1/receipts/{task.id}",
    }
    if task.chain_state:
        out["escrow"] = {"state": task.chain_state, "openTransaction": task.chain_open_tx, "closeTransaction": task.chain_close_tx}
    if payment:
        out["payment"] = {"network": payment.network, "transaction": payment.transaction, "explorer": EXPLORER_TX.get(payment.network, "{tx}").format(tx=payment.transaction)}
    if task.state == "done":
        out["result"] = task.result
        out["agreement"] = task.agreement
    if task.type == "do" and task.state in ("submitted", "disputed") and answers:
        a = answers[0]
        out["proof"] = {"value": a.answer.get("value"), "note": a.note, "submittedAt": int(a.submitted_at)}
        if needs_operator(task):
            out["awaitingOperator"] = True  # a person looks at the pictures; there is no clock
        else:
            out["acceptBy"] = int(a.submitted_at + TASK_TYPES["do"]["accept_window"])
    if task.moderation != "allowed":
        out["moderation"] = {"status": task.moderation, "reason": task.moderation_reason}
    if task.verification:
        out["verification"] = task.verification
    if task.state in ("expired", "cancelled"):
        out["refund"] = sum(r.amount for r in session.scalars(select(Refund).where(Refund.task_id == task.id)).all())
    return out


def receipt_view(session: Session, task: Task, base_url: str = "") -> dict:
    payment = session.get(Payment, task.payment_id)
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id)).all()
    payouts = session.scalars(select(Payout).where(Payout.task_id == task.id)).all()
    refunds = session.scalars(select(Refund).where(Refund.task_id == task.id)).all()
    events = session.scalars(select(TaskEvent).where(TaskEvent.task_id == task.id).order_by(TaskEvent.id)).all()
    return {
        "taskId": task.id,
        "type": task.type,
        "state": task.state,
        "payment": {
            "network": payment.network if payment else None,
            "transaction": payment.transaction if payment else None,
            "payer": payment.payer if payment else None,
            "amount": payment.amount if payment else None,
            "explorer": EXPLORER_TX.get(payment.network, "{tx}").format(tx=payment.transaction) if payment else None,
        },
        "title": task.title,
        "consensus": {"result": task.result, "agreement": task.agreement, "answers": len(answers), "agreed": sum(1 for a in answers if a.agrees)},
        "verification": task.verification,
        "payouts": [{"worker": p.worker_id, "amount": p.amount, "status": p.status, "ref": p.batch_ref} for p in payouts],
        "refunds": [{"amount": r.amount, "reason": r.reason, "status": r.status, "transaction": r.transaction} for r in refunds],
        "ledger": ledger.entries_for_task(session, task.id),
        "timeline": [{"at": int(e.at), "from": e.from_state, "to": e.to_state, "reason": e.reason} for e in events],
    }
