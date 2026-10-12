from conftest import pay, verify_body

from humanapi_api.house import catalogue
from humanapi_api.pricing import parse_task

ADMIN = {"Authorization": "Bearer adm"}


def test_requester_validation_and_listing(client):
    bad = client.post("/v1/tasks", json={**verify_body(), "requester": "siri"})
    assert bad.status_code == 400
    t = pay(client, {**verify_body(), "requester": "Claude"}).json()
    assert t["requester"] == "claude"
    d = client.get(f"/v1/tasks/open/{t['taskId']}").json()
    assert d["open"] and d["payload"]["question"] and d["requirements"]["qualification"] == "verify" and d["requirements"]["paidWhen"].startswith("your answer agrees")
    assert d["slotsLeft"] == 3 and d["image"].startswith("https://")
    assert client.get("/v1/tasks/open").json()["tasks"][0]["requester"] == "claude"
    assert client.get("/v1/tasks/open/task_nope").status_code == 404


def test_house_tasks_rotate_requesters(client, settings):
    settings.admin_token = "adm"
    settings.house_batch_size = 5
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 2_000_000_000}, headers=ADMIN)
    client.post("/v1/admin/house/post", headers=ADMIN)
    reqs = {t["requester"] for t in client.get("/v1/tasks/open").json()["tasks"]}
    assert reqs == {"claude", "chatgpt", "gemini", "grok", "deepseek"}
    assert all(parse_task({"timeLimitSeconds": 2400, **c}) for c in catalogue()[:3])
