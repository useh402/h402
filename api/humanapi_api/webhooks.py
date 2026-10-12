"""Signed webhook deliveries with retries. Signature: HMAC-SHA256 of the raw body, hex, in X-H402-Signature."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import WebhookDelivery, new_id

logger = logging.getLogger("humanapi.api.webhooks")


def new_secret() -> str:
    return "whsec_" + secrets.token_hex(24)


def sign(secret: str, body: bytes, ts: str) -> str:
    return hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()


def enqueue(session: Session, task_id: str, url: str, secret: str, event: str, body: dict) -> None:
    session.add(WebhookDelivery(id=new_id("whd"), task_id=task_id, url=url, secret=secret, event=event, body=body))


def deliver_due(session: Session, http: httpx.Client, max_attempts: int, limit: int = 50) -> int:
    now = time.time()
    due = session.scalars(
        select(WebhookDelivery).where(WebhookDelivery.status == "pending", WebhookDelivery.next_at <= now).order_by(WebhookDelivery.next_at).limit(limit)
    ).all()
    sent = 0
    for d in due:
        raw = json.dumps({"event": d.event, "taskId": d.task_id, "data": d.body, "sentAt": int(now)}, separators=(",", ":")).encode()
        ts = str(int(now))
        headers = {
            "Content-Type": "application/json",
            "X-H402-Event": d.event,
            "X-H402-Timestamp": ts,
            "X-H402-Signature": sign(d.secret, raw, ts),
            "X-H402-Delivery": d.id,
        }
        d.attempts += 1
        try:
            r = http.post(d.url, content=raw, headers=headers, timeout=10)
            d.last_status = r.status_code
            if 200 <= r.status_code < 300:
                d.status = "delivered"
                sent += 1
                continue
            d.last_error = f"http {r.status_code}"
        except Exception as e:
            d.last_error = f"{type(e).__name__}: {str(e)[:200]}"
        if d.attempts >= max_attempts:
            d.status = "failed"
        else:
            d.next_at = now + min(3600, 5 * 2 ** (d.attempts - 1))
    return sent


def verify_signature(secret: str, body: bytes, ts: str, signature: str, tolerance: int = 300) -> bool:
    """For buyers: how to check a delivery. Also used by the tests."""
    try:
        if abs(time.time() - int(ts)) > tolerance:
            return False
    except ValueError:
        return False
    return hmac.compare_digest(sign(secret, body, ts), signature)
