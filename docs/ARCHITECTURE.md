# Backend architecture, in phases

**Status:** Proposed 2026-10-09, waiting for the owner's go. Builds on [DESIGN.md](DESIGN.md) section 8 and [FACILITATORS.md](FACILITATORS.md).
**Rule:** each phase ends with something that runs end to end and is demonstrated, so a later phase never depends on untested work.

## 0. Shape of the whole thing

| Process | Owns | Talks to | Exposure |
| --- | --- | --- | --- |
| `facilitator` | x402 `/supported`, `/verify`, `/settle` for both rails; the only process with settlement keys; replay store | Robinhood RPC, Solana RPC, Postgres | Private (bearer token from the API) |
| `api` | Buyer HTTP surface: 402 flow, tasks, pricing, receipts, webhooks, batch; task state machine; ledger writes | `facilitator`, Postgres, Redis | Public |
| `jobs` | Router (fan-out to workers), claim expiry, consensus, payouts, refunds, webhook delivery, chain reconciliation, gold-task injection | Postgres, Redis, Telegram API, chain RPCs (payout keys) | Private |
| `web` | The website: landing, the Earn area for workers (sign in with a wallet, task feed, task cards, earnings), later the buyer console and docs | `api` | Public |
| Postgres | System of record: every table in DESIGN.md section 7 | | |
| Redis | Streams for routing, online-worker set, rate limits, claim locks, idempotency cache | | |

| Choice | Decision proposed | Why |
| --- | --- | --- |
| Language for `api`, `jobs` | Python 3.12, same as the facilitators | One language, one toolchain, chain clients shared with the facilitators (read-only there, keys only in `facilitator` and the payout worker) |
| HTTP | FastAPI + uvicorn; pydantic models are the API contract and generate the OpenAPI the SDKs are built from | |
| Database access | SQLAlchemy 2 (async) + Alembic migrations | Migrations are versioned from day one |
| Queues | Redis streams with consumer groups (no Celery) | Routing needs ordering and acknowledgement, not a task framework |
| Scheduling | A ticker inside `jobs` (asyncio) for expiry, payouts, reconciliation | Keeps one process to deploy |
| Worker auth | Sign-in with a wallet: the API issues a nonce, the browser wallet signs it (EIP-191 on EVM, ed25519 on Solana), the API returns a session token; that wallet is also the payout address | No passwords, no accounts, the payout address is proven by the signature |
| Repo | `facilitators/` and `api/` as uv projects (jobs run inside `api` until they need their own process); `web/` is the Next.js app | Simple to run and deploy |
| Environments | `local` (SQLite or Postgres, testnets, the echo worker), `testnet` (hosted, testnet 46630 and devnet), `mainnet` | Nothing touches mainnet before phase 5 |
| Secrets | Environment variables from the host's secret store; keys never in Postgres, never logged | |
| Observability | Structured JSON logs, a `/health` on every process, Sentry for errors, a few counters (tasks by state, settle latency, payout backlog) | |

## 1. Phase 1: facilitators (work item 1)

Already specified in full in [FACILITATORS.md](FACILITATORS.md). Summary of what this phase leaves behind for the next ones:

| Leaves behind | Used later by |
| --- | --- |
| `shared/x402/types.py`: PaymentRequirements, PaymentPayload, verify and settle responses | `api` builds 402 responses and forwards payments |
| `shared/chains/robinhood.py`, `shared/chains/solana.py`: read-only clients (balances, receipts, confirmations) | `jobs` reconciliation and payouts |
| Replay store table `settlements` | Ledger links every task to its settlement row |
| Demo server and client per rail | The pattern the `api` 402 middleware is written from |
| Docker image, run guide, testnet keys and funds | Phase 2 runs against the same testnets |

**Exit:** the acceptance criteria in FACILITATORS.md section 8, demonstrated to the owner. Estimated 1.5 to 2 weeks.

## 2. Phase 2: task API, paid end to end

The buyer side with no humans yet. A built-in "echo worker" answers tasks automatically in `local` so the whole money path can be tested before the bot exists.

| Piece | Detail |
| --- | --- |
| Schema v1 | `buyers`, `tasks`, `claims`, `answers`, `workers` (minimal), `payouts`, `ledger`, `webhooks`, `webhook_deliveries`, `idempotency_keys`; Alembic migration 0001 |
| 402 middleware | On `POST /v1/tasks` without `X-PAYMENT`: price the task, build one requirement per rail, store a `task_quote` (hash of body + price + nonce, 5-minute validity), return 402. With `X-PAYMENT`: match the quote by hash, call facilitator `/verify` then `/settle`, write the ledger credit, create the task in `paid` |
| Pricing | `GET /v1/pricing`: per-type base price, platform fee (DECISIONS B), worker count; availability number is a stub until phase 3 |
| Task state machine | One module owns transitions (`paid → open → claimed → submitted → done / expired / rejected / disputed`); every transition writes an event row; nothing else changes `state` |
| Ledger | Double-entry rows per rail: escrow in, worker due, platform fee, refund out. An invariant check (escrow balance equals chain balance minus pending payouts) runs in `jobs` |
| Idempotency | `Idempotency-Key` header stored with the response for 24 hours |
| Webhooks | `POST /v1/webhooks` registration; HMAC-SHA256 signed deliveries with retries from `jobs` |
| Receipts | `GET /v1/receipts/{id}`: public page of payment, consensus and payouts (payouts empty until phase 3) |
| Batch | `POST /v1/tasks/batch`: one payment, up to 100 tasks, one quote hash over the whole body |
| Echo worker | A `jobs` plugin, enabled only in `local`, that claims and answers tasks with canned answers, so `done` and refunds can be exercised |
| Tests | Unit tests for the state machine, ledger invariants and quote hashing; integration test of the full 402 round trip per rail against the facilitator on testnets |

**Exit:** a script pays for a `verify` task on each rail, the echo worker answers, the buyer gets the result by webhook and by `GET`, and the ledger reconciles to the testnet escrow balance. Estimated 2 weeks.

## 3. Phase 3: humans in the loop, on the website

Decision 16 (2026-10-09): no Telegram bot. The worker side lives in `web/` and talks to the API.

| Piece | Detail |
| --- | --- |
| Worker sign-in (`api` + `web`) | `POST /v1/workers/nonce` then `POST /v1/workers/session` with the wallet signature (EIP-191 for EVM, ed25519 for Solana); session token in an httpOnly cookie or bearer; the wallet is the payout address and the rail |
| Onboarding (`web`) | Earn page: connect wallet, sign in, pick languages, accept the worker terms, three qualification tasks per type (scored against gold answers) before real tasks |
| Online state | A worker is online while the Earn page is open: the page pings `POST /v1/workers/heartbeat` every 30 s; the API keeps `last_seen`; `GET /v1/pricing` reports live counts per type from it |
| Task feed (`api`) | `GET /v1/workers/tasks`: open tasks the worker qualifies for (type, min reputation, language, not already answered), newest first, with price and time left; the page polls it every few seconds (SSE later) |
| Claim and answer (`api`) | `POST /v1/tasks/{id}/claim` holds a slot for 2 minutes (row with expiry, unique per task and worker, at most `workers` live holds); `POST /v1/tasks/{id}/answer` submits; expiry releases the hold; a released task shows again in the feed |
| Task cards (`web`) | One component per type: images, options as buttons, yes/no/unsure, 1 to 5, a text box for `read` and `answer`, a note field, a countdown; keyboard friendly; no responsive work until the backend is done (owner's rule) |
| Consensus | Already in `api` (phase 2): runs when every paid slot answered or at the deadline |
| Payouts (`api` jobs) | Every 10 minutes per rail: sum `worker_due` per wallet above a minimum, one batched transfer per rail from the payout wallet (Robinhood: one ERC-20 transfer per worker in a multicall or sequential; Solana: one transaction with several SPL transfers), write `payouts` with the reference and the ledger; hot-wallet cap and an alert on unusual volume |
| Refunds (`api` jobs) | `refund_due` rows paid back to the payer address on the same rail from the escrow wallet, same batching |
| Earnings (`web` + `api`) | `GET /v1/workers/earnings`: today, this week, pending, paid, each payout with its explorer link; reputation per type |
| Reconciliation | Hourly: escrow and payout wallet balances against the ledger; `/health` shows drift |
| Tests | Sign-in signature checks on both rails; feed filtering; claim races (concurrent claims hold at most `workers` slots); answer rules; payout batching math; refund rows; a browser run of the Earn flow against the local API with real test keys |

**Exit:** a task paid on a testnet is answered by three real browser sessions, consensus is reached, the three are paid in one batched testnet transfer, and the receipt page shows all of it. Estimated 3 weeks.

## 4. Phase 4: quality and safety

| Piece | Detail |
| --- | --- |
| Moderation | Before routing: a text and image moderation model plus the hard list (credentials, captchas, private individuals, sexual or violent content); `rejected` with full refund; borderline to a review queue; a buyer address is blocked after two rejections |
| Gold tasks | `gold_tasks` table; `jobs` injects one gold task per 20 real tasks per worker; a wrong gold answer lowers reputation, three in a day pauses the worker |
| Reputation and tiers | Per-type reputation from agreement rate and gold accuracy; tiers `new / bronze / silver / gold` with price multipliers; `minReputation` honoured by the router |
| Bot detection | Timing patterns, duplicate answers across accounts, periodic liveness check in the bot |
| Disputes | Buyer `POST /v1/tasks/{id}/dispute` within 24 hours; review queue; outcomes adjust payouts or refund from the platform fee |
| Reports | One-tap Report on a task card; the worker is still paid; the task goes to review |
| Retention | Payloads encrypted at rest; deleted 30 days after completion by a `jobs` sweep |
| Remaining task types | `read`, `label`, `rate` with their consensus rules and card layouts |
| Tests | Gold injection rate, reputation math, moderation decisions on a fixture set, retention sweep |

**Exit:** a week of testnet operation with the owner's community, no unpaid correct answer, no paid wrong gold answer, moderation blocks the fixture set. Estimated 2 weeks.

## 5. Phase 5: developer surface and launch

| Piece | Detail |
| --- | --- |
| TypeScript SDK | `human.verify / choose / read / answer / rate / label`, a signer per rail, the 402 round trip hidden; generated types from the API's OpenAPI |
| Python SDK | Same surface, for data pipelines |
| Second door | Prepaid balance with an API key for buyers who do not want x402 yet; top-up is itself an x402 payment |
| `answer` type | Single gold-tier worker, 15-minute limit, confidence field |
| Buyer console | Sign in with a wallet signature; usage, spend, receipts, webhook logs, API keys; docs pages |
| Mainnet | New facilitator and payout keys, dedicated RPC provider, hot-wallet caps, alerts to Telegram; go-live on both rails |
| Operations | Runbooks: stuck settlement, payout failure, drift alert, key rotation; backups; status page |
| Launch | Legal texts, prohibited-task list, first 50 to 100 workers, 5 buyers (DECISIONS D, F) |

**Exit:** a buyer installs the SDK, runs one call on mainnet and sees the receipt; workers are paid on mainnet. Estimated 3 weeks.

## 6. Timeline and decisions needed

| Phase | Weeks (one builder) | Decisions needed before it starts |
| --- | --- | --- |
| 1 Facilitators | 1.5 to 2 | G (public or private facilitators) can wait until the end of the phase |
| 2 Task API | 2 | B (platform fee), E (hosting for the testnet environment) |
| 3 Humans on the website | 3 | none open (C resolved by decision 16) |
| 4 Quality | 2 | F (KYC threshold) |
| 5 Launch | 3 | A (name and domain), D (geography and communities) |

Total: about 12 weeks to mainnet launch, assuming the owner reviews at every phase exit.

## 7. What is deliberately not in this plan

| Left out | Why |
| --- | --- |
| Telegram bot or Mini App | Decision 16: workers use the website; Telegram may return as a notification channel |
| More rails (Base USDC, Polygon) | The facilitator design makes a rail a new module; add one only when a buyer asks |
| Separate microservices per concern | Five processes is already the maximum sensible for one builder; split `jobs` only when a worker type needs its own scaling |
| GraphQL, gRPC | Buyers are agents calling HTTP with x402; JSON over REST is the whole point |
