import time

import pytest
from conftest import pay
from test_workers import qualify, sign_in_evm

from humanapi_api import house
from humanapi_api.pricing import US_STATES, parse_task, standard_price
from humanapi_api.verifier import build_messages

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
ADMIN = {"Authorization": "Bearer adm"}
AUSTIN = {"lat": 30.2655, "lng": -97.7527}


def photo_task(client, geo=None, workers=1):
    payload = {"category": "go_and_see" if geo else "documents_and_receipts", "instructions": "Photograph the hours sign at the main entrance. Write the capture code on paper and keep it in the shot.", "proof": "photos"}
    if geo:
        payload["geo"] = geo
    body = {"type": "do", "title": "Photograph the posted hours at the library", "payload": payload, "workers": workers, "pricePerWorker": 20_000_000, "location": "Austin, TX" if geo else "Remote", "timeLimitSeconds": 3600}
    return pay(client, body).json()


def ready_worker(client):
    h, acct = sign_in_evm(client)
    qualify(client, h, "verify")
    client.post("/v1/workers/profile", json={"acceptTerms": True, "languages": ["en"]}, headers=h)
    return h, acct


@pytest.fixture
def do_worker(client, app):
    h, acct = sign_in_evm(client)
    with app.state.db.session() as s:
        from sqlalchemy import func

        from humanapi_api.models import Worker

        w = s.query(Worker).filter(func.lower(Worker.wallet) == acct.address.lower()).one()
        w.qualified_types, w.terms_accepted_at, w.reputation = ["do"], time.time(), 1.0
    return h


def test_photo_task_gives_a_capture_code_and_needs_photos_from_the_right_place(client, app, do_worker, settings):
    settings.admin_token = "adm"
    t = photo_task(client, geo=AUSTIN)
    card = client.post(f"/v1/tasks/{t['taskId']}/claim", headers=do_worker).json()
    code = card["captureCode"]
    assert len(code) == 4 and all(c in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" for c in code)
    # a text file is not a photo
    r = client.post(f"/v1/tasks/{t['taskId']}/photos", content=b"hello", headers={**do_worker, "x-photo-lat": "30.2655", "x-photo-lng": "-97.7527"})
    assert r.status_code == 400 and r.json()["error"] == "not_a_photo"
    # no location on a go-and-see task
    r = client.post(f"/v1/tasks/{t['taskId']}/photos", content=JPEG, headers=do_worker)
    assert r.status_code == 400 and r.json()["error"] == "location_needed"
    # the wrong place: Dallas
    r = client.post(f"/v1/tasks/{t['taskId']}/photos", content=JPEG, headers={**do_worker, "x-photo-lat": "32.7767", "x-photo-lng": "-96.7970", "x-photo-accuracy": "20"})
    assert r.status_code == 409 and r.json()["error"] == "wrong_place"
    # at the library
    r = client.post(f"/v1/tasks/{t['taskId']}/photos", content=JPEG, headers={**do_worker, "x-photo-lat": "30.2660", "x-photo-lng": "-97.7530", "x-photo-accuracy": "15"})
    assert r.status_code == 200, r.text
    ph = r.json()
    assert ph["contentType"] == "image/jpeg" and ph["distanceM"] < 100 and ph["code"] == code
    # the photo is private: the worker, the client and the operator can see it, nobody else
    assert client.get(f"/v1/photos/{ph['photoId']}").status_code == 403
    assert client.get(f"/v1/photos/{ph['photoId']}", headers=do_worker).status_code == 200
    assert client.get(f"/v1/photos/{ph['photoId']}", headers=ADMIN).status_code == 200
    assert client.get(f"/v1/photos/{ph['photoId']}?token={t['buyerToken']}").status_code == 200
    # the answer must list photos taken for this task
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "Open 10 to 6", "photos": ["ph_nope"]}}, headers=do_worker)
    assert r.status_code == 400
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": {"text": "Open 10 to 6", "photos": [ph["photoId"]]}}, headers=do_worker)
    assert r.status_code == 200, r.text
    # the public view shows that photos exist, not the photos
    c = client.get(f"/v1/tasks/{t['taskId']}/comments").json()
    assert c["comments"] == [] or c["hidden"] == 1  # not decided yet, so hidden
    mine = client.get(f"/v1/tasks/{t['taskId']}/comments", headers=do_worker).json()["comments"][0]
    assert mine["response"]["photoCount"] == 1 and mine["response"]["photos"] == [ph["photoId"]]


def test_at_most_three_photos_and_photos_belong_to_the_claim(client, do_worker, settings):
    t = photo_task(client)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=do_worker)
    ids = [client.post(f"/v1/tasks/{t['taskId']}/photos", content=JPEG, headers=do_worker).json()["photoId"] for _ in range(3)]
    r = client.post(f"/v1/tasks/{t['taskId']}/photos", content=JPEG, headers=do_worker)
    assert r.status_code == 409 and r.json()["error"] == "too_many"
    other = photo_task(client)
    client.post(f"/v1/tasks/{other['taskId']}/claim", headers=do_worker)
    r = client.post(f"/v1/tasks/{other['taskId']}/answer", json={"answer": {"photos": ids[:1]}}, headers=do_worker)
    assert r.status_code == 400  # taken for a different task


def test_verifier_is_told_the_code_and_shown_the_photos():
    item = {"title": "Photograph the sign", "type": "do", "acceptance": "", "payload": {"instructions": "x", "proof": "photos"}, "requester": None}
    msgs, has_image = build_messages(item, [{"value": {"text": "done", "photos": ["ph_1"], "code": "K7QM"}, "note": ""}], photo_url=lambda pid: f"data:image/jpeg;base64,AAAA{pid}")
    parts = msgs[1]["content"]
    assert has_image and any(p.get("type") == "image_url" and "ph_1" in p["image_url"]["url"] for p in parts)
    assert any("K7QM" in p.get("text", "") for p in parts)


def test_photo_tasks_in_the_catalogue_are_valid_us_tasks_with_real_rewards():
    photo = [c for c in house.catalogue() if c["payload"].get("proof") == "photos"]
    assert len(photo) >= 20
    for c in photo:
        r = parse_task(c)
        assert r.location == "Remote" or r.location[-2:] in US_STATES
        if r.payload["category"] == "go_and_see":
            assert standard_price(r) >= 25_000_000 and (r.location == "Remote" or "geo" in r.payload)
        else:
            assert standard_price(r) >= 5_000_000


def test_gas_help_only_after_a_paid_task_and_once_a_day(client, app, fac):
    from humanapi_api.models import Payout, Worker

    h, acct = sign_in_evm(client)
    r = client.post("/v1/workers/gas", headers=h)
    assert r.status_code == 403 and r.json()["error"] == "not_yet"
    with app.state.db.session() as s:
        w = s.query(Worker).one()
        s.add(Payout(id="po_x", rail="robinhood", worker_id=w.id, task_id=None, amount=1_000_000, status="sent", kind="bonus"))
    r = client.post("/v1/workers/gas", headers=h)
    assert r.status_code == 200 and r.json()["granted"] and r.json()["transaction"] == "0xgas"
    assert fac.calls[-1][0] == "/gas" and fac.calls[-1][1]["address"].lower() == acct.address.lower()
    r = client.post("/v1/workers/gas", headers=h)
    assert r.status_code == 429
