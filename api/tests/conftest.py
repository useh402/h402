from __future__ import annotations

import base64
import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from humanapi_api.config import Settings  # noqa: E402

RH_NET = "eip155:46630"
SOL_NET = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
RH_ASSET = "0x1111111111111111111111111111111111111111"
SOL_ASSET = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
RH_ESCROW = "0xcD2F3c4De3B701fdAA1492e49aA90eB807187279"
SOL_ESCROW = "CK5bECJ4rYrbb4aoyeixk56xt5FoXwJTZ2ztexAU8mo"
PAYER = "0x857b06519E91e3A54538791bDbb0E22373e36b66"
SOL_PAYER = "5oMRsZDnSnXfaUQ6QjLFx9frxGEsyyja4o35J9X9MPCA"


class FakeFacilitator:
    """Answers /supported, /verify and /settle like the real service, without a chain."""

    def __init__(self):
        self.verify_reason: str | None = None
        self.settle_reason: str | None = None
        self.calls: list[tuple[str, dict]] = []
        self.counter = 0
        self.fixed_tx: str | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/supported":
            return httpx.Response(200, json={"kinds": [{"x402Version": 2, "scheme": "exact", "network": RH_NET}, {"x402Version": 2, "scheme": "exact", "network": SOL_NET, "extra": {"feePayer": "EmHQbttAH9SE3Ha8WAgs9bvEvwnHbbJXVVHnAxfi8Vwz"}}]})
        body = json.loads(request.content)
        self.calls.append((path, body))
        if path == "/gas":
            return httpx.Response(200, json={"granted": True, "amountWei": "20000000000000", "transaction": "0xgas"})
        req = body["paymentRequirements"]
        payer = PAYER if req["network"].startswith("eip155") else SOL_PAYER
        if path == "/verify":
            if self.verify_reason:
                return httpx.Response(200, json={"isValid": False, "invalidReason": self.verify_reason})
            return httpx.Response(200, json={"isValid": True, "payer": payer})
        if path == "/settle":
            if request.headers.get("authorization") != "Bearer tok":
                return httpx.Response(401, json={"error": "unauthorized"})
            if self.settle_reason:
                return httpx.Response(200, json={"success": False, "errorReason": self.settle_reason, "transaction": "", "network": req["network"]})
            self.counter += 1
            tx = self.fixed_tx or ("0x" + f"{self.counter:064x}" if req["network"].startswith("eip155") else f"sig{self.counter}")
            return httpx.Response(200, json={"success": True, "transaction": tx, "network": req["network"], "payer": payer})
        return httpx.Response(404)


class HookReceiver:
    def __init__(self):
        self.received: list[dict] = []
        self.fail_times = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail_times > 0:
            self.fail_times -= 1
            return httpx.Response(500)
        self.received.append({"headers": dict(request.headers), "raw": request.content, "body": json.loads(request.content)})
        return httpx.Response(200)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        env="local",
        database_url=f"sqlite:///{tmp_path}/api.db",
        facilitator_url="http://facilitator",
        facilitator_settle_token="tok",
        robinhood_enabled=True,
        robinhood_asset=RH_ASSET,
        robinhood_escrow_address=RH_ESCROW,
        solana_enabled=True,
        solana_asset=SOL_ASSET,
        solana_escrow_address=SOL_ESCROW,
        echo_worker=True,
        jobs_enabled=False,
        public_base_url="http://api.test",
        min_reward=0,
        public_cache_seconds=0,
        _env_file=None,
    )


@pytest.fixture
def fac():
    return FakeFacilitator()


@pytest.fixture
def hooks():
    return HookReceiver()


@pytest.fixture
def app(settings, fac, hooks):
    from humanapi_api.app import create_app

    return create_app(settings, facilitator_transport=httpx.MockTransport(fac.handler), jobs_http=httpx.Client(transport=httpx.MockTransport(hooks.handler)))


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def verify_body(**over) -> dict:
    body = {"type": "verify", "payload": {"image": "https://x/receipt.jpg", "question": "Is the total legible?"}}
    body.update(over)
    return body


def payment_header(accepts: list[dict], network: str = RH_NET) -> str:
    req = next(a for a in accepts if a["network"] == network)
    payload = {"x402Version": 2, "accepted": req, "payload": {"signature": "0xsig", "permit2Authorization": {"from": PAYER, "nonce": "1"}}}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_header(value: str) -> dict:
    return json.loads(base64.b64decode(value + "=" * (-len(value) % 4)))


def pay(client, body: dict, network: str = RH_NET, headers: dict | None = None, path: str = "/v1/tasks"):
    quote = client.post(path, json=body)
    assert quote.status_code == 402, quote.text
    accepts = decode_header(quote.headers["PAYMENT-REQUIRED"])["accepts"]
    h = {"PAYMENT-SIGNATURE": payment_header(accepts, network)}
    h.update(headers or {})
    return client.post(path, json=body, headers=h)
