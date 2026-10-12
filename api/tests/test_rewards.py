from conftest import decode_header, verify_body

from humanapi_api.house import catalogue
from humanapi_api.pricing import parse_task, standard_price

ADMIN = {"Authorization": "Bearer adm"}


def test_every_catalogue_reward_is_in_range():
    prices = [standard_price(parse_task({"timeLimitSeconds": 2400, **c})) for c in catalogue()]
    assert min(prices) >= 1_500_000 and max(prices) <= 50_000_000
    assert sum(1 for p in prices if 5_000_000 <= p <= 20_000_000) > len(prices) * 0.6
    assert any(p >= 30_000_000 for p in prices)  # in-person work


def test_minimum_reward_on_the_api(client, settings):
    settings.min_reward = 1_500_000
    r = client.post("/v1/tasks", json=verify_body())
    acc = decode_header(r.headers["PAYMENT-REQUIRED"])["accepts"][0]
    assert acc["amount"] == str(1_500_000 * 3 + 900_000)  # default raised to the minimum, plus 20%
    low = client.post("/v1/tasks", json=verify_body(pricePerWorker=200_000))
    assert low.status_code == 400 and "at least" in low.json()["message"]
    assert client.get("/v1/pricing").json()["types"]["verify"]["basePricePerWorker"] == 1_500_000


def test_house_tasks_use_the_formula(client, settings):
    settings.admin_token, settings.min_reward, settings.house_batch_size = "adm", 1_500_000, 6
    client.post("/v1/admin/house/deposit", json={"rail": "robinhood", "amount": 2_000_000_000}, headers=ADMIN)
    client.post("/v1/admin/house/post", headers=ADMIN)
    prices = [t["price"] for t in client.get("/v1/tasks/open").json()["tasks"]]
    assert len(prices) == 6 and min(prices) >= 1_500_000
