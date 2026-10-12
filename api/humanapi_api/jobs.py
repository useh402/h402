"""Background loop: deadline expiry, webhook delivery, the echo worker, quote and idempotency cleanup."""

from __future__ import annotations

import logging
import threading
import time

import httpx
from sqlalchemy import delete

from .config import Settings
from .db import Database
from .models import IdempotencyKey, Quote, now
from .tasks import auto_accept_proofs, expire_overdue
from .webhooks import deliver_due
from .workers import expire_holds

logger = logging.getLogger("humanapi.api.jobs")


class Jobs:
    def __init__(self, settings: Settings, db: Database, http: httpx.Client | None = None, senders: dict | None = None):
        self.settings = settings
        self.db = db
        self.http = http or httpx.Client()
        self.senders = senders or {}
        self.last_payout_round = 0.0
        self.last_house_round = 0.0
        self.last_scout_round = time.time()  # the first scheduled search is one interval after start, not at start
        self.scout_http: httpx.Client | None = None
        self.scout_lock = threading.Lock()
        self.verifier_lock = threading.Lock()
        self.chain = None  # the escrow contract client, when the contract is configured
        self.store = None  # where proof photos are kept
        self.reward_sender = None  # sends rewards from the operator wallet when a worker claims
        self.chain_lock = threading.Lock()
        self.chain_thread: threading.Thread | None = None
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def tick(self) -> dict:
        out = {"expired": 0, "webhooks": 0, "echo": 0, "holds": 0}
        with self.db.session() as s:
            out["holds"] = expire_holds(s)
            out["expired"] = expire_overdue(s, self.settings)
            out["accepted"] = auto_accept_proofs(s, self.settings)
        with self.db.session() as s:
            from .admin import purge_expired

            out["purged"] = purge_expired(s, store=self.store)
        if self.settings.echo_worker:
            from .echo_worker import run_once

            with self.db.session() as s:
                out["echo"] = run_once(s, self.settings)
        with self.db.session() as s:
            out["webhooks"] = deliver_due(s, self.http, self.settings.webhook_max_attempts)
        with self.db.session() as s:
            s.execute(delete(Quote).where(Quote.expires_at < now() - 3600))
            s.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < now() - self.settings.idempotency_ttl_seconds))
        if self.senders and time.time() - self.last_payout_round >= self.settings.payout_interval_seconds:
            out["payouts"] = self.payout_round()
        if self.settings.house_poster_enabled and time.time() - self.last_house_round >= self.settings.house_interval_seconds:
            out["house"] = self.house_round()
        if self.settings.verifier_enabled and self.settings.ai_gateway_api_key:
            out["reviewed"] = self.verifier_round()
        if self.settings.scouts_enabled and self.settings.ai_gateway_api_key and time.time() - self.last_scout_round >= self.settings.scout_interval_seconds:
            out["scouts"] = self.scout_round()
        return out

    def chain_round(self) -> dict:
        from .escrow_chain import sync

        if self.chain is None:
            return {"skipped": "no escrow contract"}
        if not self.chain_lock.acquire(blocking=False):
            return {"skipped": "a settlement run is already in progress"}
        try:
            return sync(self.db, self.settings, self.chain, sender=self.reward_sender)
        finally:
            self.chain_lock.release()

    def _chain_loop(self) -> None:
        # Its own thread: waiting for transactions must not hold up deadlines and webhooks.
        while not self.stop.wait(4.0):
            try:
                self.chain_round()
            except Exception as e:
                logger.warning("escrow loop failed: %s", str(e)[:300])

    def verifier_round(self) -> dict:
        from .verifier import run as verifier_run

        if not self.verifier_lock.acquire(blocking=False):
            return {"reviewed": 0, "skipped": "a review is already running"}
        try:
            return verifier_run(self.db, self.settings, self.scout_http or httpx.Client(), store=self.store)
        finally:
            self.verifier_lock.release()

    def scout_round(self) -> dict:
        from .scouts import run_round

        if not self.scout_lock.acquire(blocking=False):
            return {"runs": 0, "proposed": 0, "skipped": "a search is already running"}
        try:
            self.last_scout_round = time.time()
            return run_round(self.db, self.settings, self.scout_http or httpx.Client())
        finally:
            self.last_scout_round = time.time()
            self.scout_lock.release()

    def house_round(self) -> dict:
        from .house import round_

        self.last_house_round = time.time()
        with self.db.session() as s:
            return round_(s, self.settings)

    def payout_round(self) -> dict:
        from .payouts import run_round

        self.last_payout_round = time.time()
        with self.db.session() as s:
            return run_round(s, self.settings, self.senders)

    def recover_payouts(self) -> int:
        from .payouts import recover

        with self.db.session() as s:
            return recover(s, self.senders)

    def _loop(self) -> None:
        while not self.stop.wait(2.0):
            try:
                self.tick()
            except Exception as e:
                logger.warning("jobs tick failed: %s", str(e)[:300])

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, name="jobs", daemon=True)
        self.thread.start()
        if self.chain is not None:
            self.chain_thread = threading.Thread(target=self._chain_loop, name="escrow", daemon=True)
            self.chain_thread.start()

    def shutdown(self) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)

