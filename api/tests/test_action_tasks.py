import time

from conftest import pay
from test_workers import sign_in_evm

from humanapi_api import ledger
from humanapi_api.models import Answer, Task

ADMIN = {"Authorization": "Bearer adm"}
DO = {"type": "do", "payload": {"instructions": "Open the link and copy the opening hours shown on the page into the proof.", "url": "https://example.com/hours", "proof": "text"}}


def qualify_do(client, h):
    client.post("/v1/workers/profile", json={"acceptTerms": True}, headers=h)
    r = client.post("/v1/workers/qualification/do", json={"answers": [1, 1, 1]}, headers=h).json()
    assert r["passed"]


def test_do_pricing_and_validation(client):
    r = client.post("/v1/tasks", json=DO)
    assert r.status_code == 402 and r.json()["quote"]["total"] == 1_200_000
    bad = client.post("/v1/tasks", json={"type": "do", "payload": {"instructions": "too short"}})
    assert bad.status_code == 400 and "instructions" in bad.json()["message"]
    bad = client.post("/v1/tasks", json={"type": "do", "payload": {"instructions": "x" * 30, "proof": "video"}})
    assert "proof" in bad.json()["message"]


def test_money_actions_go_to_review(client):
    t = pay(client, {"type": "do", "payload": {"instructions": "Go to the shop page and buy two units with the saved card, then confirm."}}).json()
    assert t["moderation"]["status"] == "review" and t["moderation"]["reason"] == "money_action"


def test_proof_flow_accept(client, app, settings):
    settings.echo_worker = False
    t = pay(client, DO).json()
    h, _ = sign_in_evm(client)
    qualify_do(client, h)
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    assert feed[0]["type"] == "do" and feed[0]["preview"].startswith("Open the link")
    c = client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h).json()
    assert c["holdExpiresAt"] - int(time.time()) > 1500  # the whole time limit, not two minutes
    assert client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "hi"}}, headers=h).status_code == 400
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "Mon to Fri 9:00 to 18:00, Sat 10:00 to 14:00, closed Sunday."}}, headers=h).json()
    assert r["state"] == "submitted"
    view = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert view["proof"]["value"]["text"].startswith("Mon") and view["acceptBy"] > time.time()
    # the deadline passing does not expire a task whose proof is in
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "submitted"
    assert client.post(f"/v1/tasks/{t['taskId']}/accept", json={"buyerToken": "x"}).status_code == 403
    done = client.post(f"/v1/tasks/{t['taskId']}/accept", json={"buyerToken": t["buyerToken"]}).json()
    assert done["state"] == "done" and done["result"]["proof"]["text"].startswith("Mon")
    e = client.get("/v1/workers/earnings", headers=h).json()
    assert e["pending"] == 1_000_000
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"] == {"task": 0, "worker_due": 1_000_000, "platform_fee": 200_000, "refund_due": 0, "house": 0, "payer": 0}


def test_proof_auto_accepts_after_window(client, app, settings):
    settings.echo_worker = False
    t = pay(client, DO).json()
    h, _ = sign_in_evm(client)
    qualify_do(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "Hours: 9 to 5 every day."}}, headers=h)
    with app.state.db.session() as s:
        a = s.query(Answer).one()
        a.submitted_at = time.time() - 3700
    assert app.state.jobs.tick()["accepted"] == 1
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "done"


def test_proof_rejected_then_admin_decides(client, app, settings):
    settings.echo_worker = False
    settings.admin_token = "adm"
    t = pay(client, DO).json()
    h, _ = sign_in_evm(client)
    qualify_do(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "Could not find any hours on the page."}}, headers=h)
    d = client.post(f"/v1/tasks/{t['taskId']}/accept", json={"buyerToken": t["buyerToken"], "reject": True, "reason": "the hours are printed right at the top"}).json()
    assert d["status"] == "open" and client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "disputed"
    r = client.post(f"/v1/admin/disputes/{d['disputeId']}", json={"outcome": "upheld"}, headers=ADMIN).json()
    assert r["status"] == "upheld" and r["refund"] == 1_200_000
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "expired"
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["refund_due"] == 1_200_000 and inv["liabilities"]["worker_due"] == 0


def test_proof_rejected_but_worker_was_right(client, app, settings):
    settings.echo_worker = False
    settings.admin_token = "adm"
    t = pay(client, DO).json()
    h, _ = sign_in_evm(client)
    qualify_do(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "Open 24 hours, as printed on the page."}}, headers=h)
    d = client.post(f"/v1/tasks/{t['taskId']}/accept", json={"buyerToken": t["buyerToken"], "reject": True, "reason": "this does not look right to me"}).json()
    r = client.post(f"/v1/admin/disputes/{d['disputeId']}", json={"outcome": "rejected", "note": "proof matches the page"}, headers=ADMIN).json()
    assert r["status"] == "rejected"
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "done"
    assert client.get("/v1/workers/earnings", headers=h).json()["pending"] == 1_000_000


def test_no_proof_by_deadline_expires(client, app, settings):
    settings.echo_worker = False
    t = pay(client, DO).json()
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    v = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert v["state"] == "expired" and v["refund"] == 1_200_000
