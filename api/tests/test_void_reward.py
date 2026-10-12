"""The operator can take back an approved reward nobody claimed; the worker sees why, and the money returns to the pool."""

import pytest
from test_claim import FakeWallet, post_one, ready

from humanapi_api import ledger
from humanapi_api import tasks as tasks_mod

ADMIN = {"Authorization": "Bearer adm"}


@pytest.fixture
def operator_all():
    tasks_mod.OPERATOR_DECIDES_ALL["on"] = True
    yield
    tasks_mod.OPERATOR_DECIDES_ALL["on"] = False


def approved_unclaimed(client, app, settings):
    task = post_one(client, app, settings, FakeWallet(usdg=100_000_000))
    heads = []
    for _ in range(3):
        h, _ = ready(client, app, "verify")
        client.post(f"/v1/tasks/{task['taskId']}/claim", json={}, headers=h)
        client.post(f"/v1/tasks/{task['taskId']}/answer", json={"answer": "yes"}, headers=h)
        heads.append(h)
    assert client.post(f"/v1/admin/responses/{task['taskId']}", json={"decision": "approve"}, headers=ADMIN).status_code == 200
    return task, heads


def test_unclaimed_rewards_are_listed_and_can_be_voided(client, app, settings, operator_all):
    task, heads = approved_unclaimed(client, app, settings)
    listed = client.get("/v1/admin/unclaimed", headers=ADMIN).json()["tasks"]
    row = next(r for r in listed if r["taskId"] == task["taskId"])
    assert row["amount"] == 6_000_000 and row["workers"] == 3
    before = client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"]
    r = client.post(f"/v1/admin/tasks/{task['taskId']}/void-reward", json={"reason": "not claimed in time"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 6_000_000 and r.json()["workers"] == 3
    assert client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"] == before + 6_000_000
    assert task["taskId"] not in {x["taskId"] for x in client.get("/v1/admin/unclaimed", headers=ADMIN).json()["tasks"]}
    for h in heads:
        e = client.get("/v1/workers/earnings", headers=h).json()
        assert e["pending"] == 0
        gone = next(x for x in e["refused"] if x["taskId"] == task["taskId"])
        assert gone["amount"] == 2_000_000 and "not claimed in time" in gone["reason"]
        assert [p["status"] for p in e["payouts"] if p["taskId"] == task["taskId"]] == ["voided"]
    assert client.post(f"/v1/admin/tasks/{task['taskId']}/void-reward", json={}, headers=ADMIN).status_code == 409
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_a_claimed_reward_cannot_be_voided(client, app, settings, operator_all):
    task, heads = approved_unclaimed(client, app, settings)
    assert client.post(f"/v1/tasks/{task['taskId']}/claim-reward", headers=heads[0]).status_code == 200
    r = client.post(f"/v1/admin/tasks/{task['taskId']}/void-reward", json={}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["workers"] == 2  # the two who had not claimed; the paid one keeps their money
