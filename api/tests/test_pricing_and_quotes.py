from conftest import RH_NET, SOL_NET, decode_header, verify_body

from humanapi_api.pricing import TaskRequest, parse_task, quote_task


def test_quote_math_and_defaults():
    r = parse_task(verify_body())
    assert r.workers == 3 and r.pricePerWorker == 80_000 and r.timeLimitSeconds == 120
    q = quote_task(r, 2000)
    assert q == {"workerPool": 240_000, "fee": 48_000, "total": 288_000}
    q = quote_task(TaskRequest(type="rate", payload={}).model_copy(update={"workers": 1, "pricePerWorker": 50_001}), 2000)
    assert q["fee"] == 10_001  # rounds up


def test_validation_messages():
    import pytest

    with pytest.raises(ValueError, match="unknown task type"):
        parse_task({"type": "nope", "payload": {}})
    with pytest.raises(ValueError, match="below the minimum"):
        parse_task(verify_body(pricePerWorker=1))
    with pytest.raises(ValueError, match="allows workers"):
        parse_task(verify_body(workers=4))
    with pytest.raises(ValueError, match="options"):
        parse_task({"type": "choose", "payload": {"question": "q", "options": ["a"]}})
    assert parse_task({"type": "answer", "payload": {"question": "q"}}).minReputation == 0.9


def test_pricing_endpoint(client):
    data = client.get("/v1/pricing").json()
    assert data["platformFeeBps"] == 2000
    assert data["types"]["verify"]["exampleTotal"] == 288_000
    assert [r["network"] for r in data["rails"]] == [RH_NET, SOL_NET]


def test_402_shape(client):
    r = client.post("/v1/tasks", json=verify_body())
    assert r.status_code == 402
    pr = decode_header(r.headers["PAYMENT-REQUIRED"])
    assert pr["x402Version"] == 2 and pr["resource"]["url"] == "http://api.test/v1/tasks"
    nets = {a["network"]: a for a in pr["accepts"]}
    assert nets[RH_NET]["amount"] == "288000" and nets[RH_NET]["extra"] == {"assetTransferMethod": "permit2"}
    assert nets[SOL_NET]["extra"]["feePayer"].startswith("EmHQ") and nets[SOL_NET]["payTo"].startswith("CK5b")
    body = r.json()
    assert body["quote"]["total"] == 288_000 and body["x402"]["accepts"] == pr["accepts"]
    again = client.post("/v1/tasks", json=verify_body())
    assert again.json()["quote"]["id"] == body["quote"]["id"]  # same body, same live quote


def test_bad_bodies(client):
    assert client.post("/v1/tasks", json={"type": "verify"}).status_code == 400
    assert client.post("/v1/tasks", content=b"x", headers={"content-type": "application/json"}).status_code == 400
    assert client.post("/v1/tasks/batch", json={"tasks": []}).status_code == 400
