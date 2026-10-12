import time

from conftest import pay, verify_body
from test_workers import sign_in_evm

from humanapi_api import ledger
from humanapi_api.house import catalogue
from humanapi_api.models import Task

ADMIN = {"Authorization": "Bearer adm"}


def test_catalogue_is_us_only_and_valid():
    from humanapi_api.pricing import parse_task

    items = catalogue()
    assert len(items) > 100
    for c in items:
        r = parse_task({"timeLimitSeconds": 2400, **c})
        assert r.location == "Remote" or r.location.endswith(tuple(f", {st}" for st in ("AZ", "IL", "NY", "TX", "CA", "CO", "GA", "WA", "OR", "MA", "FL", "PA", "TN", "MI", "MN", "DC")))
        assert "india" not in (r.title + str(r.payload)).lower()


def test_house_funding_posting_and_ledger(client, app, settings):
    settings.house_payout = "contract"  # the prefunded path
    settings.echo_worker = False
    settings.admin_token = "adm"
    settings.house_poster_enabled = True
    settings.house_batch_size = 3
    # nothing to spend yet
    r = client.post("/v1/admin/house/post", headers=ADMIN).json()
    assert r["posted"] == 0 and r["skipped"] == "house balance too low"
    d = client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 2_000_000_000}, headers=ADMIN).json()
    assert d["houseBalance"] == 2_000_000_000
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["house"] == 2_000_000_000 and inv["escrow"] == 2_000_000_000
    r = client.post("/v1/admin/house/post", headers=ADMIN).json()
    assert r["posted"] == 3 and r["houseBalance"] < 2_000_000_000
    assert all(t["deadline"] - t["postedAt"] >= 86000 for t in client.get("/v1/tasks/open").json()["tasks"])  # listed for a day
    board = client.get("/v1/tasks/open").json()
    assert board["count"] == 3 and all(b["title"] for b in board["tasks"]) and "payload" not in board["tasks"][0]
    st = client.get("/v1/admin/house", headers=ADMIN).json()
    assert st["openHouseTasks"] == 3 and st["spentToday"] == 2_000_000_000 - r["houseBalance"]
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["task"] == st["spentToday"] and inv["liabilities"]["payer"] == 0
    # same titles are not reposted while open, and no template dominates the board
    r2 = client.post("/v1/admin/house/post", headers=ADMIN).json()
    board = client.get("/v1/tasks/open").json()["tasks"]
    titles = {t["title"] for t in board}
    assert r2["posted"] == 3 and len(titles) == 6
    for _ in range(10):
        client.post("/v1/admin/house/post", headers=ADMIN)
    with app.state.db.session() as s:
        from collections import Counter

        counts = Counter((t.template_id or t.title) for t in s.query(Task).filter(Task.state == "open").all())
        assert max(counts.values()) <= 2


def test_house_task_expiry_returns_money_to_the_house(client, app, settings):
    settings.house_payout = "contract"  # the prefunded path
    settings.echo_worker = False
    settings.admin_token = "adm"
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 1_000_000_000}, headers=ADMIN)
    client.post("/v1/admin/house/post", headers=ADMIN)
    with app.state.db.session() as s:
        for t in s.query(Task).all():
            t.deadline = time.time() - 1
    app.state.jobs.tick()
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["balanced"] and inv["liabilities"]["house"] == 1_000_000_000 and inv["liabilities"]["refund_due"] == 0 and inv["liabilities"]["task"] == 0
    assert client.get("/v1/admin/house", headers=ADMIN).json()["houseBalance"] == 1_000_000_000


def test_house_task_can_be_solved_and_paid(client, app, settings):
    settings.echo_worker = False
    settings.admin_token = "adm"
    settings.house_batch_size = 1
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 1_000_000_000}, headers=ADMIN)
    def plain():  # this test answers in writing and lets the window accept it, so it needs typed proof: pictures wait for the operator
        return [t for t in client.get("/v1/tasks/open").json()["tasks"] if t["type"] != "do" or t.get("proof", "text") == "text"]

    for _ in range(8):
        client.post("/v1/admin/house/post", headers=ADMIN)
        if plain():
            break
    task = plain()[0]
    h, _ = sign_in_evm(client)
    client.post("/v1/workers/profile", json={"acceptTerms": True, "location": task["location"] if task["location"] != "Remote" else ""}, headers=h)
    for kind, ans in {"verify": ["yes", "no", "no"], "choose": [1, 1, 1], "rate": [1, 5, 2], "read": ["INVOICE 2031 TOTAL 48.00", "Gate B12 Boarding 09:40", "Lot 7 Row 3"], "label": [["complaint"], ["question"], ["praise"]], "answer": ["56", "april", "7"], "do": [1, 1, 1]}.items():
        client.post(f"/v1/workers/qualification/{kind}", json={"answers": ans}, headers=h)
    feed = client.get("/v1/workers/tasks", headers=h).json()["tasks"]
    assert any(c["taskId"] == task["taskId"] for c in feed)
    if task["type"] == "do":
        client.post(f"/v1/tasks/{task['taskId']}/claim", headers=h)
        r = client.post(f"/v1/tasks/{task['taskId']}/answer", json={"answer": {"text": "Done. Found what was asked and wrote it here.", "screenshot": "https://example.com/x.jpg"}}, headers=h).json()
        assert r["state"] == "submitted"
        with app.state.db.session() as s:
            from humanapi_api.models import Answer

            s.query(Answer).first().submitted_at = time.time() - 3700
        app.state.jobs.tick()
        assert client.get(f"/v1/tasks/{task['taskId']}").json()["state"] == "done"
        assert client.get("/v1/workers/earnings", headers=h).json()["pending"] == task["price"]
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_external_payers_still_get_refund_rows(client, app, settings):
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    with app.state.db.session() as s:
        s.get(Task, t["taskId"]).deadline = time.time() - 1
    app.state.jobs.tick()
    with app.state.db.session() as s:
        inv = ledger.check_invariant(s, "robinhood")
        assert inv["liabilities"]["refund_due"] == 288_000 and inv["liabilities"]["house"] == 0


def test_the_pool_is_never_blocked_by_its_own_moderation(client, app, settings):
    """A platform task that trips a moderation rule is held for review; the pool keeps posting."""
    from humanapi_api.house import house_buyer

    settings.admin_token = "adm"
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 500_000_000}, headers=ADMIN)
    with app.state.db.session() as s:
        b = house_buyer(s, "robinhood")
        b.blocked = True  # as if an earlier run had tripped the rule many times
    r = client.post("/v1/admin/team/run", json={"tasks": [{"type": "do", "title": "Photograph the posted hours at the library entrance", "payload": {"category": "go_and_see", "instructions": "Photograph the hours sign at the main entrance. Write the capture code on paper and keep it in the shot.", "proof": "photos"}, "location": "Austin, TX"}], "wallets": [], "teamRun": False}, headers=ADMIN)
    assert r.status_code == 200, r.text
    t = client.get(f"/v1/tasks/{r.json()['posted'][0]}").json()
    assert t["state"] == "open" and t["cost"]["pricePerWorker"] >= 25_000_000
