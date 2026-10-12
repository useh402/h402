"""The 402 side: build PaymentRequired for a quote, parse PAYMENT-SIGNATURE, talk to the facilitator."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger("humanapi.api.x402")


def canonical_hash(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def b64json(data: Any) -> str:
    return base64.b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()


def decode_b64json(value: str) -> Any:
    return json.loads(base64.b64decode(value + "=" * (-len(value) % 4)))


class FacilitatorClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.url = settings.facilitator_url.rstrip("/")
        self.token = settings.facilitator_settle_token
        self.http = httpx.Client(timeout=settings.facilitator_timeout_seconds, transport=transport)
        self._supported: dict | None = None
        self._supported_at = 0.0
        self._lock = threading.Lock()

    def supported(self, max_age: float = 60.0) -> dict:
        with self._lock:
            if self._supported and time.time() - self._supported_at < max_age:
                return self._supported
            r = self.http.get(f"{self.url}/supported")
            r.raise_for_status()
            self._supported = r.json()
            self._supported_at = time.time()
            return self._supported

    def extra_for(self, network: str) -> dict:
        """Scheme extras the facilitator advertises (the Solana fee payer)."""
        try:
            for kind in self.supported().get("kinds", []):
                if kind.get("network") == network and kind.get("extra"):
                    return dict(kind["extra"])
        except Exception as e:
            logger.warning("facilitator /supported unavailable: %s", str(e)[:200])
        return {}

    def verify(self, payload: dict, requirements: dict) -> dict:
        r = self.http.post(f"{self.url}/verify", json={"x402Version": 2, "paymentPayload": payload, "paymentRequirements": requirements})
        if r.status_code >= 400:
            return {"isValid": False, "invalidReason": "facilitator_error", "invalidMessage": r.text[:200]}
        return r.json()

    def gas(self, address: str) -> dict:
        """Asks the facilitator to put a little gas in a worker's wallet so they can move their rewards."""
        r = self.http.post(f"{self.url}/gas", json={"address": address}, headers={"Authorization": f"Bearer {self.token}"} if self.token else {})
        if r.status_code >= 400:
            try:
                detail = r.json()
            except ValueError:
                detail = {}
            return {"granted": False, "reason": str(detail.get("reason") or detail.get("error") or f"facilitator {r.status_code}"), "message": str(detail.get("message") or "")[:200], "transaction": None}
        return r.json()

    def settle(self, payload: dict, requirements: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        r = self.http.post(f"{self.url}/settle", json={"x402Version": 2, "paymentPayload": payload, "paymentRequirements": requirements}, headers=headers)
        if r.status_code >= 400:
            return {"success": False, "errorReason": "facilitator_error", "errorMessage": r.text[:200], "transaction": "", "network": requirements.get("network", "")}
        return r.json()


def requirements_for(settings: Settings, facilitator: FacilitatorClient, total: int, resource_url: str) -> list[dict]:
    accepts = []
    for rail in settings.rails():
        extra: dict[str, Any] = {}
        if rail["name"] == "robinhood":
            extra["assetTransferMethod"] = "permit2"
        else:
            extra.update(facilitator.extra_for(rail["network"]))
        accepts.append(
            {
                "scheme": "exact",
                "network": rail["network"],
                "asset": rail["asset"],
                "amount": str(total),
                "payTo": rail["pay_to"],
                "maxTimeoutSeconds": settings.max_timeout_seconds,
                "extra": extra,
            }
        )
    return accepts


def payment_required(accepts: list[dict], resource_url: str, description: str, error: str = "Payment required") -> dict:
    return {
        "x402Version": 2,
        "error": error,
        "resource": {"url": resource_url, "description": description, "mimeType": "application/json"},
        "accepts": accepts,
    }


def match_accept(payload: dict, accepts: list[dict]) -> dict | None:
    """The requirement the payer accepted must be one we offered, field for field."""
    accepted = payload.get("accepted") or {}
    for req in accepts:
        same = all(str(accepted.get(k, "")).lower() == str(req[k]).lower() for k in ("scheme", "network", "asset", "amount", "payTo"))
        if same:
            return req
    return None
