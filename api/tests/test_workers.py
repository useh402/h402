import time

from conftest import RH_NET, SOL_NET, pay, verify_body
from eth_account import Account
from eth_account.messages import encode_defunct
from solders.keypair import Keypair

from humanapi_api import ledger
from humanapi_api.models import Task


def sign_in_evm(client):
    acct = Account.create()
    n = client.post("/v1/workers/nonce", json={"wallet": acct.address, "network": RH_NET}).json()
    sig = Account.sign_message(encode_defunct(text=n["message"]), acct.key).signature.hex()
    r = client.post("/v1/workers/session", json={"wallet": acct.address.lower(), "network": RH_NET, "nonce": n["nonce"], "signature": sig})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, acct


def sign_in_sol(client):
    import base58

    kp = Keypair()
    n = client.post("/v1/workers/nonce", json={"wallet": str(kp.pubkey()), "network": SOL_NET}).json()
    sig = base58.b58encode(bytes(kp.sign_message(n["message"].encode()))).decode()
    r = client.post("/v1/workers/session", json={"wallet": str(kp.pubkey()), "network": SOL_NET, "nonce": n["nonce"], "signature": sig})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, kp


def qualify(client, h, kind="verify"):
    client.post("/v1/workers/profile", json={"acceptTerms": True, "languages": ["en"]}, headers=h)
    samples = client.get(f"/v1/workers/qualification/{kind}", headers=h).json()["samples"]
    assert len(samples) == 3
    answers = {"verify": ["yes", "no", "no"], "choose": [1, 1, 1], "rate": [1, 5, 2]}[kind]
    r = client.post(f"/v1/workers/qualification/{kind}", json={"answers": answers}, headers=h)
    assert r.json()["passed"] is True, r.text


def test_sign_in_both_rails_and_bad_signature(client):
    h, acct = sign_in_evm(client)
    me = client.get("/v1/workers/me", headers=h).json()
    assert me["wallet"] == acct.address and me["rail"] == "robinhood" and me["qualifiedTypes"] == []
    h2, kp = sign_in_sol(client)
    assert client.get("/v1/workers/me", headers=h2).json()["rail"] == "solana"
    n = client.post("/v1/workers/nonce", json={"wallet": acct.address, "network": RH_NET}).json()
    bad = client.post("/v1/workers/session", json={"wallet": acct.address, "network": RH_NET, "nonce": n["nonce"], "signature": "0x" + "11" * 65})
    assert bad.status_code == 401
    again = client.post("/v1/workers/session", json={"wallet": acct.address, "network": RH_NET, "nonce": n["nonce"], "signature": "0x" + "11" * 65})
    assert again.status_code == 401
    assert client.get("/v1/workers/me").status_code == 401
    assert client.get("/v1/workers/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_dev_login_is_local_only(client, settings):
    assert client.post("/v1/workers/dev-session", json={"wallet": "0x" + "ab" * 20, "network": RH_NET}).status_code == 404
    settings.dev_login = True
    assert client.post("/v1/workers/dev-session", json={"wallet": "0x" + "ab" * 20, "network": RH_NET}).status_code == 200


def test_qualification_gates_the_feed(client, settings):
    settings.echo_worker = False
    h, _ = sign_in_evm(client)
    pay(client, verify_body())
    assert client.get("/v1/workers/tasks", headers=h).json()["tasks"] == []
    r = client.post("/v1/workers/qualification/verify", json={"answers": ["yes", "no", "no"]}, headers=h)
    assert r.status_code == 403  # terms first
    client.post("/v1/workers/profile", json={"acceptTerms": True}, headers=h)
    r = client.post("/v1/workers/qualification/verify", json={"answers": ["no", "no", "no"]}, headers=h).json()
    assert r["passed"] is False and r["correct"] == 2 - 0 or r["correct"] in (1, 2)
    qualify(client, h)
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    assert len(feed) == 1 and feed[0]["type"] == "verify" and feed[0]["price"] == 80_000 and "payload" not in feed[0]
    assert client.get("/v1/pricing").json()["availability"]["byType"]["verify"] == 1


def test_claim_answer_consensus_and_earnings(client, app, settings):
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    heads = []
    for _ in range(3):
        h, _ = sign_in_evm(client)
        qualify(client, h)
        heads.append(h)
    # claim shows the payload and holds a slot
    c = client.post(f"/v1/tasks/{t['taskId']}/claim", headers=heads[0]).json()
    assert c["held"] and c["payload"]["question"].startswith("Is the total")
    assert client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "maybe"}, headers=heads[0]).status_code == 400
    assert client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes"}, headers=heads[1]).json()["error"] == "no_hold"
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes", "note": "clear"}, headers=heads[0]).json()
    assert r["accepted"] and r["state"] == "submitted"
    # answered tasks leave the feed for that worker, stay for others
    assert client.get("/v1/workers/tasks", headers=heads[0]).json()["tasks"] == []
    assert len(client.get("/v1/workers/tasks", headers=heads[1]).json()["tasks"]) == 1
    for h, value in zip(heads[1:], ["yes", "no"], strict=True):
        client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
        r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": value}, headers=h).json()
    assert r["state"] == "done" and r["agreed"] is False
    e0 = client.get("/v1/workers/earnings", headers=heads[0]).json()
    e2 = client.get("/v1/workers/earnings", headers=heads[2]).json()
    assert e0["pending"] == 80_000 and e0["today"] == 80_000 and e0["agreed"] == 1
    assert e2["pending"] == 0 and e2["answered"] == 1 and e2["agreed"] == 0
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["worker_due"] == 160_000 and inv["liabilities"]["refund_due"] == 80_000


def test_slots_and_hold_expiry(client, app, settings):
    settings.echo_worker = False
    t = pay(client, verify_body(workers=1)).json()
    h1, _ = sign_in_evm(client)
    h2, _ = sign_in_evm(client)
    qualify(client, h1)
    qualify(client, h2)
    assert client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h1).status_code == 200
    assert client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h2).json()["error"] == "fully_claimed"
    assert client.get("/v1/workers/tasks", headers=h2).json()["tasks"] == []
    with app.state.db.session() as s:
        from humanapi_api.models import Claim

        for c in s.query(Claim).all():
            c.expires_at = time.time() - 1
    assert app.state.jobs.tick()["holds"] == 1
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "open"
    assert len(client.get("/v1/workers/tasks", headers=h2).json()["tasks"]) == 1
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h2)
    client.post(f"/v1/tasks/{t['taskId']}/release", headers=h2)
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["state"] == "open"


def test_choose_and_rate_answers(client, settings):
    settings.echo_worker = False
    t = pay(client, {"type": "rate", "payload": {"item": "x", "rubric": "y"}, "workers": 1}).json()
    h, _ = sign_in_evm(client)
    qualify(client, h, "rate")
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    assert client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": 9}, headers=h).status_code == 400
    r = client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": 4}, headers=h).json()
    assert r["state"] == "done" and r["agreed"] is True
    assert client.get(f"/v1/tasks/{t['taskId']}").json()["result"]["answer"] == 4


def test_deadline_passes_with_one_answer_pays_that_worker(client, app, settings):
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    h, _ = sign_in_evm(client)
    qualify(client, h)
    client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "yes"}, headers=h)
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    view = client.get(f"/v1/tasks/{t['taskId']}").json()
    assert view["state"] == "done" and view["agreement"] == 1.0
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["liabilities"]["worker_due"] == 80_000 and inv["liabilities"]["refund_due"] == 288_000 - 80_000 - 16_000
