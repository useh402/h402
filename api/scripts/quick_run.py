"""Posts the fifty $1.00 quick checks on mainnet and runs the team's wallets through ten of them.

  python scripts/quick_run.py run    ten tasks: two correct answers and one wrong answer each, settled by the contract
  python scripts/quick_run.py rest   the other forty, open to anyone
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import httpx
from quick_tasks import RUN, TASKS
from team_run import ADMIN, API, REQUESTERS, WALLETS, sign_in

REWARD = 1_000_000
DATA = pathlib.Path(__file__).resolve().parents[1] / "data"


def body(i: int, workers: int) -> dict:
    cat, title, text, q, _ = TASKS[i]
    return {"type": "verify", "title": title, "payload": {"category": cat, "text": text, "question": q}, "workers": workers, "pricePerWorker": REWARD, "requester": REQUESTERS[i % 5], "location": "Remote"}


def post(c: httpx.Client, bodies: list[dict], team: bool, wallets: list[str]) -> list[str]:
    r = c.post("/v1/admin/team/run", json={"tasks": bodies, "wallets": wallets, "teamRun": team}, headers=ADMIN)
    if r.status_code != 200:
        sys.exit(f"posting failed: {r.text}")
    return r.json()["posted"]


def claim_and_answer(c: httpx.Client, h: dict, tid: str, value: str) -> None:
    for attempt in range(30):
        r = c.post(f"/v1/tasks/{tid}/claim", headers=h)
        if r.status_code == 200:
            break
        if r.status_code == 409 and "already" in r.text:
            return
        if attempt == 29:
            r.raise_for_status()
        time.sleep(6)  # the funding check could not reach the chain; try again
    time.sleep(8)  # read the task before answering
    r = c.post(f"/v1/tasks/{tid}/answer", json={"answer": value}, headers=h)
    if r.status_code not in (200, 201, 409):
        r.raise_for_status()


def main() -> None:
    c = httpx.Client(base_url=API, timeout=90)
    mode = sys.argv[1]
    if mode == "rest":
        f = DATA / "quick-rest.json"
        if f.exists():
            sys.exit("the other forty are already posted")
        ids = post(c, [body(i, 1) for i in range(50) if i not in RUN], False, [])
        f.write_text(json.dumps(ids))
        print("posted", len(ids))
        return
    good, bad = [w for w in WALLETS if w["role"] == "correct"], [w for w in WALLETS if w["role"] == "wrong"]
    f = DATA / "quick-run.json"
    print("1. signing in 20 wallets", flush=True)
    sessions = {w["address"]: sign_in(c, w) for w in good + bad}
    if f.exists():
        ids = json.loads(f.read_text())
    else:
        print("2. posting the ten tasks", flush=True)
        ids = post(c, [body(i, 3) for i in RUN], True, [w["address"] for w in WALLETS])
        f.write_text(json.dumps(ids))
    print("3. answering", flush=True)
    for n, tid in enumerate(ids):
        if c.get(f"/v1/tasks/{tid}").json()["state"] not in ("open", "claimed", "submitted"):
            continue
        right = TASKS[RUN[n]][4]
        wrong = "no" if right == "yes" else "yes"
        for w, value in ((good[n], right), (bad[n], wrong), (good[(n + 1) % 10], right)):
            claim_and_answer(c, sessions[w["address"]], tid, value)
        print(f"  task {n + 1}/10 answered", flush=True)
    print("4. waiting for the contract to settle", flush=True)
    end = time.time() + 20 * 60
    while True:
        views = [c.get(f"/v1/tasks/{i}").json() for i in ids]
        states = [(v.get("escrow") or {}).get("state") for v in views]
        print("  contract:", {s: states.count(s) for s in set(states)}, flush=True)
        if all(s == "closed" for s in states):
            break
        if time.time() > end:
            sys.exit("timed out waiting for settlement")
        time.sleep(12)
    out = [{"task": v["taskId"], "title": v["title"], "state": v["state"], "open": v["escrow"]["openTransaction"], "settle": v["escrow"]["closeTransaction"]} for v in views]
    (DATA / "quick-run-result.json").write_text(json.dumps(out, indent=1))
    for o in out:
        print(f"  {o['state']:5} {o['title'][:48]:48} {o['settle']}")


if __name__ == "__main__":
    main()
