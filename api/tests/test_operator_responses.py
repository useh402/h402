"""Pictures are approved by the operator, never by the clock; every response is visible to the operator alone."""

import time

from conftest import pay
from test_photos import JPEG, do_worker  # noqa: F401
from test_verifier import gateway

from humanapi_api import house, ledger
from humanapi_api.models import Answer, Task
from humanapi_api.tasks import PICTURE_PROOFS

ADMIN = {"Authorization": "Bearer adm"}


def photo_task(client, write="The hours for each day, as printed"):
    payload = {"category": "documents_and_receipts", "instructions": "Photograph the hours sign at the main entrance. Write the capture code on paper and keep it in the shot.", "proof": "photos", "write": write}
    body = {"type": "do", "title": "Photograph the posted hours at the library", "payload": payload, "pricePerWorker": 20_000_000, "timeLimitSeconds": 3600}
    return pay(client, body).json()


def send_photo_proof(client, h, task_id, text="Mon to Fri 9 to 6, Sat 10 to 2, closed Sunday"):
    client.post(f"/v1/tasks/{task_id}/claim", headers=h)
    ph = client.post(f"/v1/tasks/{task_id}/photos", content=JPEG, headers=h).json()
    r = client.post(f"/v1/tasks/{task_id}/answer", json={"answer": {"text": text, "photos": [ph["photoId"]]}}, headers=h)
    assert r.status_code == 200, r.text
    return ph


def age_answer(app, seconds=3700):
    with app.state.db.session() as s:
        for a in s.query(Answer).all():
            a.submitted_at = time.time() - seconds


def test_photo_proof_waits_for_the_operator_not_the_clock(client, app, do_worker, settings):  # noqa: F811
    settings.admin_token = "adm"
    t = photo_task(client)
    send_photo_proof(client, do_worker, t["taskId"])
    view = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert view["state"] == "submitted" and view["awaitingOperator"] is True and "acceptBy" not in view
    age_answer(app)
    assert app.state.jobs.tick()["accepted"] == 0
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "submitted"
    assert client.get("/v1/workers/earnings", headers=do_worker).json()["pending"] == 0


def test_the_written_part_of_a_photo_task_is_required(client, do_worker, settings):  # noqa: F811
    t = photo_task(client, write="The price on the tag")
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=do_worker)
    ph = client.post(f"/v1/tasks/{t['taskId']}/photos", content=JPEG, headers=do_worker).json()
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"photos": [ph["photoId"]]}}, headers=do_worker)
    assert r.status_code == 400 and "The price on the tag" in r.json()["message"]
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"photos": [ph["photoId"]], "text": "$4.29 store brand"}}, headers=do_worker)
    assert r.status_code == 200
    # the field itself is validated when the task is posted
    bad = {"type": "do", "title": "x", "payload": {"category": "documents_and_receipts", "instructions": "Photograph the thing and keep the code in the shot.", "proof": "photos", "write": "ab"}}
    assert client.post("/v1/tasks", json=bad).status_code == 400


def test_operator_sees_every_response_with_the_photos_and_approves(client, app, do_worker, settings):  # noqa: F811
    settings.admin_token = "adm"
    t = photo_task(client)
    ph = send_photo_proof(client, do_worker, t["taskId"])
    # nobody else can see the list
    assert client.get("/v1/admin/responses").status_code == 401
    assert client.get("/v1/admin/responses", headers={"Authorization": "Bearer wrong"}).status_code == 401
    out = client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()
    assert out["waiting"] == 1
    row = out["responses"][0]
    assert row["taskId"] == t["taskId"] and row["decision"] == "waiting" and row["awaitingOperator"] is True
    assert row["text"].startswith("Mon to Fri") and row["code"] and row["write"] == "The hours for each day, as printed"
    assert row["photos"][0]["photoId"] == ph["photoId"] and row["photos"][0]["url"].endswith(f"/v1/photos/{ph['photoId']}")
    assert row["worker"]["wallet"] and row["price"] == 20_000_000
    # the photo link works with the operator key
    assert client.get(f"/v1/photos/{ph['photoId']}", headers=ADMIN).status_code == 200
    # approve: the worker is paid, the record says the operator looked
    r = client.post(f"/v1/admin/responses/{t['taskId']}", json={"decision": "approve", "note": "code visible, hours readable"}, headers=ADMIN).json()
    assert r["state"] == "done" and r["decision"] == "approved"
    v = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert v["state"] == "done" and v["verification"]["operatorNote"] == "code visible, hours readable"
    assert any(c["name"] == "decision" and "operator" in c["detail"] for c in v["verification"]["checks"])
    assert client.get("/v1/workers/earnings", headers=do_worker).json()["pending"] == 20_000_000
    row = client.get("/v1/admin/responses?status=approved", headers=ADMIN).json()["responses"][0]
    assert row["taskId"] == t["taskId"] and row["decision"] == "approved"
    assert client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()["responses"] == []
    # decided once
    assert client.post(f"/v1/admin/responses/{t['taskId']}", json={"decision": "refuse"}, headers=ADMIN).status_code == 409
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_operator_refuses_a_photo_and_nobody_is_paid(client, app, do_worker, settings):  # noqa: F811
    settings.admin_token = "adm"
    t = photo_task(client)
    send_photo_proof(client, do_worker, t["taskId"], text="could not read it")
    r = client.post(f"/v1/admin/responses/{t['taskId']}", json={"decision": "refuse", "note": "no code in the shot"}, headers=ADMIN).json()
    assert r["state"] == "expired" and r["decision"] == "refused"
    assert client.get("/v1/workers/earnings", headers=do_worker).json()["pending"] == 0
    v = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert v["state"] == "expired" and v["refund"] == 24_000_000
    row = client.get("/v1/admin/responses?status=refused", headers=ADMIN).json()["responses"][0]
    assert row["taskId"] == t["taskId"] and row["decision"] == "refused"
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == 0


def test_operator_decides_a_disputed_response_too(client, app, do_worker, settings):  # noqa: F811
    settings.admin_token = "adm"
    t = photo_task(client)
    send_photo_proof(client, do_worker, t["taskId"])
    d = client.post(f"/v1/tasks/{t['taskId']}/accept", json={"buyerToken": t["buyerToken"], "reject": True, "reason": "I cannot read the sign in this"}).json()
    assert d["status"] == "open"
    row = client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()["responses"][0]
    assert row["decision"] == "disputed" and row["dispute"]["disputeId"] == d["disputeId"]
    r = client.post(f"/v1/admin/responses/{t['taskId']}", json={"decision": "approve", "note": "readable at full size"}, headers=ADMIN).json()
    assert r["state"] == "done"
    assert client.get("/v1/workers/earnings", headers=do_worker).json()["pending"] == 20_000_000


def test_the_assistant_never_approves_a_picture(client, app, do_worker, settings):  # noqa: F811
    settings.echo_worker, settings.admin_token, settings.ai_gateway_api_key, settings.verifier_enabled = False, "adm", "gw", True
    app.state.jobs.scout_http = gateway("right")
    t = photo_task(client)
    send_photo_proof(client, do_worker, t["taskId"])
    out = client.post("/v1/admin/verifier/run", headers=ADMIN).json()
    assert out["reviewed"] == 1 and out["approved"] == 0 and out["to_person"] == 1
    v = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert v["state"] == "submitted" and v["review"]["verdict"] == "right"
    row = client.get("/v1/admin/responses?status=waiting", headers=ADMIN).json()["responses"][0]
    assert row["review"]["verdict"] == "right"  # shown next to the pictures as advice


def test_typed_proof_still_accepts_after_the_window(client, app, do_worker, settings):  # noqa: F811
    settings.echo_worker = False
    body = {"type": "do", "title": "Call and ask", "payload": {"category": "calls", "instructions": "Call the library and ask the Saturday hours. Write who answered and what they said.", "proof": "text"}}
    t = pay(client, body).json()
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=do_worker)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "A staff member said 10 to 5 on Saturdays. Called at 2:10 pm."}}, headers=do_worker)
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["acceptBy"] > time.time()
    age_answer(app)
    assert app.state.jobs.tick()["accepted"] == 1
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "done"


def test_the_catalogue_is_mostly_typed_work_and_every_photo_task_asks_for_text():
    items = house.catalogue()
    pictures = [c for c in items if c["type"] == "do" and c["payload"].get("proof", "text") in PICTURE_PROOFS]
    typed = [c for c in items if c not in pictures]
    assert len(typed) > len(pictures) * 1.5
    for c in pictures:
        if c["payload"]["proof"] == "photos":
            assert 3 <= len(c["payload"]["write"]) <= 300, c["title"]
    from humanapi_api.manual_tasks import manual_tasks

    assert len(manual_tasks()) >= 60
    assert all(c["payload"].get("proof", "text") == "text" for c in manual_tasks() if c["type"] == "do")


def test_a_house_batch_has_at_most_one_picture_task(client, app, settings):
    settings.echo_worker, settings.admin_token, settings.house_batch_size, settings.house_pictures_per_batch = False, "adm", 6, 1
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 2_000_000_000}, headers=ADMIN)
    for _ in range(3):
        assert client.post("/v1/admin/house/post", headers=ADMIN).json()["posted"] == 6
        with app.state.db.session() as s:
            open_ = s.query(Task).filter(Task.state == "open").all()
            pictures = [t for t in open_ if t.type == "do" and (t.payload or {}).get("proof", "text") in PICTURE_PROOFS]
            assert len(pictures) <= 3  # one per batch so far
            for t in open_:
                t.state = "cancelled"  # make room for the next batch


def test_admin_page_login_gives_the_token(client, settings):
    settings.admin_token = "adm"
    assert client.post("/v1/admin/login", json={"user": "admin", "password": "nope"}).status_code == 401
    assert client.post("/v1/admin/login", json={"user": "someone", "password": "adm"}).status_code == 401
    r = client.post("/v1/admin/login", json={"user": "admin", "password": "adm"}).json()
    assert r["token"] == "adm" and r["user"] == "admin"
    settings.admin_password = "secret"
    assert client.post("/v1/admin/login", json={"user": "admin", "password": "adm"}).status_code == 401
    assert client.post("/v1/admin/login", json={"user": "admin", "password": "secret"}).json()["token"] == "adm"
