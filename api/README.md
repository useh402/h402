# H402 task API (phases 2, 3 and 4)

The buyer side: an agent posts a task, gets a `402` with one payment requirement per rail, pays with x402, and the task is created in escrow. Humans arrive in phase 3; locally an echo worker answers tasks so the whole money path runs today.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /v1/tasks` | Create a task. Without `PAYMENT-SIGNATURE`: `402` with a quote (body) and the x402 `PAYMENT-REQUIRED` header. With it: verify, settle, create; `202` with the task and a `PAYMENT-RESPONSE` header |
| `POST /v1/tasks/batch` | Up to 100 tasks in one payment; `202` with `batchId` and every task |
| `GET /v1/tasks/{id}` | State, cost, payment, result and agreement when done, refund when expired |
| `GET /v1/batches/{id}` | Every task of a batch |
| `GET /v1/pricing` | Base prices, defaults, consensus rule per type, fee, rails |
| `GET /v1/receipts/{id}` | Public receipt: payment, consensus, payouts, refunds, ledger postings, timeline |
| `POST /v1/webhooks` | Buyer-level webhook `{url, payer, network}`: state changes only. Per-task webhooks (`webhook.url` in a paid body) also carry the result |
| `GET /health` | Ledger invariant per rail, escrow drift against the chain when an RPC is configured, task counts, facilitator reachability |

Headers: `Idempotency-Key` on the POSTs replays the stored response for 24 hours (a different body with the same key is `422`). Webhook deliveries carry `X-H402-Signature` = HMAC-SHA256(secret, `<timestamp>.<raw body>`), `X-H402-Timestamp`, `X-H402-Event`, retried with backoff up to 8 times.

## Worker endpoints (phase 3)

| Method and path | Purpose |
| --- | --- |
| `POST /v1/workers/nonce` `{wallet, network}` | A message to sign; the wallet is normalised and becomes the payout address |
| `POST /v1/workers/session` `{wallet, network, nonce, signature}` | Verifies EIP-191 (EVM) or ed25519 base58 (Solana); returns a bearer token (30 days) |
| `POST /v1/workers/dev-session` | Local only (`HA_ENV=local`, `HA_DEV_LOGIN=true`): sign in without a wallet |
| `GET /v1/workers/me`, `POST /v1/workers/profile` | Profile; accept terms, set languages |
| `POST /v1/workers/heartbeat` | Marks the worker online for 10 minutes; `GET /v1/pricing` counts them per type |
| `GET /v1/workers/qualification/{type}`, `POST ...` | Three practice tasks; two correct unlocks the type |
| `GET /v1/workers/tasks` | Open tasks the worker qualifies for and has not answered, with free slots; payload only once held |
| `POST /v1/tasks/{id}/claim`, `/release`, `/answer` | Two-minute hold on a slot, give it back, submit an answer (validated per type) |
| `GET /v1/workers/earnings` | Pending, today, week, paid, payouts with explorer links |

Payouts: with `HA_PAYOUTS_ENABLED=true` and the escrow private keys, a round every `HA_PAYOUT_INTERVAL_SECONDS` groups `worker_due` per wallet (above `HA_PAYOUT_MIN_AMOUNT`, within `HA_PAYOUT_ROUND_CAP`) and sends one transfer per wallet on Robinhood Chain or several per transaction on Solana; refunds go back to payer addresses the same way. Rows move queued → sending (transaction id recorded before broadcast) → sent or failed (requeued up to five times); `sending` rows are resolved from the chain on start.

Local Earn demo: `HA_DEV_LOGIN=true uv run humanapi-api`, `uv run python demo/seed_tasks.py`, then open the site's `/earn` with `NEXT_PUBLIC_DEV_LOGIN=1`.

## Quality and safety (phase 4)

- Every paid task is moderated before routing: `moderation.py` rules reject credentials, captchas, account access and the hard list with a full refund, and hold borderline content (phone numbers, emails, private individuals, identity documents) for review. `HA_MODERATION_URL` adds an external classifier. Two rejections block the buyer.
- Admin API with `HA_ADMIN_TOKEN`: `GET/POST /v1/admin/review`, `GET/POST /v1/admin/disputes`, `GET /v1/admin/reports`, `GET/POST /v1/admin/gold`, `GET/POST /v1/admin/workers/{id}` (pause and unpause).
- Gold tasks appear in a worker's feed every `HA_GOLD_EVERY` real answers and are paid from the fee pool; wrong ones lower reputation and three in a day pause the worker.
- Reputation is Laplace-smoothed agreement times gold accuracy, kept per type too; tiers new, bronze (20 answers, 0.70), silver (100, 0.85), gold (300, 0.95 and 95% gold accuracy).
- Abuse flags: implausibly fast answers, bursts, repeated free text; three in a day pause the worker.
- Buyers dispute a done task within 24 hours with the `buyerToken` from the 202 (`POST /v1/tasks/{id}/dispute`). Workers report a task from the card (`POST /v1/tasks/{id}/report`): it leaves the feed for review and the reporter is credited.
- Payloads and free-text answers are purged 30 days after completion.

## Task body

```json
{"type": "verify", "payload": {"image": "https://...", "question": "Is the total legible?"},
 "workers": 3, "pricePerWorker": 80000, "minReputation": 0.0, "timeLimitSeconds": 120,
 "webhook": {"url": "https://agent.example/hook"}, "reference": "order-42"}
```

Types and defaults (atomic units, 6 decimals): `choose` 100000 x3, `verify` 80000 x3, `rate` 50000 x3, `read` 200000 x2, `label` 50000 x3, `answer` 500000 x1 (reputation 0.9), `do` 1000000 x1 (action task: `payload.instructions`, optional `payload.url`, `payload.proof` text|screenshot|both; the worker submits proof, the client accepts with `POST /v1/tasks/{id}/accept {buyerToken}` or rejects with `{buyerToken, reject: true, reason}`, otherwise it is accepted after one hour). Total = pricePerWorker x workers + 20% fee (`HA_PLATFORM_FEE_BPS`).

## Money

Double-entry ledger per rail (`ledger` table): a settlement debits `escrow` and credits `payer:<addr>`; creation moves the total into `task:<id>`; completion moves worker shares to `worker_due:<worker>`, the fee to `platform_fee`, and unfilled or disagreeing slots to `refund_due:<payer>`; expiry refunds everything held. `escrow == sum of liabilities` always holds and `/health` checks it, plus the chain balance of the escrow address when `HA_*_RPC_URL` is set. Payouts and refunds are queued rows; the transfers themselves are phase 3.

Consensus runs when every paid slot has answered or at the deadline: majority for `choose`, `verify`, `label`; median (within 1) for `rate`; exact match for `read`; single answer for `answer`. No consensus means `expired` with a full refund.

## Run

```bash
cd api
uv sync --extra dev
cp .env.example .env            # facilitator URL and token, rails, escrow addresses
uv run alembic upgrade head     # or let create_all run on first start
uv run humanapi-api             # http://127.0.0.1:8400, docs at /docs
uv run pytest                   # 20 tests, fake facilitator, no network
```

Demo against the real facilitator: start the facilitator (github.com/useh402/facilitator) on :8402, put its demo merchant addresses in `HA_*_ESCROW_ADDRESS`, set `HA_ECHO_WORKER=true`, then `uv run --extra demo python demo/pay_task.py solana` (or `robinhood`). It pays with the SDK client, polls to `done`, and prints the receipt.

Postgres: `uv sync --extra postgres`, `HA_DATABASE_URL=postgresql+psycopg://...`. Docker: `docker build -t humanapi-api .`.
