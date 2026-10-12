from conftest import pay, verify_body
from test_workers import qualify, sign_in_evm


def test_responses_are_kept_as_comments(client, settings):
    settings.echo_worker = False
    t = pay(client, verify_body()).json()
    heads = []
    for value in ("yes", "yes", "no"):
        h, _ = sign_in_evm(client)
        qualify(client, h)
        heads.append(h)
        client.post(f"/v1/tasks/{t['taskId']}/claim", headers=h)
        if value == "no":
            break
        client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": value, "note": "clear to me"}, headers=h)
    # before the task is decided: the public sees none, a worker sees only their own
    pub = client.get(f"/v1/tasks/{t['taskId']}/comments").json()
    assert pub["total"] == 2 and pub["hidden"] == 2 and pub["comments"] == []
    own = client.get(f"/v1/tasks/{t['taskId']}/comments", headers=heads[0]).json()
    assert len(own["comments"]) == 1 and own["comments"][0]["author"] == "You" and own["comments"][0]["outcome"] == "waiting"
    client.post(f"/v1/tasks/{t['taskId']}/answer", json={"answer": "no"}, headers=heads[2])
    done = client.get(f"/v1/tasks/{t['taskId']}/comments").json()
    assert done["decided"] and [c["response"] for c in done["comments"]] == ["yes", "yes", "no"]
    assert [c["outcome"] for c in done["comments"]] == ["accepted", "accepted", "not accepted"]
    assert done["comments"][0]["note"] == "clear to me" and done["comments"][0]["author"].startswith("Worker ") and "0x" not in str([{k: v for k, v in c.items() if k != "wallet"} for c in done["comments"]])
