from conftest import pay, verify_body


def test_stats_and_activity(client, app):
    assert client.get("/v1/stats").json()["open"] == 0
    t = pay(client, verify_body()).json()
    st = client.get("/v1/stats").json()
    assert st["open"] == 1 and st["openValue"] == 240_000 and st["lowestPrice"] == 80_000 and st["feeBps"] == 2000
    board = client.get("/v1/tasks/open").json()["tasks"][0]
    assert board["image"].startswith("https://") and board["slotsLeft"] == 3
    app.state.jobs.tick()
    st = client.get("/v1/stats").json()
    assert st["open"] == 0 and st["done24h"] == 1 and st["paid24h"] == 240_000
    act = client.get("/v1/activity").json()["activity"]
    assert act[0]["taskId"] == t["taskId"] and act[0]["state"] == "done" and act[0]["method"].startswith("independent")
