"""Schema v1. Amounts are integers in the asset's atomic unit (6 decimals on both rails)."""

from __future__ import annotations

import time
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def now() -> float:
    return time.time()


class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    payer: Mapped[str] = mapped_column(String(80), index=True)  # address on its rail
    rail: Mapped[str] = mapped_column(String(20))
    reputation: Mapped[float] = mapped_column(Float, default=1.0)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    tasks_paid: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[float] = mapped_column(Float, default=now)
    __table_args__ = (UniqueConstraint("rail", "payer", name="uq_buyer_rail_payer"),)


class ClientSession(Base):
    __tablename__ = "client_sessions"
    token: Mapped[str] = mapped_column(String(80), primary_key=True)
    buyer_id: Mapped[str] = mapped_column(String(40), ForeignKey("buyers.id"), index=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    expires_at: Mapped[float] = mapped_column(Float, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Quote(Base):
    """A priced request waiting for payment. Matched by body hash when the payment arrives."""

    __tablename__ = "quotes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # task | batch
    body: Mapped[dict] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(BigInteger)
    worker_pool: Mapped[int] = mapped_column(BigInteger)
    fee: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    expires_at: Mapped[float] = mapped_column(Float)
    consumed_by: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Payment(Base):
    """One settled x402 payment. Unique per (network, transaction); funds one task or one batch."""

    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rail: Mapped[str] = mapped_column(String(20))
    network: Mapped[str] = mapped_column(String(80))
    asset: Mapped[str] = mapped_column(String(80))
    payer: Mapped[str] = mapped_column(String(80), index=True)
    pay_to: Mapped[str] = mapped_column(String(80))
    amount: Mapped[int] = mapped_column(BigInteger)
    transaction: Mapped[str] = mapped_column(String(140))
    quote_id: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[float] = mapped_column(Float, default=now)
    __table_args__ = (UniqueConstraint("network", "transaction", name="uq_payment_tx"),)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    batch_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    buyer_id: Mapped[str] = mapped_column(String(40), ForeignKey("buyers.id"), index=True)
    payment_id: Mapped[str] = mapped_column(String(40), ForeignKey("payments.id"), index=True)
    rail: Mapped[str] = mapped_column(String(20))
    type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(140), default="")
    location: Mapped[str] = mapped_column(String(80), default="Remote")  # "Remote" or "City, ST"
    acceptance: Mapped[str] = mapped_column(Text, default="")  # what a good answer must contain, shown to the worker
    difficulty: Mapped[str] = mapped_column(String(10), default="easy")  # easy | medium | hard
    effort_minutes: Mapped[int] = mapped_column(Integer, default=2)
    template_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requester: Mapped[str | None] = mapped_column(String(40), nullable=True)  # which assistant the task is for: claude, chatgpt, gemini, grok, deepseek
    verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    team_run: Mapped[bool] = mapped_column(Boolean, default=False)  # done by the platform's own team as a test of the payment path
    chain_state: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)  # None (not on the contract) | pending | open | closed
    chain_open_tx: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Bumped each time the task's lock is released and the task listed again: the contract never reopens a refunded
    # key, so every round locks under a fresh one.
    chain_round: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    chain_close_tx: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the assistant's review of the response: verdict, reason, model, at
    payload: Mapped[dict] = mapped_column(JSON)
    price_per_worker: Mapped[int] = mapped_column(BigInteger)
    workers_wanted: Mapped[int] = mapped_column(Integer)
    fee: Mapped[int] = mapped_column(BigInteger)
    min_reputation: Mapped[float] = mapped_column(Float, default=0.0)
    time_limit_seconds: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[float] = mapped_column(Float, index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(80), nullable=True)
    buyer_token: Mapped[str | None] = mapped_column(String(80), nullable=True)  # authorises dispute for this task
    moderation: Mapped[str] = mapped_column(String(20), default="allowed")  # allowed | review | rejected
    moderation_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)
    completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    purge_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    purged: Mapped[bool] = mapped_column(Boolean, default=False)


class TaskEvent(Base):
    __tablename__ = "task_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    at: Mapped[float] = mapped_column(Float, default=now)
    from_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_state: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(200), default="")
    actor: Mapped[str] = mapped_column(String(60), default="system")


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    handle: Mapped[str] = mapped_column(String(120), unique=True)  # "<rail>:<wallet>"; echo-N locally
    rail: Mapped[str] = mapped_column(String(20), default="")
    wallet: Mapped[str] = mapped_column(String(80), default="")
    reputation: Mapped[float] = mapped_column(Float, default=1.0)
    team: Mapped[bool] = mapped_column(Boolean, default=False)  # a wallet run by the platform's own team
    gas_granted_at: Mapped[float | None] = mapped_column(Float, nullable=True)  # last time we paid for gas so they could withdraw
    tier: Mapped[str] = mapped_column(String(10), default="new")
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[str] = mapped_column(String(80), default="")  # "City, ST" the worker is in
    qualified_types: Mapped[list] = mapped_column(JSON, default=list)
    terms_accepted_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_seen: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    answered: Mapped[int] = mapped_column(Integer, default=0)
    agreed: Mapped[int] = mapped_column(Integer, default=0)
    gold_total: Mapped[int] = mapped_column(Integer, default=0)
    gold_correct: Mapped[int] = mapped_column(Integer, default=0)
    by_type: Mapped[dict] = mapped_column(JSON, default=dict)  # {type: {answered, agreed}}
    paused_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Translation(Base):
    """One string of the site in one language, translated once through the AI gateway and kept."""

    __tablename__ = "translations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), index=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 of the language and the English text
    source: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, index=True)


class Nonce(Base):
    __tablename__ = "nonces"
    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    wallet: Mapped[str] = mapped_column(String(80))
    network: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[float] = mapped_column(Float, index=True)


class WorkerSession(Base):
    __tablename__ = "worker_sessions"
    token: Mapped[str] = mapped_column(String(80), primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    expires_at: Mapped[float] = mapped_column(Float, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    claimed_at: Mapped[float] = mapped_column(Float, default=now)
    expires_at: Mapped[float] = mapped_column(Float)
    released: Mapped[bool] = mapped_column(Boolean, default=False)
    code: Mapped[str | None] = mapped_column(String(8), nullable=True)  # photo tasks: the worker writes this on paper and puts it in the shot
    __table_args__ = (UniqueConstraint("task_id", "worker_id", name="uq_claim_task_worker"),)


class Photo(Base):
    """A proof photo taken for a task. The bytes live in the photo store; this is the record."""

    __tablename__ = "photos"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    claim_id: Mapped[str] = mapped_column(String(40), index=True)
    content_type: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    code: Mapped[str | None] = mapped_column(String(8), nullable=True)  # the capture code expected in the shot
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)  # from the task's place, when it has one
    created_at: Mapped[float] = mapped_column(Float, default=now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    answer: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[float] = mapped_column(Float, default=now)
    seconds: Mapped[float | None] = mapped_column(Float, nullable=True)  # time between claim and answer
    agrees: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("task_id", "worker_id", name="uq_answer_task_worker"),)


class LedgerEntry(Base):
    """Double entry: every posting has a debit account and a credit account on one rail.

    Accounts: escrow (asset held on chain), payer:<addr> (external), task:<id> (held for a task),
    worker_due:<worker>, platform_fee, refund_due:<payer>.
    """

    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[float] = mapped_column(Float, default=now)
    rail: Mapped[str] = mapped_column(String(20), index=True)
    debit: Mapped[str] = mapped_column(String(100), index=True)
    credit: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    payment_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    memo: Mapped[str] = mapped_column(String(200), default="")


class Payout(Base):
    __tablename__ = "payouts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rail: Mapped[str] = mapped_column(String(20))
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("tasks.id"), index=True, nullable=True)  # None for gold tasks
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | sending | sent | failed
    kind: Mapped[str] = mapped_column(String(10), default="task")  # task: the task's own settlement | bonus: paid from the fee pool
    batch_ref: Mapped[str | None] = mapped_column(String(140), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    sent_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rail: Mapped[str] = mapped_column(String(20))
    payer: Mapped[str] = mapped_column(String(80), index=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    kind: Mapped[str] = mapped_column(String(10), default="task")
    transaction: Mapped[str | None] = mapped_column(String(140), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    sent_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    buyer_id: Mapped[str] = mapped_column(String(40), ForeignKey("buyers.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    secret: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), index=True)
    url: Mapped[str] = mapped_column(String(500))
    secret: Mapped[str] = mapped_column(String(80))
    event: Mapped[str] = mapped_column(String(40))
    body: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_at: Mapped[float] = mapped_column(Float, default=now, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | delivered | failed
    last_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class GoldTask(Base):
    __tablename__ = "gold_tasks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    answer: Mapped[dict] = mapped_column(JSON)  # {"value": ..., "tolerance": ...}
    price: Mapped[int] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class GoldResult(Base):
    __tablename__ = "gold_results"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    gold_id: Mapped[str] = mapped_column(String(40), ForeignKey("gold_tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    answer: Mapped[dict] = mapped_column(JSON)
    correct: Mapped[bool] = mapped_column(Boolean)
    at: Mapped[float] = mapped_column(Float, default=now, index=True)


class WorkerFlag(Base):
    __tablename__ = "worker_flags"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # fast_answer | duplicate_text | burst | gold_wrong
    detail: Mapped[str] = mapped_column(String(300), default="")
    at: Mapped[float] = mapped_column(Float, default=now, index=True)


class Dispute(Base):
    __tablename__ = "disputes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(String(40), ForeignKey("buyers.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | upheld | rejected
    outcome_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    refund: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    resolved_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(40), ForeignKey("workers.id"), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | task_rejected | cleared
    created_at: Mapped[float] = mapped_column(Float, default=now)


class ScoutRun(Base):
    __tablename__ = "scout_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    requester: Mapped[str] = mapped_column(String(40), index=True)
    model: Mapped[str] = mapped_column(String(120))
    at: Mapped[float] = mapped_column(Float, default=now, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    proposed: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), ForeignKey("scout_runs.id"), index=True)
    requester: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    raw: Mapped[dict] = mapped_column(JSON)  # what the model returned, untrusted
    body: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the validated task body we would post
    why: Mapped[str] = mapped_column(String(400), default="")
    price: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), index=True)  # review | posted | rejected
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=now, index=True)
    decided_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSON)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=now)


Index("ix_tasks_state_deadline", Task.state, Task.deadline)
