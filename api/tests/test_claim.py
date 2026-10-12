"""Rewards paid from the operator wallet when the worker claims them."""

import time

from conftest import RH_ESCROW
from test_workers import sign_in_evm

from humanapi_api import escrow_chain, ledger
from humanapi_api.models import Payout, Task, Worker

ADMIN = {"Authorization": "Bearer adm"}


class FakeWallet:
    """Stands in for the operator wallet: holds USDG, sends transfers, remembers them."""

    address = "0x00000000000000000000000000000000000000Aa"

    def __init__(self, usdg=0):
        self.usdg, self.sent, self.n = usdg, [], 0

    def balance(self):
        return self.usdg

    def prepare(self, transfers):
        self.n += 1
        return f"0xclaim{self.n}", transfers

    def broadcast(self, raw):
        for to, amount in raw:
            self.usdg -= amount
            self.sent.append((to.lower(), amount))


def ready(client, app, kind):
    h, acct = sign_in_evm(client)
    from sqlalchemy import func

    with app.state.db.session() as s:
        w = s.query(Worker).filter(func.lower(Worker.wallet) == acct.address.lower()).one()
        w.qualified_types, w.terms_accepted_at = [kind], time.time()
    return h, acct


def post_one(client, app, settings, wallet):
    settings.admin_token, settings.echo_worker, settings.house_batch_size = "adm", False, 1
    settings.escrow_contract = RH_ESCROW
    app.state.jobs.reward_sender = wallet
    app.state.jobs.chain = type("C", (), {"available": lambda self: 0, "status": lambda self, t: 0, "info": lambda self: {}})()
    escrow_chain._last_pool_sync = 0.0
    client.post("/v1/admin/escrow/run", headers=ADMIN)  # the pool's books follow the wallet
    body = {"type": "verify", "title": "Is the sign on this door current?", "payload": {"category": "real_and_current", "text": "A photo of a door sign reading 'Closed Mondays'.", "question": "Does the sign say the shop is closed on Mondays?"}, "workers": 3, "pricePerWorker": 2_000_000, "location": "Remote"}
    r = client.post("/v1/admin/team/run", json={"tasks": [body], "wallets": [], "teamRun": False}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return next(t for t in client.get("/v1/tasks/open").json()["tasks"] if t["taskId"] == r.json()["posted"][0])


def test_reward_is_claimed_from_the_wallet(client, app, settings):
    wallet = FakeWallet(usdg=100_000_000)
    task = post_one(client, app, settings, wallet)
    assert client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"] == 100_000_000  # books = wallet
    kind, tid, price, n = task["type"], task["taskId"], task["price"], task["workers"]
    answer = "yes" if kind == "verify" else 0
    workers = []
    for _ in range(n):
        h, acct = ready(client, app, kind)
        workers.append((h, acct))
        assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
        r = client.post(f"/v1/tasks/{tid}/answer", json={"answer": answer}, headers=h)
        assert r.status_code == 200, r.text
    with app.state.db.session() as s:
        t = s.get(Task, tid)
        assert t.state == "done" and t.chain_state == "funded"
        assert {p.status for p in s.query(Payout).filter_by(task_id=tid).all()} == {"claimable"}
        assert ledger.check_invariant(s, "robinhood")["balanced"]
    h, acct = workers[0]
    me = client.get(f"/v1/tasks/{tid}/comments", headers=h).json()["comments"]
    mine = next(c for c in me if c["mine"])
    assert mine["claimable"] and mine["canClaim"] and not mine["rewardPaid"]
    r = client.post(f"/v1/tasks/{tid}/claim-reward", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == price and r.json()["transaction"] == "0xclaim1" and wallet.sent == [(acct.address.lower(), price)]
    assert client.post(f"/v1/tasks/{tid}/claim-reward", headers=h).status_code == 404  # nothing left to claim
    e = client.get("/v1/workers/earnings", headers=h).json()
    assert e["paid"] == price and any(p["status"] == "sent" and p["transaction"] == "0xclaim1" for p in e["payouts"])
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == price * (n - 1)


def test_claims_stop_at_the_daily_cap_and_when_the_wallet_is_low(client, app, settings):
    wallet = FakeWallet(usdg=100_000_000)
    task = post_one(client, app, settings, wallet)
    kind, tid, price, n = task["type"], task["taskId"], task["price"], task["workers"]
    answer = "yes" if kind == "verify" else 0
    hs = []
    for _ in range(n):
        h, _ = ready(client, app, kind)
        hs.append(h)
        client.post(f"/v1/tasks/{tid}/claim", headers=h)
        client.post(f"/v1/tasks/{tid}/answer", json={"answer": answer}, headers=h)
    settings.wallet_payout_daily_cap = price  # one reward fits, the next does not
    assert client.post(f"/v1/tasks/{tid}/claim-reward", headers=hs[0]).status_code == 200
    r = client.post(f"/v1/tasks/{tid}/claim-reward", headers=hs[1])
    assert r.status_code == 429 and r.json()["error"] == "daily_cap"
    settings.wallet_payout_daily_cap = 10**12
    wallet.usdg = 0
    r = client.post(f"/v1/tasks/{tid}/claim-reward", headers=hs[1])
    assert r.status_code == 503 and r.json()["error"] == "wallet_low"
    with app.state.db.session() as s:
        assert s.query(Payout).filter_by(task_id=tid, status="claimable").count() == n - 1  # still waiting, nothing lost


def test_in_contract_mode_the_claim_settles_on_the_contract(client, app, settings):
    from test_escrow_chain import FakeChain

    settings.house_payout = "contract"
    settings.admin_token, settings.echo_worker, settings.escrow_contract = "adm", False, RH_ESCROW
    chain = FakeChain()
    chain.wallet = 100_000_000  # USDG the operator holds; the contract itself starts empty
    app.state.jobs.chain = chain
    escrow_chain._last_pool_sync = 0.0
    client.post("/v1/admin/escrow/run", headers=ADMIN)
    body = {"type": "verify", "title": "Is the sign on this door current?", "payload": {"category": "real_and_current", "text": "A door sign reading 'Closed Mondays'.", "question": "Does it say closed on Mondays?"}, "workers": 1, "pricePerWorker": 2_000_000, "location": "Remote"}
    tid = client.post("/v1/admin/team/run", json={"tasks": [body], "wallets": [], "teamRun": False}, headers=ADMIN).json()["posted"][0]
    h, acct = ready(client, app, "verify")
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
    client.post("/v1/admin/escrow/run", headers=ADMIN)  # the contract locks the reward
    assert chain.tasks[tid]["status"] == 1
    assert client.post(f"/v1/tasks/{tid}/answer", json={"answer": "yes"}, headers=h).status_code == 200
    assert client.post("/v1/admin/escrow/run", headers=ADMIN).json()["settled"] == 0  # waits for the claim
    with app.state.db.session() as s:
        assert s.get(Task, tid).state == "done" and s.query(Payout).filter_by(task_id=tid).one().status == "claimable"
    r = client.post(f"/v1/tasks/{tid}/claim-reward", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["transaction"].startswith("0xtx") and chain.tasks[tid]["status"] == 2
    assert (acct.address.lower(), 2_000_000) in [(a.lower(), n) for a, n in chain.sent]
    with app.state.db.session() as s:
        po = s.query(Payout).filter_by(task_id=tid).one()
        assert po.status == "sent" and po.batch_ref == r.json()["transaction"]
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_operator_can_close_a_task_with_the_answers_it_has(client, app, settings):
    wallet = FakeWallet(usdg=100_000_000)
    task = post_one(client, app, settings, wallet)  # wants 3 answers
    tid, kind = task["taskId"], task["type"]
    h, _ = ready(client, app, kind)
    client.post(f"/v1/tasks/{tid}/claim", headers=h)
    client.post(f"/v1/tasks/{tid}/answer", json={"answer": "yes"}, headers=h)
    assert client.get(f"/v1/tasks/{tid}").json()["state"] != "done"
    r = client.post(f"/v1/admin/tasks/{tid}/close", headers=ADMIN)
    assert r.status_code == 200 and r.json()["state"] == "done", r.text
    with app.state.db.session() as s:
        assert s.query(Payout).filter_by(task_id=tid, status="claimable").count() == 1  # the one answer is accepted and claimable
        assert ledger.check_invariant(s, "robinhood")["balanced"]
