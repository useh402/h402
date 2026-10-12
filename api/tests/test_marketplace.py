import time

from conftest import PAYER, RH_NET, pay, verify_body
from test_workers import qualify, sign_in_evm

from humanapi_api import ledger
from humanapi_api.models import Task
from humanapi_api.pricing import normalize_location, parse_task

DO = {"type": "do", "title": "Check the price board at Jewel-Osco", "location": "Chicago, IL", "acceptance": "The photo must show the tag; write the price.", "difficulty": "medium", "effortMinutes": 20, "templateId": "HUM-036", "payload": {"category": "go_and_see", "instructions": "Go to any Jewel-Osco in Chicago and photograph the shelf price tag for a gallon of whole milk.", "proof": "both"}}


def client_sign_in(client, wallet=PAYER):
    r = client.post("/v1/clients/dev-session", json={"wallet": wallet, "network": RH_NET})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_spec_fields_and_location_rules(client):
    r = parse_task(DO)
    assert r.title.startswith("Check the price") and r.location == "Chicago, IL" and r.difficulty == "medium" and r.effortMinutes == 20
    assert parse_task(verify_body()).title.startswith("Is the total legible") and parse_task(verify_body()).location == "Remote"
    assert normalize_location("austin, tx") == "Austin, TX" and normalize_location(None) == "Remote"
    import pytest

    with pytest.raises(ValueError):
        normalize_location("Paris, FR")
    bad = client.post("/v1/tasks", json={**DO, "location": "Paris, FR"})
    assert bad.status_code == 400
    t = pay(client, DO).json()
    assert t["title"] == DO["title"] and t["location"] == "Chicago, IL" and t["templateId"] == "HUM-036" and t["effortMinutes"] == 20


def test_feed_filters_and_location(client, settings):
    settings.echo_worker = False
    settings.dev_login = True
    pay(client, DO)
    pay(client, verify_body(reference="remote one"))
    h, _ = sign_in_evm(client)
    client.post("/v1/workers/profile", json={"acceptTerms": True}, headers=h)
    client.post("/v1/workers/qualification/do", json={"answers": [1, 1, 1]}, headers=h)
    qualify(client, h)
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    assert {c["location"] for c in feed} == {"Chicago, IL", "Remote"}
    assert feed[0]["title"] == DO["title"] and feed[0]["acceptance"].startswith("The photo") and feed[0]["difficulty"] == "medium"
    only_do = client.get("/v1/workers/tasks?type=do", headers=h).json()["tasks"]
    assert [c["type"] for c in only_do] == ["do"]
    by_cat = client.get("/v1/workers/tasks?category=go_and_see", headers=h).json()["tasks"]
    assert len(by_cat) == 1
    pricey = client.get("/v1/workers/tasks?minPrice=500000", headers=h).json()["tasks"]
    assert [c["type"] for c in pricey] == ["do"]
    # a worker in Austin does not see a Chicago task; remote tasks stay
    client.post("/v1/workers/profile", json={"location": "Austin, TX"}, headers=h)
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    assert {c["location"] for c in feed} == {"Remote"}
    client.post("/v1/workers/profile", json={"location": "chicago, il"}, headers=h)
    assert client.get("/v1/workers/me", headers=h).json()["location"] == "Chicago, IL"
    assert len(client.get("/v1/workers/tasks", headers=h).json()["tasks"]) == 2


def test_client_console_endpoints(client, app, settings):
    settings.dev_login = True
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    h = client_sign_in(client)
    me = client.get("/v1/clients/me", headers=h).json()
    assert me["wallet"] == PAYER.lower() and me["tasksPaid"] == 1
    client.post("/v1/clients/profile", json={"name": "Acme Research"}, headers=h)
    lst = client.get("/v1/clients/tasks", headers=h).json()
    assert lst["counts"]["open"] == 1 and lst["spent"] == 288_000 and lst["tasks"][0]["buyerToken"] == t["buyerToken"]
    one = client.get(f"/v1/clients/tasks/{t['taskId']}", headers=h).json()
    assert one["payload"]["question"] and one["receipt"]["payment"]["amount"] == 288_000
    other = client_sign_in(client, "0x0000000000000000000000000000000000000b0b")
    assert client.get(f"/v1/clients/tasks/{t['taskId']}", headers=other).status_code == 404
    # cancel with the session, no buyerToken needed
    r = client.post(f"/v1/tasks/{t['taskId']}/cancel", json={"reason": "posted by mistake"}, headers=h).json()
    assert r["state"] == "cancelled" and r["refund"] == 288_000 and r["verification"]["outcome"] == "cancelled"
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["refund_due"] == 288_000
    assert client.get("/v1/clients/tasks", headers=h).json()["refundsDue"] == 288_000
    # another client cannot cancel
    t2 = pay(client, verify_body(reference="two")).json()
    assert client.post(f"/v1/tasks/{t2['taskId']}/cancel", json={}, headers=other).status_code == 403
    assert client.post(f"/v1/tasks/{t2['taskId']}/cancel", json={}).status_code == 403


def test_cannot_cancel_after_an_answer(client, settings):
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    h, _ = sign_in_evm(client)
    qualify(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes"}, headers=h)
    r = client.post(f"/v1/tasks/{t['taskId']}/cancel", json={"buyerToken": t["buyerToken"]})
    assert r.status_code == 409


def test_verification_record_on_completion(client, app):
    t = pay(client, verify_body()).json()
    app.state.jobs.tick()
    v = client.get(f"/v1/tasks/{t['taskId']}").json()["verification"]
    assert v["method"].startswith("independent agreement") and v["outcome"] == "approved"
    names = [c["name"] for c in v["checks"]]
    assert names == ["answers received", "answers valid for the type", "agreement", "paid"] and all(c["passed"] for c in v["checks"])
    assert client.get(f"/v1/receipts/{t['taskId']}").json()["verification"]["outcome"] == "approved"


def test_verification_record_on_expiry_and_proof(client, app, settings):
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    v = client.get(f"/v1/tasks/{t['taskId']}").json()["verification"]
    assert v["outcome"] == "no_answers" and v["checks"][-1]["name"] == "refund"
    d = pay(client, DO).json()
    h, _ = sign_in_evm(client)
    client.post("/v1/workers/profile", json={"acceptTerms": True, "location": "Chicago, IL"}, headers=h)
    client.post("/v1/workers/qualification/do", json={"answers": [1, 1, 1]}, headers=h)
    client.post(f"/v1/tasks/{d['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{d['taskId']}/answer", json={"answer": {"text": "Price tag shows $3.49 for a gallon.", "screenshot": "https://example.com/tag.jpg"}}, headers=h)
    done = client.post(f"/v1/tasks/{d['taskId']}/accept", json={"buyerToken": d["buyerToken"]}).json()
    assert done["verification"]["method"] == "client acceptance" and done["verification"]["checks"][2]["detail"].startswith("accepted by the client")
