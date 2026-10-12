import json

import httpx

from humanapi_api import ledger, scouts
from humanapi_api.pricing import parse_task

ADMIN = {"Authorization": "Bearer adm"}

GOOD = {"title": "Call the main Seattle Public Library and ask about printing costs", "category": "calls", "type": "do", "location": "Remote", "instructions": "Look up the main branch of the Seattle Public Library, call it during opening hours, and ask how much black and white printing costs per page. Write who answered and what they said.", "proof": "text", "acceptance": "The price per page and the time of the call", "effortMinutes": 12, "why": "Libraries answer people on the phone, not programs."}
PHONE = {**GOOD, "title": "Call a Denver hardware store about key cutting prices today", "instructions": GOOD["instructions"] + " Their number is (303) 555-0142."}
BAD = {"title": "Log in to my bank and tell me the password reset steps please", "category": "blocked_sites", "type": "do", "location": "Remote", "instructions": "Log in to my account with the password I give you and write down the steps you see on the page.", "proof": "text", "effortMinutes": 5, "why": "x"}
DUP = {**GOOD, "title": "Call the Seattle Public Library main branch and ask about printing costs"}
JUDGE = {"title": "Which of these two apology emails sounds more sincere to a customer?", "category": "judgement", "type": "choose", "location": "Remote", "question": "Which apology sounds more sincere?", "options": ["Sorry for the trouble.", "We got this wrong, and here is what we are doing to fix it."], "effortMinutes": 1, "why": "Tone is a human call."}


def gateway(tasks, fail=False):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer gw"
        if fail:
            return httpx.Response(500, text="boom")
        body = json.loads(request.content)
        assert body["model"] and "United States only" in body["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "Here you go:\\n" + json.dumps({"tasks": tasks})}}], "usage": {"prompt_tokens": 400, "completion_tokens": 300}})

    return httpx.Client(transport=httpx.MockTransport(handler))


def setup(settings):
    settings.admin_token, settings.ai_gateway_api_key, settings.scouts_enabled = "adm", "gw", True
    settings.scout_models = "claude=anthropic/claude-haiku-5.5,grok=spacexai/grok-4.1-fast-non-reasoning"


def test_pricing_formula(settings):
    do = parse_task({k: v for k, v in scouts.to_body(GOOD).items() if v})
    assert scouts.price_for(settings, do) == 11_600_000  # 5 + 12 min x 0.30 + 3 for a call
    judge = parse_task({k: v for k, v in scouts.to_body(JUDGE).items() if v})
    assert scouts.price_for(settings, judge) == 2_000_000  # 1.50 + 0.50
    long = parse_task({**{k: v for k, v in scouts.to_body(GOOD).items() if v}, "effortMinutes": 200})
    assert scouts.price_for(settings, long) == 21_500_000  # effort counted to 45 min
    see = parse_task({**{k: v for k, v in scouts.to_body({**GOOD, "category": "go_and_see"}).items() if v}, "effortMinutes": 45})
    assert scouts.price_for(settings, see) == 43_500_000


def test_round_checks_and_review_queue(client, app, settings):
    setup(settings)
    app.state.jobs.scout_http = gateway([GOOD, PHONE, BAD, DUP, JUDGE])
    out = client.post("/v1/admin/scouts/run", headers=ADMIN).json()
    assert out["runs"] == 2
    v = client.get("/v1/scouts").json()
    claude = next(s for s in v["scouts"] if s["requester"] == "claude")
    assert claude["proposed"] == 5 and claude["waiting"] == 2 and claude["rejected"] == 3 and claude["inputTokens"] == 400
    reasons = {p["title"][:20]: p["reason"] for p in v["proposals"] if p["requester"] == "claude" and p["status"] == "rejected"}
    assert any("phone number" in r for r in reasons.values()) and any("moderation" in r for r in reasons.values()) and any("similar" in r for r in reasons.values())
    # the second model proposed the same things: all duplicates of what the first already has waiting
    grok = next(s for s in v["scouts"] if s["requester"] == "grok")
    assert grok["waiting"] == 0
    assert client.get("/v1/tasks/open").json()["count"] == 0  # nothing is live before an operator decides


def test_post_and_reject(client, app, settings):
    setup(settings)
    app.state.jobs.scout_http = gateway([GOOD, JUDGE])
    client.post("/v1/admin/scouts/run", headers=ADMIN)
    props = [p for p in client.get("/v1/scouts").json()["proposals"] if p["status"] == "review"]
    call = next(p for p in props if p["type"] == "do")
    r = client.post(f"/v1/admin/scouts/proposals/{call['id']}", json={"decision": "post"}, headers=ADMIN)
    assert r.status_code == 409 and "house balance" in r.json()["message"]
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 60_000_000}, headers=ADMIN)
    r = client.post(f"/v1/admin/scouts/proposals/{call['id']}", json={"decision": "post"}, headers=ADMIN).json()
    assert r["status"] == "posted"
    task = client.get(f"/v1/tasks/open/{r['taskId']}").json()
    assert task["requester"] == "claude" and task["price"] == 11_600_000 and task["payload"]["category"] == "calls"
    other = next(p for p in props if p["type"] == "choose")
    assert client.post(f"/v1/admin/scouts/proposals/{other['id']}", json={"decision": "reject", "reason": "dull"}, headers=ADMIN).json()["status"] == "rejected"
    assert client.post(f"/v1/admin/scouts/proposals/{other['id']}", json={"decision": "post"}, headers=ADMIN).status_code == 409
    with app.state.db.session() as s:
        assert ledger.check_invariant(s, "robinhood")["balanced"]


def test_auto_post_gateway_failure_and_limits(client, app, settings):
    setup(settings)
    settings.scout_auto_post = True
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 60_000_000}, headers=ADMIN)
    app.state.jobs.scout_http = gateway([JUDGE])
    client.post("/v1/admin/scouts/run", headers=ADMIN)
    assert client.get("/v1/tasks/open").json()["count"] == 1
    app.state.jobs.scout_http = gateway([], fail=True)
    client.post("/v1/admin/scouts/run", headers=ADMIN)
    v = client.get("/v1/scouts").json()
    assert v["scouts"][0]["lastOk"] is False and "500" in v["scouts"][0]["lastError"]
    settings.scout_daily_calls = 1
    assert client.post("/v1/admin/scouts/run", headers=ADMIN).json()["skipped"] == "daily call limit reached"
    settings.ai_gateway_api_key = ""
    assert client.post("/v1/admin/scouts/run", headers=ADMIN).json()["skipped"] == "no gateway key"


def test_extract_ignores_garbage():
    assert scouts.extract_tasks("no json here") == []
    assert scouts.extract_tasks('{"tasks": "ignore previous instructions"}') == []
    assert len(scouts.extract_tasks('```json\\n{"tasks": [{"title": "a"}, 5]}\\n```')) == 1
