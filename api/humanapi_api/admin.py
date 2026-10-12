"""Admin surface: every response for the operator to approve, review queue, disputes, reports, gold tasks, worker pauses, retention sweep."""

from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ledger
from .config import Settings
from .models import Answer, Dispute, GoldTask, Payment, Photo, Refund, Report, Task, Worker, new_id, now
from .states import transition
from .tasks import ApiError, needs_operator, operator_decides_all, reject_task, task_view


def new_buyer_token() -> str:
    return "bt_" + secrets.token_urlsafe(24)


# -- moderation review ----------------------------------------------------------------------------


def review_queue(session: Session, base: str) -> list[dict]:
    rows = session.scalars(select(Task).where(Task.moderation == "review").order_by(Task.created_at)).all()
    return [{**task_view(session, t, base), "payload": t.payload, "moderationReason": t.moderation_reason} for t in rows]


def decide_review(session: Session, settings: Settings, task: Task, decision: str, note: str = "") -> dict:
    if task.moderation != "review":
        raise ApiError(409, "not_in_review", f"task moderation is {task.moderation}")
    if decision == "approve":
        task.moderation = "allowed"
        task.moderation_reason = f"approved: {note}"[:200]
        if task.state == "paid":
            transition(session, task, "open", "approved after review", actor="admin")
        for r in session.scalars(select(Report).where(Report.task_id == task.id, Report.status == "open")).all():
            r.status = "cleared"
    elif decision == "reject":
        reject_task(session, settings, task, f"rejected after review: {note}")
        for r in session.scalars(select(Report).where(Report.task_id == task.id, Report.status == "open")).all():
            r.status = "task_rejected"
    else:
        raise ApiError(400, "invalid_request", "decision must be approve or reject")
    return task_view(session, task)


# -- disputes -------------------------------------------------------------------------------------


def open_dispute(session: Session, settings: Settings, task: Task, token: str, reason: str) -> dict:
    if not task.buyer_token or not secrets.compare_digest(task.buyer_token, token or ""):
        raise ApiError(403, "forbidden", "a valid buyerToken for this task is required")
    if task.state != "done":
        raise ApiError(409, "not_disputable", f"task is {task.state}")
    if task.completed_at and now() - task.completed_at > settings.dispute_window_seconds:
        raise ApiError(409, "window_closed", "disputes must be opened within 24 hours of completion")
    if not reason or len(reason) < 10:
        raise ApiError(400, "invalid_request", "give a reason of at least 10 characters")
    d = Dispute(id=new_id("dsp"), task_id=task.id, buyer_id=task.buyer_id, reason=reason[:2000])
    session.add(d)
    transition(session, task, "disputed", "buyer dispute", actor="buyer")
    session.flush()
    return {"disputeId": d.id, "taskId": task.id, "status": d.status}


def resolve_dispute(session: Session, settings: Settings, dispute: Dispute, outcome: str, note: str = "") -> dict:
    if dispute.status != "open":
        raise ApiError(409, "resolved", "already resolved")
    task = session.get(Task, dispute.task_id)
    assert task is not None
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id)).all()
    proof_stage = task.type in ("do", "answer") and task.state == "disputed" and all(a.agrees is None for a in answers)
    if proof_stage:
        # The proof was never accepted: upheld means the worker is not paid and the client is refunded in full;
        # rejected means the proof stands and the worker is paid.
        from .tasks import try_complete

        dispute.status, dispute.outcome_note, dispute.resolved_at = outcome, note[:300], now()
        if outcome == "upheld":
            refuse_work(session, settings, task, answers)
            dispute.refund = task.price_per_worker * task.workers_wanted + task.fee
        elif outcome == "rejected":
            try_complete(session, settings, task, accept=True, by="operator")
        else:
            raise ApiError(400, "invalid_request", "outcome must be upheld or rejected")
        return {"disputeId": dispute.id, "status": dispute.status, "refund": dispute.refund}
    if outcome == "upheld":
        # Workers keep their pay; the buyer is made whole from the fee pool, up to what they paid.
        payment = session.get(Payment, task.payment_id)
        refund = task.price_per_worker * task.workers_wanted + task.fee
        pool = ledger.balance(session, task.rail, "platform_fee")
        refund = min(refund, max(pool, 0))
        if refund > 0:
            ledger.post(session, task.rail, "platform_fee", f"refund_due:{payment.payer}", refund, task_id=task.id, memo=f"dispute {dispute.id} upheld")
            session.add(Refund(id=new_id("rf"), rail=task.rail, payer=payment.payer, task_id=task.id, amount=refund, reason="dispute_upheld", kind="bonus"))
        dispute.refund = refund
        for a in session.scalars(select(Answer).where(Answer.task_id == task.id)).all():
            w = session.get(Worker, a.worker_id)
            if w and a.agrees:
                from .quality import record_outcome

                record_outcome(w, task.type, False)
    elif outcome != "rejected":
        raise ApiError(400, "invalid_request", "outcome must be upheld or rejected")
    dispute.status = outcome
    dispute.outcome_note = note[:300]
    dispute.resolved_at = now()
    transition(session, task, "done", f"dispute {outcome}", actor="admin")
    return {"disputeId": dispute.id, "status": dispute.status, "refund": dispute.refund}


def refuse_work(session: Session, settings: Settings, task: Task, answers: list[Answer], reason: str = "proof rejected") -> None:
    """A response that was never accepted is refused: nobody is paid, the money goes back, the workers' records take a miss."""
    from .quality import record_outcome
    from .tasks import expire

    for a in answers:
        w = session.get(Worker, a.worker_id)
        if w:
            record_outcome(w, task.type, False)
    expire(session, settings, task, reason)


# -- unclaimed rewards: approved pay nobody has collected ------------------------------------------


def unclaimed_rewards(session: Session) -> list[dict]:
    """Tasks the operator approved whose reward is still waiting for the worker's Claim, oldest first."""
    from .models import Payout

    rows = session.execute(select(Payout, Task).join(Task, Task.id == Payout.task_id).where(Payout.status == "claimable", Payout.kind == "task")).all()
    by: dict[str, dict] = {}
    for po, t in rows:
        d = by.setdefault(t.id, {"taskId": t.id, "title": t.title, "type": t.type, "amount": 0, "workers": 0, "approvedAt": int(t.completed_at or t.updated_at or 0), "chainState": t.chain_state, "locked": t.chain_state in ("pending", "open")})
        d["amount"] += po.amount
        d["workers"] += 1
    return sorted(by.values(), key=lambda d: d["approvedAt"])


def void_reward(session: Session, task: Task, reason: str, transaction: str | None) -> dict:
    """The operator takes back an approved reward nobody claimed: the money returns to the pool's books, the payout is
    marked voided so the worker sees why, and the contract refund (already sent, if the task was open there) is recorded."""
    from .models import Payout

    payouts = session.scalars(select(Payout).where(Payout.task_id == task.id, Payout.kind == "task", Payout.status == "claimable")).all()
    if not payouts:
        raise ApiError(409, "nothing_to_void", "this task has no unclaimed reward")
    if task.chain_state in ("pending", "open"):
        task.chain_state = "closed"
        task.chain_close_tx = transaction or task.chain_close_tx
    total = 0
    for po in payouts:
        po.status, po.batch_ref, po.sent_at = "voided", transaction or "voided", now()
        ledger.post(session, task.rail, f"worker_due:{po.worker_id}", "house", po.amount, task_id=task.id, memo=f"reward voided by the operator: {reason}"[:200])
        total += po.amount
    task.verification = {**(task.verification or {}), "rewardVoided": {"at": int(now()), "amount": total, "reason": reason[:300], "transaction": transaction}}
    return {"taskId": task.id, "amount": total, "workers": len(payouts), "transaction": transaction}


# -- responses: everything people sent back, for the operator ------------------------------------


def _decision_of(task: Task, answer: Answer, dispute: Dispute | None, answered: int | None = None) -> str:
    if task.state == "done":
        return "approved" if answer.agrees else "not_paid"
    if task.state in ("expired", "cancelled", "rejected"):
        return "refused"
    if task.state == "disputed" or dispute is not None:
        return "disputed"
    if task.state == "submitted":
        if task.type in ("do", "answer"):
            return "waiting"
        # A consensus task waits for the operator once every wanted answer is in, or the deadline has passed.
        if operator_decides_all() and ((answered or 0) >= task.workers_wanted or task.deadline <= now()):
            return "waiting"
    return "open"  # a consensus task still collecting answers


def responses(session: Session, base: str, status: str = "all", limit: int = 100) -> list[dict]:
    """Every answer on the platform, newest first, with the pictures: the operator's view of what people actually sent."""
    from .catalogue import CATEGORIES

    rows = session.execute(select(Answer, Task).join(Task, Task.id == Answer.task_id).order_by(Answer.submitted_at.desc()).limit(max(limit * 4, 200))).all()
    disputes = {d.task_id: d for d in session.scalars(select(Dispute).where(Dispute.status == "open")).all()}
    answered = {tid: int(n) for tid, n in session.execute(select(Answer.task_id, func.count()).where(Answer.task_id.in_({t.id for _, t in rows})).group_by(Answer.task_id)).all()} if rows else {}
    out: list[dict] = []
    for a, t in rows:
        decision = _decision_of(t, a, disputes.get(t.id), answered.get(t.id))
        if status == "waiting" and decision not in ("waiting", "disputed"):
            continue
        if status not in ("all", "waiting") and decision != status:
            continue
        w = session.get(Worker, a.worker_id)
        payload = t.payload or {}
        value = a.answer.get("value")
        text = value.get("text") if isinstance(value, dict) else value
        photos = []
        if isinstance(value, dict) and isinstance(value.get("photos"), list):
            for pid in value["photos"]:
                ph = session.get(Photo, pid)
                if ph is None or ph.deleted:
                    photos.append({"photoId": pid, "url": None, "expired": True})
                else:
                    photos.append({"photoId": ph.id, "url": f"{base}/v1/photos/{ph.id}", "distanceM": int(ph.distance_m) if ph.distance_m is not None else None, "accuracyM": int(ph.accuracy_m) if ph.accuracy_m is not None else None, "takenAt": int(ph.created_at)})
        cat = payload.get("category") if isinstance(payload, dict) else None
        d = disputes.get(t.id)
        out.append({
            "taskId": t.id,
            "title": t.title,
            "type": t.type,
            "category": cat,
            "categoryLabel": CATEGORIES.get(cat, {}).get("label") if cat else None,
            "location": t.location,
            "price": t.price_per_worker,
            "state": t.state,
            "proofKind": payload.get("proof", "text") if t.type == "do" else None,
            "awaitingOperator": needs_operator(t) and t.state in ("submitted", "disputed"),
            "instructions": payload.get("instructions") or payload.get("question") or payload.get("text") or "",
            "options": payload.get("options") if isinstance(payload.get("options"), list) else None,
            "write": payload.get("write"),
            "acceptance": t.acceptance,
            "worker": {"id": a.worker_id, "wallet": w.wallet if w else "", "reputation": w.reputation if w else None, "team": bool(w.team) if w else False},
            "answerId": a.id,
            "submittedAt": int(a.submitted_at),
            "seconds": a.seconds,
            "value": value,
            "text": text if isinstance(text, str) else None,
            "screenshot": value.get("screenshot") if isinstance(value, dict) and isinstance(value.get("screenshot"), str) else None,
            "photos": photos,
            "code": value.get("code") if isinstance(value, dict) else None,
            "note": a.note,
            "confidence": a.answer.get("confidence"),
            "review": t.review,
            "decision": decision,
            "paid": bool(a.paid),
            "dispute": {"disputeId": d.id, "reason": d.reason} if d else None,
        })
        if len(out) >= limit:
            break
    return out


def decide_response(session: Session, settings: Settings, task: Task, decision: str, note: str = "") -> dict:
    """The operator approves a response (the worker is paid) or refuses it (nobody is paid, the money goes back)."""
    from .pricing import TASK_TYPES
    from .tasks import try_complete

    if decision not in ("approve", "refuse", "reject"):
        raise ApiError(400, "invalid_request", "decision must be approve or refuse")
    consensus = TASK_TYPES[task.type]["rule"] != "proof" and task.type != "answer"
    if consensus and not operator_decides_all():
        raise ApiError(409, "not_decidable", "only action tasks and written answers are decided by hand; close a consensus task instead")
    answers = session.scalars(select(Answer).where(Answer.task_id == task.id).order_by(Answer.submitted_at)).all()
    if not answers:
        raise ApiError(409, "no_answers", "nobody has answered yet")
    d = session.scalars(select(Dispute).where(Dispute.task_id == task.id, Dispute.status == "open")).first()
    if d is not None:
        resolve_dispute(session, settings, d, "rejected" if decision == "approve" else "upheld", note or f"operator: {decision}")
    elif task.state == "submitted":
        if decision == "approve":
            # A consensus task is decided among the answers that are in: the agreeing ones are paid.
            if not try_complete(session, settings, task, accept=True, force=consensus, by="operator"):
                raise ApiError(409, "not_ready", "the task is still waiting for another answer")
        else:
            refuse_work(session, settings, task, answers, "refused by the operator")
    else:
        raise ApiError(409, "already_decided", f"task is {task.state}")
    if note:
        task.verification = {**(task.verification or {}), "operatorNote": note[:300]}
    return {"taskId": task.id, "state": task.state, "decision": "approved" if decision == "approve" else "refused"}


# -- reports --------------------------------------------------------------------------------------


def report_task(session: Session, settings: Settings, task: Task, worker: Worker, reason: str) -> dict:
    if session.scalars(select(Report).where(Report.task_id == task.id, Report.worker_id == worker.id)).first():
        raise ApiError(409, "already_reported", "you already reported this task")
    r = Report(id=new_id("rep"), task_id=task.id, worker_id=worker.id, reason=(reason or "no reason given")[:300])
    session.add(r)
    if task.moderation == "allowed" and task.state not in ("done", "expired", "rejected"):
        task.moderation = "review"
        task.moderation_reason = f"reported: {r.reason}"[:200]
    # The reporter is paid for their time from the fee pool, once per task.
    if ledger.balance(session, task.rail, "platform_fee") >= task.price_per_worker:
        ledger.post(session, task.rail, "platform_fee", f"worker_due:{worker.id}", task.price_per_worker, task_id=task.id, memo="report credit")
        from .models import Payout

        session.add(Payout(id=new_id("po"), rail=task.rail, worker_id=worker.id, task_id=task.id, amount=task.price_per_worker, kind="bonus"))
    from .workers import release

    release(session, worker, task.id)  # gives the slot back; the task reopens if nobody else holds it
    return {"reportId": r.id, "taskId": task.id, "status": "received"}


# -- retention ------------------------------------------------------------------------------------


def purge_expired(session: Session, limit: int = 200, store=None) -> int:
    from .models import Photo

    rows = session.scalars(select(Task).where(Task.purged.is_(False), Task.purge_after.is_not(None), Task.purge_after <= now()).limit(limit)).all()
    for t in rows:
        for ph in session.query(Photo).filter(Photo.task_id == t.id, Photo.deleted.is_(False)).all():
            ph.deleted = True
            if store is not None:
                try:
                    store.delete(ph.id)
                except Exception:
                    pass
        t.payload = {"purged": True}
        t.purged = True
        for a in session.scalars(select(Answer).where(Answer.task_id == t.id)).all():
            if isinstance(a.answer.get("value"), str):
                a.answer = {**a.answer, "value": "[purged]"}
            a.note = ""
    return len(rows)


# -- gold management --------------------------------------------------------------------------------


def add_gold(session: Session, kind: str, payload: dict, answer, tolerance: float = 0, price: int | None = None) -> GoldTask:
    from .pricing import TASK_TYPES, validate_payload

    if kind not in TASK_TYPES:
        raise ApiError(400, "invalid_request", "unknown type")
    validate_payload(kind, payload)
    g = GoldTask(id=new_id("gold"), type=kind, payload=payload, answer={"value": answer, "tolerance": tolerance}, price=price or TASK_TYPES[kind]["base"])
    session.add(g)
    session.flush()
    return g
