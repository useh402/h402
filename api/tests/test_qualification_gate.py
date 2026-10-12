"""With the qualification gate off, every worker may take every type of work without the practice questions."""

import time

from sqlalchemy import func
from test_claim import FakeWallet, post_one
from test_workers import sign_in_evm

from humanapi_api.models import Worker


def accepted_terms_only(client, app):
    """A worker who accepted the terms but passed no practice questions."""
    h, acct = sign_in_evm(client)
    with app.state.db.session() as s:
        w = s.query(Worker).filter(func.lower(Worker.wallet) == acct.address.lower()).one()
        w.qualified_types, w.terms_accepted_at = [], time.time()
    return h


def test_gate_on_keeps_unqualified_workers_out(client, app, settings):
    settings.qualification_required = True
    task = post_one(client, app, settings, FakeWallet(usdg=100_000_000))
    h = accepted_terms_only(client, app)
    assert client.get("/v1/workers/me", headers=h).json()["qualifiedTypes"] == []
    assert client.get("/v1/workers/tasks", headers=h).json()["tasks"] == []
    assert client.post(f"/v1/tasks/{task['taskId']}/claim", json={}, headers=h).status_code == 403


def test_gate_off_lets_anyone_take_any_type(client, app, settings):
    settings.qualification_required = False
    task = post_one(client, app, settings, FakeWallet(usdg=100_000_000))
    h = accepted_terms_only(client, app)
    me = client.get("/v1/workers/me", headers=h).json()
    assert "verify" in me["qualifiedTypes"] and "do" in me["qualifiedTypes"]
    assert task["taskId"] in {t["taskId"] for t in client.get("/v1/workers/tasks", headers=h).json()["tasks"]}
    r = client.post(f"/v1/tasks/{task['taskId']}/claim", json={}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["taskId"] == task["taskId"]
