from humanapi_api.catalogue import CATEGORIES
from humanapi_api.pricing import PROOF_KINDS, TASK_TYPES
from humanapi_api.templates import TEMPLATES


def test_templates_are_consistent():
    assert len(TEMPLATES) == 100
    assert len({t["id"] for t in TEMPLATES}) == 100
    for t in TEMPLATES:
        assert t["category"] in CATEGORIES, t["id"]
        assert t["type"] in TASK_TYPES, t["id"]
        assert t["proof"] in PROOF_KINDS, t["id"]
        assert t["status"] == "template"
        assert "india" not in (t["where"] + t["summary"]).lower()


def test_templates_endpoint(client):
    r = client.get("/v1/catalogue/templates?category=web3").json()
    assert len(r["templates"]) == 15 and r["note"].startswith("templates")
    assert len(client.get("/v1/catalogue").json()["categories"]) == 15
