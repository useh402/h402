"""Pay for a HumanAPI task with the x402 SDK client, then poll until it is done.

    uv run --extra demo python demo/pay_task.py robinhood|solana [--type verify]

Needs the facilitator (:8402) and the API (:8400) running, and the test keys from
demo/.keys.json in a checkout of useh402/facilitator (created by that project's setup scripts).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
import warnings
from pathlib import Path

warnings.simplefilter("ignore")

import httpx  # noqa: E402

API = os.environ.get("DEMO_API_URL", "http://127.0.0.1:8400")
KEYS = Path(__file__).resolve().parents[2] / "facilitators" / "demo" / ".keys.json"

BODIES = {
    "verify": {"type": "verify", "payload": {"image": "https://example.com/receipt.jpg", "question": "Is the total legible?"}},
    "choose": {"type": "choose", "payload": {"question": "Which headline is clearer?", "options": ["Pay humans per task", "Human intelligence for agents"]}},
    "rate": {"type": "rate", "payload": {"item": "A product description", "rubric": "1 unclear, 5 crystal clear"}, "workers": 1},
}


def build_client(rail: str, keys: dict):
    from x402 import x402Client

    client = x402Client()
    client.set_spend_controls(False)
    if rail == "robinhood":
        from eth_account import Account
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact import register_exact_evm_client

        register_exact_evm_client(client, EthAccountSigner(Account.from_key(keys["robinhood"]["payer"])), networks="eip155:46630")
    else:
        from solders.keypair import Keypair
        from x402.mechanisms.svm import KeypairSigner
        from x402.mechanisms.svm.exact import register_exact_svm_client

        register_exact_svm_client(client, KeypairSigner(Keypair.from_base58_string(keys["solana"]["payer"])), networks="solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", rpc_url="https://api.devnet.solana.com")
    return client


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rail", choices=["robinhood", "solana"])
    ap.add_argument("--type", default="verify", choices=list(BODIES))
    args = ap.parse_args()
    if not KEYS.exists():
        print("no test keys; run the facilitator setup scripts first")
        return 1
    keys = json.loads(KEYS.read_text())
    from x402.http.clients import wrapHttpxWithPayment

    client = build_client(args.rail, keys)
    body = BODIES[args.type]
    async with wrapHttpxWithPayment(client, timeout=240) as http:
        r = await http.post(f"{API}/v1/tasks", json=body)
        print("status:", r.status_code)
        print(json.dumps(r.json(), indent=2)[:1500])
        settle = r.headers.get("payment-response")
        if settle:
            print("settlement:", json.dumps(json.loads(base64.b64decode(settle)), indent=2))
        if r.status_code != 202:
            return 1
        task = r.json()
    print("waiting for the result ...")
    async with httpx.AsyncClient(timeout=30) as plain:
        for _ in range(60):
            await asyncio.sleep(2)
            t = (await plain.get(task["resultUrl"])).json()
            if t["state"] in ("done", "expired"):
                print(json.dumps(t, indent=2))
                receipt = (await plain.get(task["receiptUrl"])).json()
                print("receipt payouts:", receipt["payouts"], "refunds:", receipt["refunds"])
                return 0
            print("  state:", t["state"], "answers:", t["workers"]["answered"], time.strftime("%H:%M:%S"))
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
