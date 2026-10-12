import time

from conftest import PAYER, RH_NET, SOL_NET, SOL_PAYER, decode_header, pay, verify_body
from sqlalchemy import select

from humanapi_api import ledger
from humanapi_api.models import Payout, Refund, Task
from humanapi_api.webhooks import verify_signature


def test_pay_creates_open_task_and_ledger(client, fac, app):
    r = pay(client, verify_body())
    assert r.status_code == 202, r.text
    t = r.json()
    assert t["state"] == "open" and t["cost"]["total"] == 288_000
    assert t["payment"]["network"] == RH_NET and t["payment"]["transaction"].startswith("0x")
    assert decode_header(r.headers["PAYMENT-RESPONSE"])["success"] is True
    assert [c[0] for c in fac.calls] == ["/verify", "/settle"]
    assert fac.calls[1][1]["paymentRequirements"]["amount"] == "288000"
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["escrow"] == 288_000 and inv["liabilities"]["task"] == 288_000 and inv["balanced"]
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "open"


def test_echo_worker_completes_and_webhook_is_signed(client, app, hooks):
    body = verify_body(webhook={"url": "http://buyer.test/hook"})
    r = pay(client, body)
    t = r.json()
    secret = t["webhookSecret"]
    assert secret.startswith("whsec_")
    tick = app.state.jobs.tick()
    assert tick["echo"] == 1
    done = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert done["state"] == "done" and done["result"]["answer"] == "yes" and done["agreement"] == 1.0
    app.state.jobs.tick()  # delivers the webhook
    assert len(hooks.received) == 1
    d = hooks.received[0]
    assert d["body"]["event"] == "task.done" and d["body"]["data"]["result"]["answer"] == "yes"
    assert verify_signature(secret, d["raw"], d["headers"]["x-h402-timestamp"], d["headers"]["x-h402-signature"])
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"] == {"task": 0, "worker_due": 240_000, "platform_fee": 48_000, "refund_due": 0, "house": 0, "payer": 0}
        assert len(s.scalars(select(Payout)).all()) == 3
    receipt = client.get(f"/v1/receipts/{t['taskId']}").json()
    assert receipt["consensus"]["agreed"] == 3 and len(receipt["payouts"]) == 3 and receipt["timeline"][-1]["to"] == "done"
    assert all(e["debit"].startswith("task:") or e["credit"].startswith("task:") for e in receipt["ledger"])


def test_webhook_retries_then_delivers(client, app, hooks):
    hooks.fail_times = 2
    pay(client, verify_body(webhook={"url": "http://buyer.test/hook"}))
    app.state.jobs.tick()
    app.state.jobs.tick()
    assert hooks.received == []
    with app.state.db.session() as s:
        from humanapi_api.models import WebhookDelivery

        d = s.scalars(select(WebhookDelivery)).one()
        assert d.attempts == 1 and d.status == "pending" and d.last_status == 500
        d.next_at = 0
    app.state.jobs.tick()
    with app.state.db.session() as s:
        d = s.scalars(select(WebhookDelivery)).one()
        d.next_at = 0
    app.state.jobs.tick()
    assert len(hooks.received) == 1


def test_same_settlement_returns_existing_task(client, fac):
    fac.fixed_tx = "0x" + "ab" * 32
    first = pay(client, verify_body()).json()
    second = pay(client, verify_body(reference="again"))
    assert second.status_code == 200 and second.json()["taskId"] == first["taskId"]


def test_payment_rejections(client, fac):
    fac.verify_reason = "insufficient_funds"
    r = pay(client, verify_body())
    assert r.status_code == 402 and "insufficient_funds" in r.json()["message"]
    fac.verify_reason = None
    fac.settle_reason = "settlement_pending"
    r = pay(client, verify_body())
    assert r.status_code == 402 and decode_header(r.headers["PAYMENT-RESPONSE"])["errorReason"] == "settlement_pending"


def test_accept_must_match_offer(client):
    quote = client.post("/v1/tasks", json=verify_body())
    accepts = decode_header(quote.headers["PAYMENT-REQUIRED"])["accepts"]
    accepts[0]["amount"] = "1"
    from conftest import payment_header

    r = client.post("/v1/tasks", json=verify_body(), headers={"PAYMENT-SIGNATURE": payment_header(accepts)})
    assert r.status_code == 402 and "not offered" in r.json()["message"]


def test_solana_rail(client, app):
    r = pay(client, verify_body(), network=SOL_NET)
    assert r.status_code == 202 and r.json()["payment"]["network"] == SOL_NET
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "solana")["escrow"] == 288_000
        assert ledger.check_invariant(s, "robinhood")["escrow"] == 0


def test_idempotency_key(client):
    body = verify_body()
    quote = client.post("/v1/tasks", json=body)
    from conftest import payment_header

    accepts = decode_header(quote.headers["PAYMENT-REQUIRED"])["accepts"]
    h = {"PAYMENT-SIGNATURE": payment_header(accepts), "Idempotency-Key": "k1"}
    a = client.post("/v1/tasks", json=body, headers=h)
    b = client.post("/v1/tasks", json=body, headers=h)
    assert a.status_code == 202 and b.status_code == 202 and a.json()["taskId"] == b.json()["taskId"]
    assert b.headers["PAYMENT-RESPONSE"] == a.headers["PAYMENT-RESPONSE"]
    c = client.post("/v1/tasks", json=verify_body(reference="other"), headers=h)
    assert c.status_code == 422


def test_batch(client, app):
    body = {"tasks": [verify_body(), {"type": "choose", "payload": {"question": "best?", "options": ["a", "b"]}}, {"type": "rate", "payload": {"item": "x", "rubric": "y"}, "workers": 1}]}
    r = pay(client, body, path="/v1/tasks/batch")
    assert r.status_code == 202, r.text
    data = r.json()
    assert len(data["tasks"]) == 3 and data["cost"]["total"] == 288_000 + 360_000 + 60_000
    assert client.get(f"/v1/batches/{data['batchId']}").json()["tasks"][2]["type"] == "rate"
    app.state.jobs.tick()
    states = [t["state"] for t in client.get(f"/v1/batches/{data['batchId']}").json()["tasks"]]
    assert states == ["done", "done", "done"]
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_expiry_refunds_everything(client, app, settings):
    settings.echo_worker = False
    t = pay(client, verify_body(timeLimitSeconds=30)).json()
    with app.state.db.session() as s:
        task = s.get(Task, t["taskId"])
        task.deadline = time.time() - 1
    assert app.state.jobs.tick()["expired"] == 1
    view = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert view["state"] == "expired" and view["refund"] == 288_000
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["refund_due"] == 288_000 and inv["liabilities"]["task"] == 0
        rf = s.scalars(select(Refund)).one()
        assert rf.payer == PAYER.lower() and rf.status == "queued"


def test_disagreement_pays_only_the_majority(client, app, settings):
    settings.echo_worker = False
    t = pay(client, {"type": "choose", "payload": {"question": "q", "options": ["a", "b", "c"]}}).json()
    from humanapi_api.echo_worker import ensure_workers
    from humanapi_api.tasks import claim, submit

    with app.state.db.session() as s:
        task = s.get(Task, t["taskId"])
        w = ensure_workers(s, 3)
        for worker, value in zip(w, [1, 1, 2], strict=True):
            claim(s, task, worker)
            submit(s, settings, task, worker, value)
        assert task.state == "done" and task.result["answer"] == 1 and task.agreement == round(2 / 3, 3)
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == 200_000 and inv["liabilities"]["refund_due"] == 100_000
        assert inv["liabilities"]["platform_fee"] == 60_000


def test_no_consensus_expires(client, app, settings):
    settings.echo_worker = False
    t = pay(client, {"type": "choose", "payload": {"question": "q", "options": ["a", "b", "c"]}}).json()
    from humanapi_api.echo_worker import ensure_workers
    from humanapi_api.tasks import claim, submit

    with app.state.db.session() as s:
        task = s.get(Task, t["taskId"])
        for worker, value in zip(ensure_workers(s, 3), [0, 1, 2], strict=True):
            claim(s, task, worker)
            submit(s, settings, task, worker, value)
        assert task.state == "expired"
        assert ledger.check_invariant(s, "robinhood")["liabilities"]["refund_due"] == 360_000


def test_buyer_level_webhook_strips_result(client, app, hooks):
    r = client.post("/v1/webhooks", json={"url": "http://buyer.test/all", "payer": SOL_PAYER, "network": SOL_NET})
    assert r.status_code == 201 and r.json()["secret"].startswith("whbs_")
    pay(client, verify_body(), network=SOL_NET)
    app.state.jobs.tick()
    app.state.jobs.tick()
    assert len(hooks.received) == 1
    data = hooks.received[0]["body"]["data"]
    assert data["state"] == "done" and "result" not in data


def test_state_machine_rejects_illegal_moves(app):
    import pytest

    from humanapi_api.models import Task as T
    from humanapi_api.states import IllegalTransition, transition

    with app.state.db.session() as s:
        t = T(id="task_x", buyer_id="b", payment_id="p", rail="robinhood", type="verify", payload={}, price_per_worker=1, workers_wanted=1, fee=0, time_limit_seconds=1, deadline=0, state="done")
        with pytest.raises(IllegalTransition):
            transition(s, t, "open")


def test_health(client):
    h = client.get("/health")
    assert h.status_code == 200
    data = h.json()
    assert data["ok"] and data["facilitator"] == "ok" and data["rails"]["robinhood"]["balanced"]
