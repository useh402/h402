"""A listed task the pool cannot pay for is not shown: nobody takes a task only to be told it cannot be funded."""

from conftest import RH_ESCROW
from test_claim import FakeWallet, ready

from humanapi_api import escrow_chain

ADMIN = {"Authorization": "Bearer adm"}
BIG = {"type": "verify", "title": "Is the sign on this door current?", "payload": {"category": "real_and_current", "text": "A photo of a door sign reading 'Closed Mondays'.", "question": "Does the sign say the shop is closed on Mondays?"}, "workers": 3, "pricePerWorker": 20_000_000, "location": "Remote"}
SMALL = {**BIG, "title": "Is this receipt total readable?", "pricePerWorker": 2_000_000}


def pool_of(client, app, settings, usdg):
    settings.admin_token, settings.echo_worker, settings.house_batch_size = "adm", False, 1
    settings.escrow_contract = RH_ESCROW
    app.state.jobs.reward_sender = FakeWallet(usdg=usdg)
    app.state.jobs.chain = type("C", (), {"available": lambda self: 0, "status": lambda self, t: 0, "info": lambda self: {}})()
    escrow_chain._last_pool_sync = 0.0
    client.post("/v1/admin/escrow/run", headers=ADMIN)  # the pool's books follow the wallet


def test_tasks_the_pool_cannot_cover_are_hidden_until_money_arrives(client, app, settings):
    pool_of(client, app, settings, 10_000_000)  # $10 in the pool
    r = client.post("/v1/admin/team/run", json={"tasks": [BIG, SMALL], "wallets": [], "teamRun": False}, headers=ADMIN)
    big, small = r.json()["posted"]
    shown = {t["taskId"] for t in client.get("/v1/tasks/open").json()["tasks"]}
    assert small in shown and big not in shown  # $7.20 fits, $72 does not
    h, _ = ready(client, app, "verify")
    assert {t["taskId"] for t in client.get("/v1/workers/tasks", headers=h).json()["tasks"]} == {small}
    # Money arrives: the big task appears.
    app.state.jobs.reward_sender.usdg = 100_000_000
    escrow_chain._last_pool_sync = 0.0
    client.post("/v1/admin/escrow/run", headers=ADMIN)
    assert big in {t["taskId"] for t in client.get("/v1/tasks/open").json()["tasks"]}


def test_a_task_already_funded_stays_visible_when_the_pool_runs_low(client, app, settings):
    pool_of(client, app, settings, 10_000_000)
    small = client.post("/v1/admin/team/run", json={"tasks": [SMALL], "wallets": [], "teamRun": False}, headers=ADMIN).json()["posted"][0]
    h, _ = ready(client, app, "verify")
    assert client.post(f"/v1/tasks/{small}/claim", json={}, headers=h).status_code == 200  # taken: its money is set aside
    app.state.jobs.reward_sender.usdg = 0
    escrow_chain._last_pool_sync = 0.0
    client.post("/v1/admin/escrow/run", headers=ADMIN)
    assert small in {t["taskId"] for t in client.get("/v1/tasks/open").json()["tasks"]}
