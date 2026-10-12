import time

import pytest
from conftest import PAYER, RH_ESCROW, pay, verify_body
from test_workers import qualify, sign_in_evm

from humanapi_api import ledger
from humanapi_api.models import Payout, Task

ADMIN = {"Authorization": "Bearer adm"}


class FakeChain:
    """Behaves like the contract: refuses double opens, unfunded opens, overpaying and closing twice."""

    address = "0x00000000000000000000000000000000000000Aa"

    def __init__(self):
        self.balance, self.allocated, self.fees, self.tasks, self.sent, self.wallet, self.n = 0, 0, 0, {}, [], 0, 0

    def _tx(self):
        self.n += 1
        return f"0xtx{self.n}"

    def deposit(self, amount):  # an x402 payment arriving
        self.balance += amount

    def status(self, tid):
        return self.tasks.get(tid, {"status": 0})["status"]

    def unallocated(self):
        return self.balance - self.allocated - self.fees

    def available(self):
        return self.unallocated() + self.wallet

    def fund(self, amount):
        if self.wallet < amount:
            raise RuntimeError("operator wallet short")
        self.wallet -= amount
        self.balance += amount
        return self._tx()

    def open(self, tid, payer, amount):
        assert tid not in self.tasks and self.unallocated() >= amount
        self.tasks[tid] = {"status": 1, "payer": payer, "amount": amount}
        self.allocated += amount
        return self._tx()

    def settle(self, tid, workers, amounts, fee):
        t = self.tasks[tid]
        assert t["status"] == 1 and sum(amounts) + fee <= t["amount"] and fee * 10_000 <= t["amount"] * 3000
        back = t["amount"] - sum(amounts) - fee
        t["status"] = 2
        self.allocated -= t["amount"]
        self.fees += fee
        self.balance -= sum(amounts) + back
        self.sent += list(zip(workers, amounts, strict=True)) + ([(t["payer"], back)] if back else [])
        return self._tx()

    def refund(self, tid):
        t = self.tasks[tid]
        assert t["status"] == 1
        t["status"] = 3
        self.allocated -= t["amount"]
        self.balance -= t["amount"]
        self.sent.append((t["payer"], t["amount"]))
        return self._tx()

    def info(self):
        return {"contract": RH_ESCROW, "operator": self.address, "balance": self.balance, "allocated": self.allocated, "feesAccrued": self.fees, "operatorGasWei": 1}


@pytest.fixture
def chain(app, settings):
    settings.escrow_contract, settings.admin_token, settings.echo_worker = RH_ESCROW, "adm", False
    c = FakeChain()
    app.state.jobs.chain = c
    return c


def run(client):
    return client.post("/v1/admin/escrow/run", headers=ADMIN).json()


def test_paid_task_opens_and_settles_through_the_contract(client, app, chain):
    t = pay(client, verify_body()).json()
    assert t["escrow"]["state"] == "pending"
    assert run(client)["waiting"] == 1  # the payment has not reached the contract yet
    chain.deposit(288_000)
    assert run(client)["opened"] == 1
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["escrow"]["openTransaction"] == "0xtx1"
    wallets = []
    for value in ("yes", "yes", "no"):
        h, acct = sign_in_evm(client)
        qualify(client, h)
        wallets.append(acct.address)
        client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
        client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": value}, headers=h)
    assert run(client)["settled"] == 1
    paid = dict(chain.sent)
    assert paid[wallets[0]] == 80_000 and paid[wallets[1]] == 80_000 and wallets[2] not in paid
    assert paid[PAYER.lower()] == 80_000 and chain.fees == 48_000 and chain.allocated == 0  # the disagreeing slot goes back
    v = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert v["escrow"] == {"state": "closed", "openTransaction": "0xtx1", "closeTransaction": "0xtx2"}
    with app.state.db.session() as s:
        assert {p.status for p in s.query(Payout).all()} == {"sent"} and {p.batch_ref for p in s.query(Payout).all()} == {"0xtx2"}
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == 0 and inv["liabilities"]["refund_due"] == 0 and inv["escrow"] == 48_000 == chain.balance
    assert {k: v for k, v in run(client).items() if k not in ("poolRaised", "released")} == {"opened": 0, "settled": 0, "refunded": 0, "waiting": 0, "failed": 0}  # nothing happens twice


def test_expired_task_is_refunded_by_the_contract(client, app, chain):
    t = pay(client, verify_body()).json()
    chain.deposit(288_000)
    run(client)
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    assert run(client)["refunded"] == 1 and chain.sent == [(PAYER.lower(), 288_000)] and chain.balance == 0
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["escrow"] == 0


def test_platform_tasks_are_funded_from_the_operator_wallet(client, app, chain, settings):
    settings.house_payout = "contract"
    settings.house_batch_size = 1
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 500_000_000}, headers=ADMIN)
    client.post("/v1/admin/house/post", headers=ADMIN)
    tid = client.get("/v1/tasks/open").json()["tasks"][0]["taskId"]
    kind = client.get("/v1/tasks/open").json()["tasks"][0]["type"]
    assert {k: v for k, v in run(client).items() if k not in ("poolRaised", "released")} == {"opened": 0, "settled": 0, "refunded": 0, "waiting": 0, "failed": 0} and chain.tasks == {}  # listed only: nothing is locked yet
    h, _ = sign_in_evm(client)
    with app.state.db.session() as s:
        from humanapi_api.models import Worker

        w = s.query(Worker).one()
        w.qualified_types, w.terms_accepted_at = [kind], time.time()
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).json()["error"] == "not_funded"  # the operator wallet is empty
    chain.wallet = 500_000_000
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
    assert run(client)["opened"] == 1  # taking the task locks its money
    assert chain.tasks[tid]["payer"] == chain.address and chain.balance == chain.allocated > 0


def test_the_old_payout_job_leaves_contract_tasks_alone(client, app, chain, settings):
    from test_payouts import FakeSender

    from humanapi_api.payouts import run_round

    t = pay(client, verify_body(workers=1)).json()
    chain.deposit(96_000)
    run(client)
    h, _ = sign_in_evm(client)
    qualify(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes"}, headers=h)
    settings.payout_min_amount = 1
    sender = FakeSender()
    with app.state.db.session() as s:
        assert run_round(s, settings, {"robinhood": sender})["payouts"] == 0 and sender.sent == []
    assert run(client)["settled"] == 1


def test_escrow_admin_view(client, chain):
    pay(client, verify_body())
    v = client.get("/v1/admin/escrow", headers=ADMIN).json()
    assert v["tasks"]["pending"] == 1 and v["operator"] == chain.address


def test_listed_tasks_cost_nothing_until_taken(client, app, chain, settings):
    """With the contract on, the pool lists tasks for free; money moves only when someone takes one."""
    from humanapi_api.models import Worker

    settings.house_payout = "contract"
    settings.house_batch_size = 2
    r = client.post("/v1/admin/house/post", headers=ADMIN).json()
    assert r["posted"] == 2 and r["houseBalance"] == 0  # an empty pool can still list
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["escrow"] == 0
    assert client.get("/v1/tasks/open").json()["tasks"] == []  # listed, but hidden from the board until the pool can cover them
    with app.state.db.session() as s:
        from humanapi_api.models import Task

        t = s.query(Task).filter(Task.chain_state == "listed").first()
        tid, kind = t.id, t.type
    h, _ = sign_in_evm(client)
    with app.state.db.session() as s:
        w = s.query(Worker).one()
        w.qualified_types, w.terms_accepted_at = [kind], time.time()
    chain.wallet = 500_000_000
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).json()["error"] == "not_funded"  # the pool's books are empty
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 500_000_000}, headers=ADMIN)
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
    with app.state.db.session() as s:
        t = s.get(Task, tid)
        assert t.chain_state == "pending" and ledger.balance(s, "robinhood", f"task:{tid}") == t.price_per_worker * t.workers_wanted + t.fee
        assert ledger.check_invariant(s, "robinhood")["balanced"]
    # a listed task nobody took expires without touching the books
    other = [t for t in client.get("/v1/tasks/open").json()["tasks"] if t["taskId"] != tid][0]["taskId"]
    with app.state.db.session() as s:
        s.get(Task, other).deadline = time.time() - 1
    app.state.jobs.tick()
    with app.state.db.session() as s:
        assert s.get(Task, other).state == "expired" and ledger.balance(s, "robinhood", f"task:{other}") == 0 and ledger.balance(s, "robinhood", "house") == 500_000_000 - (s.get(Task, tid).price_per_worker * s.get(Task, tid).workers_wanted + s.get(Task, tid).fee)


def test_pool_books_follow_the_operator_wallet(client, app, chain, settings):
    from humanapi_api import escrow_chain

    escrow_chain._last_pool_sync = 0.0
    chain.wallet = 60_000_000  # USDG sent to the operator wallet, nothing recorded by hand
    assert run(client)["poolRaised"] == 60_000_000
    assert client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"] == 60_000_000
    escrow_chain._last_pool_sync = 0.0
    assert run(client)["poolRaised"] == 0  # already in line
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]
