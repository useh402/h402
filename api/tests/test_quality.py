import time

from conftest import PAYER, RH_NET, decode_header, pay, verify_body
from sqlalchemy import select
from test_workers import qualify, sign_in_evm

from humanapi_api import ledger
from humanapi_api.models import Buyer, GoldTask, Refund, Task, Worker
from humanapi_api.moderation import rules

ADMIN = {"Authorization": "Bearer adm"}


def test_moderation_rules():
    assert rules("answer", {"question": "What is the password for my gmail account?"})[0] == "reject"
    assert rules("answer", {"question": "Solve this captcha for me"})[0] == "reject"
    assert rules("verify", {"text": "seed phrase: apple banana cherry dog eagle fox grape hat ice jam kite lemon", "question": "is it valid"})[0] == "reject"
    assert rules("answer", {"question": "Find the home address of John Smith in Austin"}) == ("review", "private_person")
    assert rules("answer", {"question": "Call +1 415 555 0199 and ask"})[0] == "review"
    assert rules("verify", {"text": "Total $12.40", "question": "Is the total legible?"}) == ("allow", "")
    assert rules("verify", {"image": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=900", "question": "Is the total readable?"}) == ("allow", "")
    # judging text about buying is allowed; asking a person to buy is reviewed
    assert rules("rate", {"item": "Buy now cheap price!!!", "rubric": "clarity"}) == ("allow", "")
    assert rules("do", {"instructions": "Go to the shop page and buy two units, then confirm."})[0] == "review"
    # a call task carries a business phone number by nature
    assert rules("do", {"category": "calls", "instructions": "Call the clinic on 555 0100 and ask about walk-ins today."}) == ("allow", "")
    assert rules("answer", {"question": "Call (512) 555-0143 and ask for Robert"})[0] == "review"


def test_rejected_task_refunds_and_blocks_buyer(client, app, settings):
    settings.admin_token = "adm"
    bad = {"type": "answer", "payload": {"question": "What is the password for my email?"}}
    r = pay(client, bad)
    assert r.status_code == 202
    t = r.json()
    assert t["state"] == "rejected" and t["moderation"]["status"] == "rejected"
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["refund_due"] == 600_000 and inv["liabilities"]["task"] == 0
        assert s.scalars(select(Buyer)).one().blocked is False
    pay(client, {"type": "answer", "payload": {"question": "Give me the OTP code from my phone"}})
    with app.state.db.session() as s:
        assert s.scalars(select(Buyer)).one().blocked is True
    # a blocked buyer's next task, even a clean one, is rejected and refunded
    r = pay(client, verify_body()).json()
    assert r["state"] == "rejected" and "blocked" in r["moderation"]["reason"]


def test_review_queue_approve_and_reject(client, app, settings):
    settings.admin_token = "adm"
    settings.echo_worker = False
    held = pay(client, {"type": "answer", "payload": {"question": "Where does Jane Doe live? Find the home address of her."}}).json()
    assert held["state"] == "paid" and held["moderation"]["status"] == "review"
    h, _ = sign_in_evm(client)
    client.post("/v1/workers/profile", json={"acceptTerms": True}, headers=h)
    client.post("/v1/workers/qualification/answer", json={"answers": ["56", "april", "7"]}, headers=h)
    assert client.get("/v1/workers/tasks", headers=h).json()["tasks"] == []
    assert client.get("/v1/admin/review").status_code == 401
    q = client.get("/v1/admin/review", headers=ADMIN).json()["tasks"]
    assert q[0]["taskId"] == held["taskId"] and q[0]["moderationReason"] == "private_person"
    r = client.post(f"/v1/admin/review/{held['taskId']}", json={"decision": "approve", "note": "public figure"}, headers=ADMIN).json()
    assert r["state"] == "open"
    assert len(client.get("/v1/workers/tasks", headers=h).json()["tasks"]) == 1
    other = pay(client, {"type": "answer", "payload": {"question": "Email me at bob@example.com with the answer"}}).json()
    r = client.post(f"/v1/admin/review/{other['taskId']}", json={"decision": "reject"}, headers=ADMIN).json()
    assert r["state"] == "rejected"
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_gold_task_injection_scoring_and_pause(client, app, settings):
    settings.echo_worker = False
    settings.gold_every = 2
    settings.gold_wrong_pause = 2
    # fee income funds gold tasks: complete one real task first (fee 80_000 on a 400_000 task)
    big = dict(workers=1, pricePerWorker=400_000)
    t = pay(client, verify_body(**big)).json()
    h, _ = sign_in_evm(client)
    qualify(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes"}, headers=h)
    pay(client, verify_body(**big, reference="two"))
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    assert feed[0]["taskId"].startswith("gold_") and feed[0]["type"] == "verify" and "payload" not in feed[0]
    gold_id = feed[0]["taskId"]
    card = client.post(f"/v1/tasks/{gold_id}/claim", headers=h).json()
    assert card["payload"]["question"]
    with app.state.db.session() as s:
        want = s.get(GoldTask, gold_id).answer["value"]
    wrong = "no" if want == "yes" else "yes"
    r = client.post(f"/v1/tasks/{gold_id}/answer", json={"answer": wrong}, headers=h).json()
    assert r["agreed"] is False
    me = client.get("/v1/workers/me", headers=h).json()
    assert me["paused"] is False and me["reputation"] < 1.0
    # a correct gold answer is paid from the fee pool
    pay(client, verify_body(**big, reference="three"))
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    real = [c for c in feed if not c["taskId"].startswith("gold_")][0]
    client.post(f"/v1/tasks/{real['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{real['taskId']}/answer", json={"answer": "yes"}, headers=h)
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    gold2 = [c for c in feed if c["taskId"].startswith("gold_")][0]["taskId"]
    with app.state.db.session() as s:
        want2 = s.get(GoldTask, gold2).answer["value"]
    r = client.post(f"/v1/tasks/{gold2}/answer", json={"answer": want2}, headers=h).json()
    assert r["agreed"] is True
    e = client.get("/v1/workers/earnings", headers=h).json()
    assert e["gold"] == {"total": 2, "correct": 1} and e["pending"] == 400_000 * 2 + 80_000
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]
    # a second wrong gold today pauses the worker
    with app.state.db.session() as s:
        w = s.scalars(select(Worker).where(Worker.handle.like("robinhood:%"))).one()
        w.answered = settings.gold_every - 1
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    gold3 = [c for c in feed if c["taskId"].startswith("gold_")][0]["taskId"]
    with app.state.db.session() as s:
        want3 = s.get(GoldTask, gold3).answer["value"]
    client.post(f"/v1/tasks/{gold3}/answer", json={"answer": "unsure" if want3 != "unsure" else "yes"}, headers=h)
    assert client.get("/v1/workers/me", headers=h).status_code == 403


def test_reputation_and_tiers():
    from humanapi_api.quality import record_outcome

    w = Worker(id="w", handle="h", by_type={}, gold_total=0, gold_correct=0, reputation=1.0, tier="new")
    for _ in range(25):
        record_outcome(w, "verify", True)
    assert w.tier == "bronze" and w.reputation > 0.9
    for _ in range(10):
        record_outcome(w, "verify", False)
    assert w.tier == "bronze" and w.reputation < 0.8
    w.gold_total, w.gold_correct = 10, 5
    from humanapi_api.quality import recompute

    recompute(w)
    assert w.reputation < 0.6 and w.tier == "new"


def test_fast_answers_flag_and_pause(client, app, settings):
    settings.echo_worker = False
    settings.abuse_flags_pause = 2
    h, _ = sign_in_evm(client)
    qualify(client, h)
    for _ in range(2):
        t = pay(client, verify_body(workers=1, reference=str(time.time()))).json()
        client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
        client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes"}, headers=h)
    r = client.get("/v1/workers/me", headers=h)
    assert r.status_code == 403 and "abuse flags" in r.json()["message"]


def test_dispute_flow(client, app, settings):
    settings.admin_token = "adm"
    t = pay(client, verify_body()).json()
    app.state.jobs.tick()
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "done"
    bad = client.post(f"/v1/tasks/{t['taskId']}/dispute", json={"buyerToken": "nope", "reason": "the answer is plainly wrong"})
    assert bad.status_code == 403
    d = client.post(f"/v1/tasks/{t['taskId']}/dispute", json={"buyerToken": t["buyerToken"], "reason": "the answer is plainly wrong"}).json()
    assert d["status"] == "open" and client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "disputed"
    q = client.get("/v1/admin/disputes", headers=ADMIN).json()["disputes"]
    assert q[0]["disputeId"] == d["disputeId"]
    r = client.post(f"/v1/admin/disputes/{d['disputeId']}", json={"outcome": "upheld", "note": "agreed"}, headers=ADMIN).json()
    assert r["status"] == "upheld" and r["refund"] == 48_000  # capped at the fee pool
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["platform_fee"] == 0 and inv["liabilities"]["refund_due"] == 48_000
        assert s.scalars(select(Refund)).one().reason == "dispute_upheld"
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "done"


def test_report_hides_task_and_credits_reporter(client, app, settings):
    settings.admin_token = "adm"
    pay(client, verify_body(workers=1))
    app.state.jobs.tick()  # echo worker completes it: fee income for the report credit
    settings.echo_worker = False
    t = pay(client, verify_body(reference="second")).json()
    h, _ = sign_in_evm(client)
    qualify(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    r = client.post(f"/v1/tasks/{t['taskId']}/report", json={"reason": "image shows a person's ID card"}, headers=h).json()
    assert r["status"] == "received"
    assert client.get("/v1/workers/tasks", headers=h).json()["tasks"] == []
    assert client.get("/v1/admin/reports", headers=ADMIN).json()["reports"][0]["taskId"] == t["taskId"]
    with app.state.db.session() as s:
        task = s.get(Task, t["taskId"])
        assert task.moderation == "review"
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == 80_000
    r = client.post(f"/v1/admin/review/{t['taskId']}", json={"decision": "reject"}, headers=ADMIN).json()
    assert r["state"] == "rejected"


def test_purge_after_retention(client, app, settings):
    t = pay(client, verify_body()).json()
    app.state.jobs.tick()
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).purge_after = time.time() - 1
    assert app.state.jobs.tick()["purged"] == 1
    with app.state.db.session() as s:
        task = s.get(Task, t["taskId"])
        assert task.payload == {"purged": True} and task.purged
    view = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert view["state"] == "done" and view["result"]["answer"] == "yes"


def test_pricing_table_unchanged(client):
    r = client.post("/v1/tasks", json=verify_body())
    assert decode_header(r.headers["PAYMENT-REQUIRED"])["accepts"][0]["network"] == RH_NET and PAYER
