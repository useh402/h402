"""With the operator deciding everything, no task is paid until they approve it on the admin page: consensus tasks included."""

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


def three_answers(client, app, settings, answers=("yes", "yes", "yes")):
    task = post_one(client, app, settings, FakeWallet(usdg=100_000_000))
    heads = []
    for a in answers:
        h, _ = ready(client, app, "verify")
        assert client.post(f"/v1/tasks/{task['taskId']}/claim", json={}, headers=h).status_code == 200
        r = client.post(f"/v1/tasks/{task['taskId']}/answer", json={"answer": a}, headers=h)
        assert r.status_code == 200, r.text
        heads.append(h)
    return task, heads


def test_consensus_waits_for_the_operator_and_approve_pays(client, app, settings, operator_all):
    task, heads = three_answers(client, app, settings)
    v = client.get(f"/v1/tasks/{task['taskId']}").json()
    assert v["state"] == "submitted"  # agreement reached, nobody paid yet
    rows = client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()["responses"]
    assert {r["taskId"] for r in rows} == {task["taskId"]} and len(rows) == 3
    assert rows[0]["decision"] == "waiting" and rows[0]["awaitingOperator"]
    r = client.post(f"/v1/admin/responses/{task['taskId']}", json={"decision": "approve"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert client.get(f"/v1/tasks/{task['taskId']}").json()["state"] == "done"
    for h in heads:
        assert client.get("/v1/workers/earnings", headers=h).json()["pending"] == 2_000_000
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_operator_refuses_a_consensus_task_and_nobody_is_paid(client, app, settings, operator_all):
    task, heads = three_answers(client, app, settings)
    r = client.post(f"/v1/admin/responses/{task['taskId']}", json={"decision": "refuse"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert client.get(f"/v1/tasks/{task['taskId']}").json()["state"] == "expired"
    for h in heads:
        assert client.get("/v1/workers/earnings", headers=h).json()["pending"] == 0
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_a_consensus_task_waits_for_the_operator_only_once_every_answer_is_in(client, app, settings, operator_all):
    task = post_one(client, app, settings, FakeWallet(usdg=100_000_000))
    h, _ = ready(client, app, "verify")
    client.post(f"/v1/tasks/{task['taskId']}/claim", json={}, headers=h)
    client.post(f"/v1/tasks/{task['taskId']}/answer", json={"answer": "yes"}, headers=h)
    rows = client.get("/v1/admin/responses?status=all", headers=ADMIN).json()["responses"]
    assert next(r for r in rows if r["taskId"] == task["taskId"])["decision"] == "open"  # one of three in: still collecting
    assert client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()["responses"] == []
    with app.state.db.session() as s:
        s.get(tasks_mod.Task, task["taskId"]).deadline = 1.0
    rows = client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()["responses"]
    assert [r["taskId"] for r in rows] == [task["taskId"]]  # the deadline passed: the operator decides with what is in


def test_the_deadline_does_not_decide_a_task_with_answers(client, app, settings, operator_all):
    task, _ = three_answers(client, app, settings, ("yes", "no", "yes"))
    with app.state.db.session() as s:
        t = s.get(tasks_mod.Task, task["taskId"])
        t.deadline = 1.0
    app.state.jobs.tick()
    assert client.get(f"/v1/tasks/{task['taskId']}").json()["state"] == "submitted"


def test_without_the_setting_consensus_still_decides_itself(client, app, settings):
    task, heads = three_answers(client, app, settings)
    assert client.get(f"/v1/tasks/{task['taskId']}").json()["state"] == "done"
    r = client.post(f"/v1/admin/responses/{task['taskId']}", json={"decision": "approve"}, headers=ADMIN)
    assert r.status_code == 409
