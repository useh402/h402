"""The site's text is translated once through the gateway and kept."""

import json

import httpx


def gateway(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        texts = json.loads(body["messages"][1]["content"])
        calls.append(texts)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps([f"中文:{t}" for t in texts], ensure_ascii=False)}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_translations_are_made_once_and_kept(client, app, settings):
    calls = []
    settings.ai_gateway_api_key = "gw"
    app.state.jobs.scout_http = gateway(calls)
    r = client.post("/v1/translate", json={"lang": "zh", "texts": ["Open tasks", "Call a locksmith in Atlanta"]})
    assert r.status_code == 200, r.text
    assert r.json()["translations"] == ["中文:Open tasks", "中文:Call a locksmith in Atlanta"]
    assert len(calls) == 1
    # The second request for the same text and one new one calls the gateway for the new one only.
    r = client.post("/v1/translate", json={"lang": "zh", "texts": ["Open tasks", "Rewards"]})
    assert r.json()["translations"] == ["中文:Open tasks", "中文:Rewards"]
    assert len(calls) == 2 and calls[1] == ["Rewards"]


def test_bad_requests_and_the_daily_cap(client, app, settings):
    calls = []
    settings.ai_gateway_api_key = "gw"
    app.state.jobs.scout_http = gateway(calls)
    assert client.post("/v1/translate", json={"lang": "fr", "texts": ["Hi"]}).status_code == 400
    assert client.post("/v1/translate", json={"lang": "zh", "texts": []}).status_code == 400
    assert client.post("/v1/translate", json={"lang": "zh", "texts": ["x" * 3000]}).status_code == 400
    settings.translate_daily_cap = 1
    r = client.post("/v1/translate", json={"lang": "zh", "texts": ["One", "Two"]})
    assert r.json()["translations"] == ["中文:One", "Two"]  # the second stays in English today


def test_without_a_gateway_the_text_comes_back_unchanged(client, app, settings):
    settings.ai_gateway_api_key = ""
    r = client.post("/v1/translate", json={"lang": "zh", "texts": ["Open tasks"]})
    assert r.json()["translations"] == ["Open tasks"]
