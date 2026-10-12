# H402: design

**Status:** Design agreed on 2026-10-09. Nothing built yet except the documents.
**One line:** AI agents pay humans per task, over HTTP, with x402. A person on Telegram does the task in seconds and is paid the moment the answer is accepted.

Payment rails: **USDG on Robinhood Chain (4663)** and **USDC on Solana**, each through its own Python facilitator (see [FACILITATORS.md](FACILITATORS.md)). Everything else in this document is rail-independent.

## 1. What it is

| Item | Decision |
| --- | --- |
| Buyers | Agent builders: trading bots, automation platforms, support bots, data pipelines, anyone whose agent gets stuck on judgment, verification or the physical world |
| Earners ("workers") | Anyone in the United States with a browser wallet. The market, the tasks and the examples are United States only (decision 22) |
| Value to buyers | A human in the loop in under a minute, no hiring, no account, no invoice, price known before the call, pay only on delivery |
| Value to earners | Real money for small tasks, paid the moment the task is accepted, with a public, verifiable payout history |
| What exists today | Amazon MTurk and Scale (accounts, weeks to pay, 20 to 40% fees, no API an agent can pay), Toloka, captcha farms (abusive). Nothing agent-native, nothing x402-native |

## 2. Task types for version 1

| Type | Agent sends | Human returns | Typical price per worker | Time limit | Consensus |
| --- | --- | --- | --- | --- | --- |
| `choose` | Two to five options (text or images) and a question | Index of the best one and one sentence why | $0.05 to $0.20 | 2 min | 3 humans, majority |
| `verify` | An image or text and a yes/no question | yes / no / unsure plus a note | $0.05 to $0.15 | 2 min | 3 humans |
| `rate` | One item and a rubric | A score 1 to 5 plus a note | $0.05 | 2 min | 3 humans |
| `read` | An image of text (receipt, sign, handwriting) | The transcribed text | $0.10 to $0.30 | 5 min | 2 humans, must match or a third breaks the tie |
| `label` | An item and a fixed list of labels | One or more labels | $0.03 to $0.10 | 2 min | 3 humans |
| `answer` | A short free question needing local or human knowledge | Free-text answer with a confidence | $0.20 to $1.00 | 15 min | 1 human, rating-gated |
| `do` (added 2026-10-09) | Instructions, a link, what proof is wanted (text, screenshot or both) | Proof of the finished action | $1.00 to $5.00 | 30 min (up to 60) | 1 person; the client accepts the proof or disputes it within 1 hour, otherwise it is accepted |
| Excluded | Solving bot checks for a script, anything with login credentials or one-time codes, buying or paying on someone's behalf, sexual or violent content, content identifying private people. Phone calls and go-and-see tasks are IN since 2026-10-09 as `do` categories (see TASKS.md) | | | | |

Buyers set `workers` (1, 3 or 5) and `minReputation`. Price is per worker, so a 3-worker `verify` at $0.05 costs $0.15 plus the platform fee.

## 3. The protocol

| Step | What happens |
| --- | --- |
| 1 | Agent calls `POST /v1/tasks` with the task body and no payment |
| 2 | Server answers `402 Payment Required` with one x402 payment requirement per rail (USDG on Robinhood Chain, USDC on Solana): amount, pay-to address, nonce or reference, the task hash in `extra`, validity window |
| 3 | Agent signs the payment for the rail it chose and repeats the request with the `X-PAYMENT` header |
| 4 | Server asks its facilitator to verify, then settle; the funds land in the escrow wallet of that rail; the task is created; `202` with `taskId` and a `resultUrl` |
| 5 | Task is routed to qualified online workers; the first N to claim get it |
| 6 | Workers submit; consensus is computed when enough answers are in or the deadline passes |
| 7 | Agent fetches `GET /v1/tasks/{id}` or receives a signed webhook: the answer, agreement level, worker count, a receipt |
| 8 | Workers who agreed with the consensus are paid; the platform fee is kept; an unfulfilled task is refunded to the payer address on the same rail |

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/tasks` | Create and pay for a task (x402) |
| `GET /v1/tasks/{id}` | Status and result |
| `POST /v1/tasks/batch` | Up to 100 tasks in one payment |
| `GET /v1/pricing` | Live prices and current worker availability per task type |
| `POST /v1/webhooks` | Register a result webhook (HMAC-signed deliveries) |
| `GET /v1/receipts/{id}` | Payment, payouts and consensus record; public |

| Task state | Meaning |
| --- | --- |
| `paid` | Payment settled, task queued |
| `open` | Visible to workers |
| `claimed` | Enough workers hold it |
| `submitted` | Answers in, consensus pending |
| `done` | Consensus reached, payouts queued |
| `expired` | Deadline passed with too few answers; partial refund |
| `rejected` | Failed moderation before routing; full refund |
| `disputed` | Buyer disputed within the window; under review |

## 4. Money

| Item | Decision | Why |
| --- | --- | --- |
| Rails | USDG on Robinhood Chain via the x402 Permit2 route; USDC on Solana via the x402 SVM route | Both chosen by the owner; each has its own Python facilitator |
| Facilitators | Our own, in Python, one process serving both rails (`/supported`, `/verify`, `/settle`) | No public facilitator serves Robinhood Chain; owning both keeps fees and control in house |
| Escrow | One platform wallet per rail receives settlements; a ledger tracks each task's balance and reconciles to the chain | Simple, auditable; a contract escrow is a phase-3 option |
| Worker payouts | On the rail the worker chose, batched every 10 minutes once the balance is at or above $1; the platform pays gas | Instant enough, cheap enough |
| Platform fee | 20% of the task price (open decision B), shown in the 402 response | Covers gas, consensus overhead, fraud losses |
| Refunds | Expired tasks refund unused worker slots; rejected tasks refund fully, from escrow, to the payer address | Keeps "pay only on delivery" true |
| Minimums | Task price at least $0.02 per worker; payout batch at least $1 | Below this, gas and attention cost more than the task |
| Worker wallet | v1: worker pastes an address for one rail (EVM address for USDG, Solana address for USDC). v2: embedded wallet in a Telegram Mini App | Fastest path first |
| Prepaid balance | Also accept a prepaid balance with an API key, with the same 402 semantics underneath | For buyers who cannot sign x402 yet |

## 5. Quality

| Mechanism | Rule |
| --- | --- |
| Qualification | New workers pass 10 gold tasks per type before earning; 8 of 10 correct |
| Consensus | Majority of N; a worker in the minority on a clear-majority task is not paid for that task |
| Gold tasks | 5% of served tasks are known-answer tasks; a wrong gold answer costs reputation |
| Reputation | Rolling score per type from agreement rate, gold accuracy and speed; buyers can set `minReputation` |
| Speed | Claims expire after the time limit; three abandoned tasks in a day pauses the worker |
| Dispute | Buyer can dispute within 24 hours with a reason; a senior worker pool re-judges; a lost dispute refunds the buyer and docks the workers |
| Tiers | Bronze (new), Silver (100 tasks, 90% agreement), Gold (1,000 tasks, 95%). Gold workers get `answer` tasks and a higher price |

## 6. Abuse controls

| Threat | Control |
| --- | --- |
| Sybil workers | One Telegram account per wallet, phone-verified Telegram accounts only, device and IP clustering, cap on new accounts per day per IP |
| Bots doing the tasks | Gold tasks with subtle traps, human-only timing patterns, image tasks hard for models, periodic liveness check |
| Collusion | Workers never see who else holds a task; assignment is randomised across geographies |
| Abusive tasks | Automatic moderation on every task before routing; a hard list (no credentials, no captchas, no private individuals, no sexual or violent content); a human review queue for borderline; the buyer address is blocked after two rejections |
| PII | Workers see only the task payload; payloads are deleted 30 days after completion; buyers agree not to include personal data |
| Payment replay | x402 nonce plus task hash; one settlement per authorization; idempotency key per request; the facilitator stores every settled nonce and signature |
| Payout drain | Payout wallets hold only a day's float; a hot-wallet cap and an alert on unusual payout volume |

## 7. Data model

| Table | Key fields |
| --- | --- |
| `buyers` | payer address per rail, API key (optional), reputation, blocked flag |
| `tasks` | type, payload (encrypted at rest), price per worker, workers wanted, min reputation, deadline, state, consensus answer, agreement, rail, payment reference (tx hash or signature), refund reference |
| `claims` | task, worker, claimed at, expires at |
| `answers` | task, worker, answer, note, submitted at, agrees with consensus, paid |
| `workers` | Telegram id, wallet address and rail, tier, reputation per type, qualifications, paused flag, balance due |
| `payouts` | worker, amount, rail, batch reference, status |
| `gold_tasks` | type, payload, correct answer |
| `disputes` | task, reason, outcome |
| `ledger` | every credit and debit per rail, so escrow always reconciles to the chain |

## 8. Architecture

| Component | Does | Built with |
| --- | --- | --- |
| Facilitators | `/supported`, `/verify`, `/settle` per rail; replay store; the only code holding settlement keys | Python, FastAPI, web3.py, solders/solana-py |
| Task API | The 402 endpoints, routing, consensus, webhooks, ledger | To decide (Python to match the facilitators, or TypeScript); Postgres, Redis |
| Worker bot | Telegram: join, qualify, task cards with buttons, submit, earnings | Telegram Bot API, long polling; Mini App later |
| Router | Picks workers by type, reputation, language, online state; fans out; handles claim expiry | Redis streams |
| Moderation | Pre-routing checks on text and images | A moderation model |
| Payouts | Batched transfers per rail from the payout wallet | Shares code with the facilitators' chain clients |
| Dashboard | Buyer console: usage, receipts, docs; worker leaderboard | Next.js |
| SDK | `human.choose()`, `human.verify()`, `human.read()`, `human.answer()` with x402 built in | TypeScript first, Python second |

## 9. SDK, what a buyer writes

| Call | Returns |
| --- | --- |
| `human.verify({ image, question, workers: 3 })` | `{ answer: "yes", agreement: 1.0, cost: 0.18, receipt }` |
| `human.choose({ options: [a, b], question })` | `{ index: 1, reason, agreement }` |
| `human.read({ image })` | `{ text, agreement }` |
| `human.answer({ question, minReputation: "gold" })` | `{ text, confidence, worker: { tier, tasks } }` |

The SDK holds a signer for one rail and handles the 402 round trip, so the integration is two lines.

## 10. Economics

| Scenario | Numbers |
| --- | --- |
| One `verify` task, 3 workers at $0.05 | Buyer pays $0.18; workers get $0.15; platform keeps $0.03; gas well under a cent on either rail |
| A worker doing 200 tasks a day | $8 to $15 a day, paid continuously |
| 10,000 tasks a day | About $1,800 a day through the system, $300 a day to the platform |
| Break-even | Hosting and services about $150 a month; covered at roughly 170 tasks a day |

## 11. Risks

| Risk | Mitigation |
| --- | --- |
| Not enough workers online when a task arrives | Live availability in `/v1/pricing`; longer deadlines; a small bonus in low-supply hours |
| Workers game consensus | Gold tasks, tiers, disputes; pay only on agreement |
| Buyers send abusive content | Moderation before routing, blocking, one-tap report by workers (still paid) |
| Regulation on paying contractors in stablecoins | Workers are independent contractors; cap unverified workers at a monthly amount; light KYC above it (open decision F) |
| x402 adoption still early | Prepaid balance with an API key as the second door |
| Robinhood Chain liquidity of USDG for buyers | USDC on Solana is the second door; both are offered in every 402 response |

## 12. Build plan

| Phase | Deliver |
| --- | --- |
| 1 (first) | The two facilitators, tested on testnets with a demo paywalled server and client per rail. See FACILITATORS.md |
| 2 | Task model, ledger, `POST /v1/tasks` on both rails, `verify` and `choose` |
| 3 | Worker bot, router, consensus, batched payouts on both rails |
| 4 | Moderation, gold tasks, reputation, disputes, refunds; `read`, `label`, `rate` |
| 5 | SDK, buyer console, docs, `answer` type; launch |
