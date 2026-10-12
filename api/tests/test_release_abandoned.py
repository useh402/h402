"""A task taken, locked on the contract and then dropped before any answer is released: the money comes back and the
task is listed again under a fresh contract key. A worker who dropped a task can take it again without an error."""

import time

from test_claim import ready
from test_escrow_chain import ADMIN, chain, run  # noqa: F401

from humanapi_api import escrow_chain, ledger
from humanapi_api.models import Claim, Task


def listed_house_task(client, app, settings, chain):  # noqa: F811
    settings.house_payout, settings.house_batch_size = "contract", 1
    chain.wallet = 500_000_000
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 500_000_000}, headers=ADMIN)
    assert client.post("/v1/admin/house/post", headers=ADMIN).json()["posted"] == 1
    with app.state.db.session() as s:
        t = s.query(Task).filter(Task.chain_state == "listed").one()
        return t.id, t.type


def drop_hold(app, task_id):
    with app.state.db.session() as s:
        for c in s.query(Claim).filter(Claim.task_id == task_id).all():
            c.expires_at = time.time() - 1
    app.state.jobs.tick()  # releases the lapsed hold; the task goes back to open
    with app.state.db.session() as s:
        s.get(Task, task_id).updated_at = time.time() - 120  # long enough ago for the release to apply


def test_a_dropped_task_is_released_and_listed_again_under_a_new_key(client, app, settings, chain):  # noqa: F811
    tid, kind = listed_house_task(client, app, settings, chain)
    h, _ = ready(client, app, kind)
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
    assert run(client)["opened"] == 1 and chain.status(tid) == 1
    pool_before = client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"]
    drop_hold(app, tid)
    out = run(client)
    assert out["released"] == 1
    assert chain.status(tid) == 3  # refunded on the contract
    with app.state.db.session() as s:
        t = s.get(Task, tid)
        assert t.chain_state == "listed" and t.chain_round == 1 and t.state == "open"
        assert ledger.check_invariant(s, "robinhood")["balanced"]
    assert client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"] > pool_before
    # Taken again: locked under the fresh key, the old refunded one untouched.
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
    assert run(client)["opened"] == 1
    assert chain.status(f"{tid}#1") == 1 and chain.status(tid) == 3


def test_a_task_with_an_answer_or_a_live_hold_is_not_released(client, app, settings, chain):  # noqa: F811
    tid, kind = listed_house_task(client, app, settings, chain)
    h, _ = ready(client, app, kind)
    client.post(f"/v1/tasks/{tid}/claim", headers=h)
    run(client)
    with app.state.db.session() as s:
        s.get(Task, tid).updated_at = time.time() - 120
    assert run(client)["released"] == 0  # the hold is live
    escrow_chain._last_pool_sync = 0.0


def test_a_worker_who_dropped_a_task_can_take_it_again(client, app, settings, chain):  # noqa: F811
    tid, kind = listed_house_task(client, app, settings, chain)
    h, _ = ready(client, app, kind)
    assert client.post(f"/v1/tasks/{tid}/claim", headers=h).status_code == 200
    with app.state.db.session() as s:
        for c in s.query(Claim).filter(Claim.task_id == tid).all():
            c.expires_at = time.time() - 1
    app.state.jobs.tick()
    r = client.post(f"/v1/tasks/{tid}/claim", headers=h)
    assert r.status_code == 200, r.text  # no duplicate-hold crash: the old hold is reused
    with app.state.db.session() as s:
        assert s.query(Claim).filter(Claim.task_id == tid).count() == 1
