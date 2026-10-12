"""Local only: insert paid tasks straight into the database (no chain), so the Earn pages have work to show.

    uv run python demo/seed_tasks.py [--n 6] [--rail robinhood|solana]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from humanapi_api import ledger  # noqa: E402
from humanapi_api.catalogue import STARTER_TASKS as BODIES  # noqa: E402
from humanapi_api.config import Settings  # noqa: E402
from humanapi_api.db import Database  # noqa: E402
from humanapi_api.models import Payment, new_id  # noqa: E402
from humanapi_api.pricing import parse_task, quote_task  # noqa: E402
from humanapi_api.tasks import create_tasks, get_or_create_buyer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=len(BODIES))
    ap.add_argument("--rail", default="robinhood")
    args = ap.parse_args()
    settings = Settings()
    if settings.env != "local":
        print("seeding is local only")
        return 1
    rail = next(r for r in settings.rails() if r["name"] == args.rail)
    db = Database(settings.database_url)
    db.create_all()
    reqs = [parse_task({"timeLimitSeconds": 3600, **BODIES[i % len(BODIES)]}) for i in range(args.n)]
    total = sum(quote_task(r, settings.platform_fee_bps)["total"] for r in reqs)
    payer = "0x857b06519e91e3a54538791bdbb0e22373e36b66" if args.rail == "robinhood" else "5oMRsZDnSnXfaUQ6QjLFx9frxGEsyyja4o35J9X9MPCA"
    with db.session() as s:
        payment = Payment(id=new_id("pay"), rail=args.rail, network=rail["network"], asset=rail["asset"], payer=payer, pay_to=rail["pay_to"], amount=total, transaction=f"seed-{new_id('tx')}", quote_id="seed")
        s.add(payment)
        s.flush()
        ledger.post(s, args.rail, "escrow", f"payer:{payer}", total, payment_id=payment.id, memo="seed (no chain)")
        buyer = get_or_create_buyer(s, args.rail, payer)
        tasks = create_tasks(s, settings, reqs, payment, buyer, None, None)
        for t in tasks:
            print(t.id, t.type, t.price_per_worker, "x", t.workers_wanted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
