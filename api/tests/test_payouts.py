from conftest import pay, verify_body
from sqlalchemy import select

from humanapi_api import ledger
from humanapi_api.models import Payout, Refund
from humanapi_api.payouts import recover, run_round


class FakeSender:
    rail = "robinhood"

    def __init__(self, per_tx=1, fail_prepare=False, status="sent"):
        self.per_tx, self.fail_prepare, self._status = per_tx, fail_prepare, status
        self.sent: list[list[tuple[str, int]]] = []
        self.n = 0

    def max_per_tx(self):
        return self.per_tx

    def prepare(self, transfers):
        if self.fail_prepare:
            raise RuntimeError("rpc down")
        self.n += 1
        return f"0xtx{self.n}", list(transfers)

    def broadcast(self, prepared):
        self.sent.append(prepared)

    def status(self, tx):
        return self._status


def _complete_three(client, app):
    from humanapi_api.echo_worker import ensure_workers
    from humanapi_api.models import Task
    from humanapi_api.tasks import claim, submit

    t = pay(client, verify_body()).json()
    with app.state.db.session() as s:
        task = s.get(Task, t["taskId"])
        for i, w in enumerate(ensure_workers(s, 3)):
            w.wallet = f"0x{i + 1:040x}"
            claim(s, task, w)
            submit(s, task and app.state.settings, task, w, "yes")
        assert task.state == "done"
    return t


def test_round_groups_per_wallet_and_posts_ledger(client, app, settings):
    settings.echo_worker = False
    _complete_three(client, app)
    _complete_three(client, app)  # same three echo workers again: two payouts each
    sender = FakeSender(per_tx=1)
    with app.state.db.session() as s:
        out = run_round(s, settings, {"robinhood": sender})
        assert out == {"payouts": 6, "refunds": 0, "transactions": 3, "failed": 0}
        assert sorted(a for batch in sender.sent for _, a in batch) == [160_000] * 3
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == 0 and inv["escrow"] == 2 * 48_000
        assert {p.status for p in s.scalars(select(Payout)).all()} == {"sent"}
        assert all(p.batch_ref.startswith("0xtx") for p in s.scalars(select(Payout)).all())


def test_min_amount_and_round_cap(client, app, settings):
    settings.echo_worker = False
    _complete_three(client, app)
    settings.payout_min_amount = 100_000  # each worker is owed 80_000: nothing goes out
    with app.state.db.session() as s:
        assert run_round(s, settings, {"robinhood": FakeSender()})["payouts"] == 0
    settings.payout_min_amount = 1
    settings.payout_round_cap = 100_000  # only one transfer fits
    with app.state.db.session() as s:
        assert run_round(s, settings, {"robinhood": FakeSender()})["payouts"] == 1


def test_refunds_are_paid_and_failures_requeue(client, app, settings):
    import time

    from humanapi_api.models import Task

    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    settings.payout_min_amount = 1
    with app.state.db.session() as s:
        out = run_round(s, settings, {"robinhood": FakeSender(status="failed")})
        assert out["failed"] == 1
        r = s.scalars(select(Refund)).one()
        assert r.status == "queued" and r.attempts == 1 and r.transaction == "0xtx1"
        assert ledger.check_invariant(s, "robinhood")["liabilities"]["refund_due"] == 288_000
    with app.state.db.session() as s:
        out = run_round(s, settings, {"robinhood": FakeSender()})
        assert out["refunds"] == 1
        r = s.scalars(select(Refund)).one()
        assert r.status == "sent" and ledger.check_invariant(s, "robinhood")["escrow"] == 0


def test_recovery_resolves_sending_rows(client, app, settings):
    settings.echo_worker = False
    _complete_three(client, app)
    with app.state.db.session() as s:
        for p in s.scalars(select(Payout)).all():
            p.status, p.batch_ref = "sending", "0xlost"
    with app.state.db.session() as s:
        assert recover(s, {"robinhood": FakeSender(status="sent")}) == 3
        assert {p.status for p in s.scalars(select(Payout)).all()} == {"sent"}
        assert ledger.check_invariant(s, "robinhood")["liabilities"]["worker_due"] == 0
