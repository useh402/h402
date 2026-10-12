# H402: the complete guide

This is the complete description of how H402 works: the website, the tasks, the people who do them, the software that posts them, the money, the operator tools and the way it all runs. It is written from the code as it is today (October 2026) and from the decisions taken while building it.

The older documents in `docs/` (`DESIGN.md`, `ARCHITECTURE.md`) are the plans and the history. When they disagree with this guide, this guide describes what is built.

## Contents

| # | Chapter | What it covers |
| --- | --- | --- |
| 1 | [Overview](#1-overview) | What H402 is, who takes part, the life of one task in a minute, the rules that never change, where it runs, glossary |
| 2 | [The website](#2-the-website) | Every page: what it shows, who it is for, what you can do there, which calls it makes, sign-in, the announcement, content protection, settings |
| 3 | [How tasks work](#3-how-tasks-work) | Task types, the task spec, where tasks come from, prices and the fee, the full lifecycle with every state and trigger, consensus, the verifier, disputes, cancellation, expiry, refunds, moderation, retention |
| 4 | [Workers](#4-workers) | The earning side end to end: connect a wallet, terms, qualification, the feed, holding a task, answering each type, photo proof, reports, gold checks, reputation and tiers, pauses, earnings, payouts, gas help |
| 5 | [Clients and the API](#5-clients-and-the-api) | The developer surface: paying for a task over x402, every endpoint, buyer tokens, webhooks, receipts, batches, pricing, errors |
| 6 | [Payments and escrow](#6-payments-and-escrow) | Rails and tokens, the facilitator, the TaskEscrow contract, wallet mode and contract mode, how the task service drives the contract, the ledger, payouts, the house pool, the one-copy rule |
| 7 | [Operator](#7-operator) | The operator page, the admin API, the review queue, disputes, reports, gold tasks, the pool, team runs, scripts, a daily checklist |
| 8 | [Architecture and settings](#8-architecture-and-settings) | The three services and the contract, background jobs, the data model, every environment variable with its default |
| 9 | [Running and deploying](#9-running-and-deploying) | Local development, Docker Compose, tests, the Render deployment, health checks |
| 10 | [Policies and known gaps](#10-policies-and-known-gaps) | United States only, copy rules, prohibited tasks, terms and privacy, the training disclosure, secrets, and the places where the site and the code still disagree |

Reading order: new to the project, chapters 1, 3, 2; building something that posts tasks, 5 then 6; running the service day to day, 7, 9, 8; working on site copy or legal pages, 10 then 2.

```text
h402/                       this repository
  web/            the website (Next.js 16, React 19, Tailwind 4, Privy)
  api/            the task service (Python 3.12, FastAPI, SQLAlchemy 2, Alembic)
  deploy/         render.sh, the build, push and deploy script
  docs/           design, architecture, and this guide
facilitator/                github.com/useh402/facilitator: the x402 payment facilitator (Python 3.12, official x402 SDK)
Contract/                   github.com/useh402/Contract: TaskEscrow.sol, the contract that holds and pays rewards
```

Where this guide says `facilitators/` or `contracts/`, it means a checkout of those two repositories.


---

## 1. Overview

### What H402 is

H402 is a marketplace for small pieces of work that need a real person: check a receipt, pick the better option, read a sign, confirm a listing, call a business, go to a place and photograph something. Tasks are posted around the clock with a fixed price. A qualified person in the United States does one in minutes. The reward is held in escrow before anyone starts and is released the moment the work is accepted.

Two sides use it:

- **Workers** (the people doing the work) sign in on the website with a wallet, pass a short qualification, take tasks and are paid in stablecoins to that wallet. No account, no password, no invoices.
- **Clients** are software systems. They post tasks through the API, pay for each one with an x402 payment from a wallet, and receive the answer by polling or by a signed webhook. Nobody posts tasks by hand on the site.

Alongside the clients, the platform posts its own tasks from a funded pool. Five assistants (Claude, ChatGPT, Gemini, Grok and DeepSeek, which the site calls "Sources") propose tasks that only a person can do; an operator reviews and posts them.

H402 is also training its own language model on the work done on the platform. The terms, the privacy policy and the first-visit announcement say so plainly. See [10. Policies](#10-policies-and-known-gaps).

### The parties

| Party | Who | What they do | How they are identified |
| --- | --- | --- | --- |
| Worker | A person in the United States, 18 or older | Takes and answers tasks, submits proof, reports bad tasks | Their wallet (MetaMask or Phantom). The wallet is the payout address |
| Client (buyer) | Software connected through the API | Posts and pays for tasks, accepts or disputes proof, cancels | The wallet that paid, plus a per-task buyer token |
| House | The platform itself | Posts tasks from its funded pool | The buyer record named "H402" with payer `house` |
| Scouts (Sources) | Five assistants reached through the Vercel AI Gateway | Propose tasks; one of them reviews proof and written answers | The `requester` label on a task (claude, chatgpt, gemini, grok, deepseek) |
| Operator | A person on the H402 team | Decides disputes, approves held tasks, approves proposals, runs the pool and the contract | The admin token (`HA_ADMIN_TOKEN`) |

Workers never see who asked. Clients never see who answered.

### The life of one task, in a minute

1. **Posted.** The platform's poster, or a client over the API, creates the task. Client tasks are paid first: the API answers `402 Payment Required` with the exact price, the client pays with x402, and only then does the task exist. Platform tasks are listed from the pool without locking money yet.
2. **Listed.** The task appears on the public board at `/tasks` and in the feed of every worker qualified for that type of work. Place-bound tasks show only to workers in that city.
3. **Taken.** A worker takes it. Short tasks are held for two minutes; action tasks for their whole time limit. For a platform task, the reward plus the 20% fee is reserved from the pool at this point (in contract mode it is locked in the escrow contract).
4. **Answered.** The worker submits an answer or proof. Every response is saved and hidden from other workers until the task is decided.
5. **Decided.** Short tasks (check, choose, rate, read, label) are decided by agreement between the workers who answered. Action and written-answer tasks are reviewed: the client accepts the proof, or the verifier approves it, or it is accepted automatically after an hour. A proof with a photo or screenshot in it is the exception: it is never accepted by the clock or by the verifier; the operator looks at the pictures on the Responses tab and approves or refuses them by hand. Anything wrong or unsure becomes a dispute for the operator.
6. **Paid.** On a platform task the accepted worker presses Claim and the reward is sent from the platform's wallet to theirs at once. On a client task one contract transaction pays the accepted workers, sets the fee aside and returns any unearned money to the payer. The task page links to the transaction either way.
7. **Expired or cancelled.** A task nobody finishes is refunded in full. A client can cancel until someone answers.

The full state machine, with every trigger and timing, is in [3. How tasks work](#3-how-tasks-work).

### Rules that never change

- **United States only.** Every task, place, example and piece of copy is for the United States. Tasks naming India are refused at creation.
- **Nobody posts by hand.** Tasks come from the platform's poster, from the scouts after review, and from software through the API.
- **Pay on acceptance.** Money is held before anyone starts and no one is paid before the work is accepted. Unfilled slots are refunded.
- **Plain professional copy.** Screens real people use speak of clients, tasks, workers and rewards. Technical terms stay in code, in the developer docs and in the operator tools. The one exception is the model-training disclosure in the terms, the privacy policy and the announcement.
- **Team activity is labelled.** Test runs by the team's own wallets are marked "H402 team" everywhere and are kept out of the public totals.
- **Secrets stay out of the repository.** Keys live in ignored settings files and are never printed or logged.

### Where it runs

Public, on Render, from Docker images in a container registry:

| Service | Address |
| --- | --- |
| Website | https://humanapi-web.onrender.com |
| Task service (API) | https://humanapi-api.onrender.com |
| Facilitator | https://humanapi-facilitator.onrender.com |

Money is on Robinhood Chain mainnet (chain id 4663):

| Item | Value |
| --- | --- |
| Reward token | USDG `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168` (6 decimals) |
| TaskEscrow contract | `0x530C2beDB048a658cB9fFD074eB7A75D68bfBd90` |
| Owner, operator and treasury wallet | `0xAd576D84708597616510186DAAc39D4aEF559a14` |
| Facilitator signer (gas only) | `0x60F02A52451ce6dDCA7C32A1390eabFEc0BB7b9E` |
| Explorer | https://robinhoodchain.blockscout.com |

Solana (USDC) exists in the sign-in, the facilitator and the payout code, but there is no contract, no browser payment and no gas help on it yet. The site describes it as "coming next".

### Glossary

| Term | Meaning |
| --- | --- |
| Task | One unit of work with a type, a payload, a price per worker, a number of workers wanted and a deadline |
| Type | One of `verify` (Check), `choose`, `rate`, `read`, `label`, `answer`, `do` (Action task) |
| Category | The kind of work, for example `calls`, `go_and_see`, `judgement`; 15 in all |
| Slot | One of the `workers` places on a task. A task wanting 3 workers has 3 slots |
| Hold (claim) | A worker's reserved slot while they answer. Two minutes for short tasks, the time limit for action tasks |
| Claim (a reward) | The button an accepted worker presses on a platform task to have the reward sent from the platform's wallet to theirs at once |
| Proof | What an action task returns: a note, a screenshot, photos, or a note plus an image |
| Capture code | A four-character code shown when a photo task is taken; it must appear in every photo |
| Consensus | The rule that decides a short task from several answers: majority, median or match |
| Verifier | The assistant that reviews proof and written answers; it approves or hands the task to a person |
| Dispute | A task waiting for an operator's decision |
| Gold task | A known-answer check slipped into a worker's feed to measure accuracy |
| Reputation, tier | A worker's score and level (new, bronze, silver, gold) from agreement and gold accuracy |
| Buyer token | The `bt_…` secret returned when a task is paid; it alone lets software accept, dispute or cancel that task |
| Quote | The price of a task body, valid five minutes, matched when the payment arrives |
| Rail | A chain plus its token: Robinhood Chain with USDG, Solana with USDC |
| Facilitator | The service that verifies and settles x402 payments on chain and pays the gas |
| Escrow contract | TaskEscrow on Robinhood Chain: holds rewards, pays workers, keeps the fee, refunds the rest |
| House, pool | The platform's own buyer and its funded balance for platform-posted tasks |
| Scouts, Sources | The five assistants that propose tasks |
| Team run | An end-to-end payment test by the team's own wallets, labelled and excluded from public totals |
| Amounts | The API counts money in millionths of a dollar: `1500000` is $1.50 |


---

## 2. The website

The website is a Next.js 16 app in `web/`. It is the only screen workers use, the public window on the board and the money, and the operator's console. It has no server-side logic of its own: every page talks straight to the task service (`NEXT_PUBLIC_API_URL`) from the browser, and all live behaviour is polling on a timer.

### Pages at a glance

| Path | For | What it is |
| --- | --- | --- |
| `/` | Everyone | Landing page: hero, live payments ticker, a practice task, introduction, live numbers, FAQ, trust section |
| `/tasks` | Everyone, workers | The board: every open task with filters, a Completed tab, an Activity tab and a How-it-works tab |
| `/tasks/[id]` | Everyone, workers | One task: details, requirements, take it and answer in place, the saved responses with their reward links |
| `/map` | Everyone | A globe with a pin for every open task that has a place |
| `/rewards` | Everyone | Total rewards paid, the live pool, task counts, the contract address, the latest payments |
| `/scouts` (nav label "Sources") | Everyone, operator | Where tasks come from: one card per assistant, the proposal feed, operator approve or refuse |
| `/earn` | Workers | Connect a wallet and start |
| `/earn/qualify/[type]` | Workers | Worker terms, then the three practice questions for one type of work |
| `/earn/tasks` ("My list") | Workers | The worker's own feed with task cards, take, answer, skip, report |
| `/earn/earnings` | Workers | Pending, today, this week, paid out; the payouts table; send USDG; gas help |
| `/client` | Clients | Sign in with the wallet your software pays from |
| `/client/tasks` | Clients | Every task that wallet paid for, with states and money |
| `/client/tasks/[id]` | Clients | One task: what was asked, the answer or proof, accept or dispute, cancel, money, timeline, buyer token |
| `/client/docs` | Developers | The public integration guide ("Connect your software") |
| `/operator` | Operator | Disputes, proposals, tasks held for review, reports, contract and pool controls |
| `/terms`, `/privacy`, `/contact` | Everyone | Legal pages and contact |

Routes that do not exist, so nobody looks for them: there is no `/earn/rewards`, no `/earn/map`, no receipt page on the site (receipts are served by the API at `/v1/receipts/{id}`), and no page for posting a task. Posting is by the platform and by software only.

### Navigation

The top bar links to Tasks (`/tasks`), Map (`/map`), Rewards (`/rewards`), Sources (`/scouts`) and How it works (`/#introduction`), shows a "Paid per task" pill, a "See the board" button and the wallet button. The mobile menu adds "Start earning" (`/earn`).

The wallet button reads "Connect wallet". Once connected it shows the short address (click to copy) with a menu: Open tasks, My tasks, Earnings, Disconnect. If the connected wallet has not accepted the worker terms or has no qualified type yet, connecting sends it to `/earn/qualify/verify`.

The footer carries the tagline "Real people, paid per task.", links to Open tasks, Earn, Connect your software (`/client/docs`) and Contact, a live clock, and the Privacy Policy and Terms links.

A "not found" page says the task may have closed or the address may be wrong and links to the open tasks.

### The first-visit announcement

A full-screen notice is mounted from the root layout, so it can appear on any page, and is shown once per browser (localStorage key `humanapi.notice.v1`). Its title is "Before you start, three things you should know." and it states:

1. Your responses train models (H402's and its partners'); the wallet address is kept out of training data.
2. Responses are checked by assistants from several providers (Claude, ChatGPT, Gemini, Grok, DeepSeek) and compared with other people's answers; an operator decides what the assistants cannot.
3. Rewards are paid on chain to your wallet, in USDG on Robinhood Chain, when a response is accepted; payments cannot be reversed; tasks are for the United States only.

Buttons: "Leave" (goes to google.com) and "I understand, continue". The line underneath links to the Terms of Use and Privacy Policy.

### The landing page, section by section

- **Hero.** A WebGL smoke background with a cursor ink trail. Headline "Work that pays on delivery". Subtitle: new tasks are posted around the clock, real people do them in minutes and are paid the moment the work is accepted. Button "See open tasks".
- **Ticker ("Paid on chain").** A moving strip of the latest real payments from `GET /v1/rewards`: "$X paid to 0xabcd…1234 for 'title'", with a "H402 team" badge on test-run payments. Hidden when there are no payments yet.
- **Try one.** A practice Check task at $2.00 with three built-in questions. The visitor answers yes or no and watches the four rows every real task goes through: Your answer, Two other people, Decision, Reward. Nothing is paid and no API call is made. It ends with "Real tasks pay in USDG on Robinhood Chain, straight from the contract."
- **Introduction (`#introduction`).** Scroll-highlighted text explaining the board, that tasks are posted by the platform and by connected software, never by hand, with the price fixed up front, held in escrow, shown only to qualified people and checked against other answers; and that workers sign in with a wallet, pass a short qualification and are paid in stablecoins every few minutes.
- **H402, live.** Three animated counters from `GET /v1/rewards`: Rewards paid (with payments and wallets counts, and how much came from the team's own tests), Tasks open right now, Waiting to be earned (the value of open tasks). Each links to the board or the rewards page.
- **FAQ.** Eight questions: what H402 is, what kinds of tasks, how you get paid, when work is paid, what happens if the client disagrees, who posts the tasks, what a task can never ask for, and how to start.
- **Trust.** The client pays before anyone starts, no one is paid before the work is accepted, every payment is in escrow on chain, answers are checked against each other, undelivered work is refunded. Badges: x402 ("Payments over the open x402 protocol"), Robinhood Chain ("Rewards in USDG, held by the contract"), Solana ("USDC on Solana, coming next").

### The board (`/tasks`)

Refreshes every 20 seconds from `GET /v1/tasks/open?limit=200`, `GET /v1/stats` and `GET /v1/activity`, plus `GET /v1/catalogue` once.

- **Header chips:** United States, USDG · USDC, the number of kinds of work in the catalogue, "New every 5 min", the service fee percentage.
- **Stats:** lowest and highest price, paid out in 24 hours and in total, open now, workers online and joined.
- **Tasks tab.** Filters by status (All, Slots open, Action tasks), type of work, price band, Remote only, and category; a search box; sort by recently posted, price, or ending soon; three card densities. A card shows the task's image or the requester's mark, the type badge, slots left of workers wanted, title, category, place, the requester ("for Claude" and so on), the price, time left and the estimated minutes.
- **Completed tab.** Finished tasks with the amount paid, the agreement percentage and a link to the payment on chain (or "Paid in a batch").
- **Activity tab.** A table of recent decided tasks: type, place, paid per worker, decided by, result, when.
- **How it works tab.** Three cards: pick a task; do it and show it; get paid when accepted.
- **Sticky bar.** Live open count, value to be earned, workers online, "Post tasks from software" (`/client/docs`) and "Start earning" (`/earn`).

If the API cannot be reached the board says so and keeps retrying on its own.

### One task (`/tasks/[id]`)

Polls `GET /v1/tasks/open/{id}` and `GET /v1/tasks/{id}/comments` every 10 seconds.

- **Details panel:** type, category, where (with an "Open in Maps" link), difficulty, how long it takes, time limit, people wanted and slots open, when it was listed, when it ends, who it is for.
- **Price box:** "Pays, per person" and when it is paid (for example "Paid when it agrees with the other answers"), plus "Payouts go to your wallet every ten minutes."
- **Action button:** "Take this task", or "Qualify for Check first" (sends the worker to `/earn/qualify/{type}?next=/tasks/{id}`), or "Sign in to take it" with an inline sign-in, or "You hold this task", or "No longer open".
- **What you will do:** the task content. It is wrapped in the content-protection layer (see below).
- **Requirements:** the qualification needed, the proof asked for, when it is accepted, when it is paid, the location rule (Remote, in the city, or an exact spot whose photos are checked against the location), the time allowed once taken, the minimum reputation and the type's rules.
- **When held:** the full task card appears in place and the worker answers right there (`POST /v1/tasks/{id}/claim`, `/answer`, `/release`, and `/photos` for photo tasks).
- **Responses:** how many are saved. Until the task is decided only the worker's own response is visible ("saved and hidden until this task is decided, so that everyone answers on their own"). After the decision each response shows an anonymous author label ("Worker ab12"), the tier, the time taken, the outcome, the response, any screenshot, the note and the reward with a link to the transaction. On the worker's own accepted response to a platform task a "Claim reward" button appears until the reward is claimed; everyone else sees "Reward ready to claim". Responses older than 30 days show "Removed after 30 days."

### The map (`/map`)

A three.js globe with the open tasks that have a place, from `GET /v1/tasks/map` every 30 seconds. Gold pins are exact spots (a photo must be taken there), blue pins are anywhere in that city, a cyan pin is the visitor's own location after "Show my location". City chips, distance from the visitor, "Show on globe", "Open in Maps" and, for exact spots, "Street View" links. Remote tasks are counted in a line of text.

### Rewards (`/rewards`)

From `GET /v1/rewards` every 30 seconds: total rewards paid, the live pool, tasks all time (completed, open, expired and refunded), where the paid rewards went (to workers, in team test runs, service fee earned), the contract address with an explorer link, and the latest 25 payments with task, wallet, reward, time and transaction.

### Sources (`/scouts`)

"Five assistants, looking for work only people can do." From `GET /v1/scouts` every 8 seconds: whether searching is on, how often, calls used today, whether accepted proposals post automatically or an operator approves each one; one card per assistant with its model and counts on board, waiting and refused; the proposal feed with title, requester, type, location, "Why a person", the price and a link to the task once posted. Filters: all, waiting for review, on the board, not accepted.

An operator box takes the operator key (stored as `humanapi.operator.key`) and then shows "Search now" (`POST /v1/admin/scouts/run`) and, on each proposal in review, Post and Refuse (`POST /v1/admin/scouts/proposals/{id}`).

### Sign-in

Sign-in is by wallet signature. Nothing else is collected.

1. The site asks the API for a nonce: `POST /v1/workers/nonce` (or `/v1/clients/nonce`) with the wallet and network.
2. The wallet signs the returned message ("H402 wants you to sign in with your wallet… costs nothing and sends nothing").
3. The site sends the signature to `POST /v1/workers/session` (or `/v1/clients/session`) and receives a token.
4. The token is kept in the browser's localStorage: `humanapi.worker.token` for workers, `humanapi.client.token` for clients. No cookies are used. A session lasts 30 days.

Two wallet paths exist:

- **With Privy** (`NEXT_PUBLIC_PRIVY_APP_ID` set, which is the production setup): the Privy modal with wallet login only, MetaMask and Phantom in the list, embedded wallets off. The sign-in always uses the Robinhood Chain network. Privy accepts Ethereum, Base, Polygon, Sepolia and both Robinhood chains for the signature because Phantom refuses other networks; rewards are still paid on Robinhood Chain to the same address.
- **Without Privy:** raw browser wallets. One button per rail: Robinhood Chain (`window.ethereum`, `personal_sign`) and Solana (`window.solana`, ed25519 `signMessage`). This is the only place the Solana rail is reachable from the site.

A local dev sign-in box ("Local sign-in without an account", a `0x…` address and Go) appears when `NEXT_PUBLIC_DEV_LOGIN=1`; the API accepts it only with `HA_ENV=local` and `HA_DEV_LOGIN=true`.

"Sign out" clears the token (and logs out of Privy). "Export this wallet's key" appears only for Privy embedded wallets, which are off.

### The Earn area

All `/earn` pages share a shell that loads `GET /v1/workers/me`, sends a heartbeat (`POST /v1/workers/heartbeat`) every 30 seconds while signed in, and redirects: not signed in goes to `/earn`; signed in and qualified goes to `/tasks`; signed in and not qualified goes to `/earn/qualify/verify`. A paused worker sees "Your account is paused" with the reason and the note that pending earnings are kept.

The shell's own links are Open tasks, My list, Types of work and Earnings. The badge shows the rail (Robinhood or Solana), the short wallet and Sign out.

- **`/earn`.** "Get paid for judgment." Three bullets (connect MetaMask or Phantom; paid in batches every ten minutes; a short qualification per type) and the button "Connect wallet and start earning".
- **`/earn/qualify/[type]`.** First the worker terms gate ("Before your first task"): you do the work yourself, one person one account; paid when accepted; nobody knows who you are, report bad tasks with one tap and still be paid; money goes to your wallet in batches; you are an independent contractor and handle your own taxes. Checkbox and Continue (`POST /v1/workers/profile` with `acceptTerms`). Then, per type: an intro (what it is, pays, takes, accepted when, how to do it well), "Start the three questions", three practice cards rendered exactly like real tasks, and the result: two of three right unlocks that type. The sidebar shows "n of 7 unlocked". Practice can be repeated any time.
- **`/earn/tasks`.** Polls `GET /v1/workers/tasks` every 4 seconds; cards grouped by category with price, preview, workers wanted and a countdown. Clicking a card takes it (`POST /v1/tasks/{id}/claim`); the active card is wrapped in the protection layer and watermarked with the wallet. Skip releases the hold; Report asks for a reason. After submitting, a toast says one of: accepted and added to pending; submitted but the other answers did not match; proof submitted and the client has up to an hour; submitted and paid once the other answers are in and match.
- **`/earn/earnings`.** Polls `GET /v1/workers/earnings` every 10 seconds. Cards for Ready to claim (with the number of rewards waiting), Today, This week and Paid out; the payout wallet with Copy; a "Rewards ready to claim" panel listing each accepted platform task with a Claim button ("Each claim sends the reward from the platform wallet to yours, on chain, straight away"), which calls `POST /v1/tasks/{id}/claim-reward` and then shows "$X sent to your wallet." with a transaction link; the Send USDG panel (see below); the payouts table (when, task, amount, status, transaction); and the worker's tier, accepted/answered, reputation and gold-check score.

The task card itself and the photo-proof flow are described in [4. Workers](#4-workers).

#### Send USDG and gas help

The "Send USDG" panel appears for Robinhood workers on mainnet. It reads the wallet's USDG and ETH balances straight from the Robinhood RPC every 15 seconds. If the wallet holds less than 0.000006 ETH, a first button "1. Cover the gas" calls `POST /v1/workers/gas`, which asks the facilitator to send a little ETH (once a day, only to wallets that have already been paid). Then "Send USDG" switches the wallet to chain 4663 and sends an ERC-20 transfer to the address given, with a link to the transaction.

### The client area

The client shell loads `GET /v1/clients/me` and redirects signed-out visitors to `/client` (except `/client/docs`, which is public) and signed-in ones from `/client` to `/client/tasks`.

- **`/client`.** "Your software, a real person." Tasks are posted by software, not by hand; three people per short task, paid only when they agree; action tasks come back with proof to accept or dispute within an hour; every task has a public receipt; posting is by API only. A sign-in panel for the wallet the software pays from, and "I want to earn instead".
- **`/client/tasks`.** Polls every 5 seconds. Open (open + claimed + submitted), Done, Refunded (expired + rejected + cancelled), Spent with refunds due. A state filter and a table (task, type, where, price, state, posted). The states are labelled for people: Waiting for workers, Being worked on, Proof in and your decision, Done, Expired and refunded, Refused and refunded, Cancelled and refunded, In dispute.
- **`/client/tasks/[id]`.** Polls every 5 seconds. What you asked (payload and acceptance); the answer, or the proof with its screenshot; while a proof is in, "Accept this proof or dispute it before {time}" with Accept and Dispute (a reason of at least 10 characters); how it was decided (method, outcome, checks); actions: Cancel and refund (until someone answers), Dispute the answer (short tasks, within 24 hours of done), Public receipt; money (per worker, workers, fee, paid, refund); the timeline; and "For your software": the task id and the buyer token. These browser actions authenticate with the client session rather than the buyer token.
- **`/client/docs`.** The integration guide, reproduced in [5. Clients and the API](#5-clients-and-the-api).

### The operator page (`/operator`)

Takes the operator key (localStorage `humanapi.operator.key`, sent as `Authorization: Bearer`). Refreshes every 30 seconds. Tabs with counts: Disputes (uphold or reject with an optional note), Proposals (post or refuse), Held for review (approve, or reject and refund, with the moderation reason and the payload), Reports (display only), and Money: the contract (holds, locked for tasks, fees waiting, operator gas, tasks on chain, "Run settlement now") and the pool for platform tasks (available, open tasks, spent today of the daily budget, automatic posting on or off, "Post a batch of tasks", "Run the verifier"). Details in [7. Operator](#7-operator).

### Content protection

Task content is shown inside a protection layer on the task page and on the worker's active card. It blocks copy, cut, drag and the context menu; blurs the content when the tab is hidden or the window loses focus, and for a moment on screenshot shortcuts (clearing the clipboard as well); blocks Ctrl/Cmd + C, X, P, S and A outside inputs; overlays a tiled watermark of the worker's wallet; and the whole site refuses to print. The layer shows "Task content is hidden while this page is not in front. Click here to continue."

### Legal and contact pages

- **Terms of Use** (last updated October 10, 2026): who can work (18+, United States, independent), rewards paid when accepted in USDG from a contract with the fee paid by the client on top, honesty rules (no guessing, no software answering for you, photos taken by you at the stated time and place with the capture code, one person one wallet), the content licence, the training and automated review section naming the providers, disputes decided by an operator, no warranty, changes, contact.
- **Privacy Policy:** what is kept (wallet address, responses with timing, photo location only to verify the place, record and reputation, on-chain payments), what is not collected (name, email, phone, ID), who sees what (client, visitors, operators, review assistants, model training with de-identified data), retention (task content and responses removed 30 days after the decision, photos within 90 days), US hosting with photos at a separate provider, choices, and that only a sign-in token is stored in the browser.
- **Contact:** contact@h402.io; include the task address and your wallet; payments are all on Robinhood Chain and listed on the Rewards page; report a task with the Report link while holding it; developers go to Connect your software.

### Polling intervals

| Page | Interval |
| --- | --- |
| `/earn/tasks` | 4 s |
| `/client/tasks`, `/client/tasks/[id]` | 5 s |
| `/scouts` | 8 s |
| `/earn/earnings`, `/tasks/[id]` | 10 s |
| Send USDG panel (chain balances) | 15 s |
| `/tasks`, landing numbers and ticker | 20 s |
| `/rewards`, `/map`, `/operator` | 30 s |
| Worker heartbeat | 30 s |

There is no server-sent events or WebSocket channel.

### Browser storage

| Key | Holds |
| --- | --- |
| `humanapi.worker.token` | worker session token |
| `humanapi.client.token` | client session token |
| `humanapi.operator.key` | operator key |
| `humanapi.notice.v1` | the announcement was accepted |

### Settings the site is built with

These are `NEXT_PUBLIC_*` variables, compiled into the bundle at build time, so they are passed as Docker build arguments.

| Variable | Meaning | Default in code | In the production image |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Where the task service is | `http://127.0.0.1:8400` | `https://humanapi-api.onrender.com` |
| `NEXT_PUBLIC_ROBINHOOD_NETWORK` | Which Robinhood chain to sign in on; Send USDG shows only on `eip155:4663` | `eip155:46630` (testnet) | `eip155:4663` |
| `NEXT_PUBLIC_SOLANA_NETWORK` | Solana network for the raw-wallet path | devnet | not set |
| `NEXT_PUBLIC_PRIVY_APP_ID` | Turns Privy on | empty (raw wallets) | set from `web/.env.local` |
| `NEXT_PUBLIC_DEV_LOGIN` | Shows the local sign-in box when `1` | unset | `0` |

Hard-coded in the site: the Robinhood RPC and explorer URLs, the Permit2 address, the x402 proxy address and the USDG token address.

### Stack

Next 16.4 with `output: "standalone"`, React 19.3, Tailwind 4, Framer Motion 14, Privy React Auth 3.48, three.js 0.170, lucide icons. Fonts Inter and Source Serif 4. The Docker image is three-stage on node:22-alpine, runs as a non-root user on port 3000 and health-checks `/`.


---

## 3. How tasks work

A task is one unit of work: a type, a payload, a price per worker, how many workers are wanted, a time limit and a deadline. This document follows a task from the moment it is created to the moment the money moves.

Amounts in the API are millionths of a dollar: `1500000` is $1.50.

### Task types

| Type | On the site | The worker gets | The worker returns | Base price | Default workers | Allowed workers | Time limit | Decided by | Min. reputation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `verify` | Check | An image or text and a yes/no question | yes, no or unsure | $0.08 | 3 | 1, 3, 5 | 2 min | majority | 0 |
| `choose` | Choose | 2 to 5 options and a question | The index of the best option | $0.10 | 3 | 1, 3, 5 | 2 min | majority | 0 |
| `rate` | Rate | An item and a rubric | A score 1 to 5 | $0.05 | 3 | 1, 3, 5 | 2 min | median | 0 |
| `read` | Read | An image of text | The text, typed exactly | $0.20 | 2 | 1, 2, 3 | 5 min | match | 0 |
| `label` | Label | An item and 2 to 30 labels | One or more labels | $0.05 | 3 | 1, 3, 5 | 2 min | majority | 0 |
| `answer` | Answer | A short question needing local or human knowledge | Free text plus a confidence | $0.50 | 1 | 1 | 15 min | single, reviewed | 0.9 |
| `do` | Action task | Instructions, an optional link, what proof is wanted | Proof: a note, a screenshot, photos, or note plus image | $1.00 | 1 | 1, 2 | 30 min | proof: client acceptance, verifier, or auto-accept after 1 h | 0.8 |

The base prices are floors. The minimum reward actually paid is $1.50 (`HA_MIN_REWARD`), and the platform's own formula prices most work between $5 and $20. See "Prices and the fee" below.

There is no separate photo type. A photo task is a `do` task whose payload says `proof: "photos"`.

#### Payload per type

| Type | Required payload fields | Optional |
| --- | --- | --- |
| all | `category` (one of the 15 categories) | `image` |
| `verify` | `question`, and `image` or `text` | |
| `choose` | `question`, `options` (2 to 5, text or image URLs) | |
| `rate` | `item`, `rubric` | |
| `read` | `image` | |
| `label` | `item`, `labels` (2 to 30) | |
| `answer` | `question` | |
| `do` | `instructions` (20 to 4000 characters), `proof` (`text`, `screenshot`, `both` or `photos`) | `url` (http or https, up to 2000 characters), `geo {lat, lng}` for an exact spot |

The payload may be at most 64,000 bytes of JSON.

#### Answer per type

| Type | Valid answer |
| --- | --- |
| `choose` | an integer index |
| `verify` | `yes`, `no` or `unsure` |
| `rate` | a number from 1 to 5 |
| `label` | a non-empty subset of the given labels |
| `read`, `answer` | non-empty text up to 4000 characters |
| `do` | an object `{text, screenshot, photos}`: `text` of at least 5 characters for proof `text` or `both`; a `screenshot` (an https link up to 2000 characters, or a `data:image/` URL up to 2,000,000 characters) for `screenshot` or `both`; 1 to 3 `photos` ids taken under the current hold for `photos` |

Every answer may carry a `note` and a `confidence`.

### The task spec

Beyond type and payload, a task carries:

| Field | Meaning | Rules |
| --- | --- | --- |
| `title` | What the card shows | Up to 140 characters; defaults from the question, instructions or item |
| `location` | Where the work is | `Remote`, or `City, ST` with a real US state or DC. "united states", "us", "usa" and "anywhere" become Remote |
| `acceptance` | What makes the work acceptable; shown to the worker | Up to 2000 characters |
| `difficulty` | easy, medium or hard | Defaults to medium for `do`, easy otherwise |
| `effortMinutes` | Estimated effort | 1 to 240; defaults: do 15, answer 5, read 2, others 1 |
| `templateId` | Which catalogue template it came from | Up to 20 characters |
| `requester` | Which assistant it is for | claude, chatgpt, gemini, grok or deepseek |
| `workers` | Slots wanted | Must be in the type's allowed set |
| `pricePerWorker` | Reward per slot | From $1.50 (the minimum) to $50 (`MAX_PRICE_PER_WORKER`); at least the type base |
| `minReputation` | Who may take it | 0 to 1; raised to the type's minimum |
| `timeLimitSeconds` | How long a worker has once they take it | 30 to 10,800 |
| `listSeconds` | How long it stays listed | 60 seconds to 7 days; the deadline is creation plus listSeconds (or the time limit if not given) |
| `webhook.url` | Per-task webhook | https |
| `reference` | The client's own reference | Up to 120 characters |

#### Categories

Fifteen categories of work, each with a label, the human need it answers, and examples: `calls`, `go_and_see`, `blocked_sites`, `forms_and_listings`, `real_and_current`, `documents_and_receipts`, `judgement`, `local_knowledge`, `community_resources`, `accessibility`, `business_research`, `research_and_verification`, `technical`, `web3`, `sorting_and_tagging`. The public list is at `GET /v1/catalogue`.

#### United States only

Everything is checked at creation. The title, location and payload are scanned for anything naming India (cities, rupees, Aadhaar, UPI, Paytm, Flipkart, Zomato, Swiggy, IRCTC, GSTIN, pincodes, lakh and crore, Hindi, +91 numbers) and refused with "tasks are for the United States only". Locations must normalise to Remote or `City, ST`. About 51 US cities have coordinates on file so that a task with a city shows on the map and is filtered by the worker's location.

### Where tasks come from

Nobody posts a task by hand on the website. Three sources exist.

#### 1. The platform's poster (the house)

The platform has its own buyer record (name "H402", payer `house`) and a funded pool. Every 5 minutes (`HA_HOUSE_INTERVAL_SECONDS`, when `HA_HOUSE_POSTER_ENABLED=true`), or on demand from the operator page, a round runs:

1. Stop if the open platform tasks are already at the cap (240, `HA_HOUSE_MAX_OPEN`) or today's spend has reached the daily budget ($2,000, `HA_HOUSE_DAILY_BUDGET`).
2. Shuffle the house catalogue, leaving out titles already open.
3. For each candidate: build the task with a 40-minute time limit, a requester rotated through the five assistants, a price of max(minimum reward, formula price), and a 24-hour listing (`HA_HOUSE_LIST_SECONDS`). One action task in five (`HA_SECOND_WORKER_EVERY`) wants 2 workers as an independent cross-check.
4. Skip anything moderation rejects. At most 2 open tasks per template (or per title).
5. Post up to 3 (`HA_HOUSE_BATCH_SIZE`).

The house catalogue has 351 concrete US tasks: 12 starters, 71 typed tasks in `manual_tasks.py` (calls, questions to ask at a counter, pages to open as a person and read out, forms, local knowledge, text to copy out exactly, and judgement tasks), 178 more across every category in `catalogue_more.py`, 90 per-city variants of community and research tasks across 20 cities, and 30 photo tasks in `photo_tasks.py` (12 go-and-see places with coordinates, 8 at-home, 10 one-dollar quick checks). By type: 320 action tasks, 18 choose, 4 verify, 4 rate, 3 label, 2 read.

Most of the board is typed work: 238 tasks are answered in writing and 113 carry a picture (94 camera photos, 19 text plus screenshot). Every photo task also names what the person has to type (`payload.write`), so a photo alone is never a complete answer; the operator reads the text against the picture. Each house batch holds at most `HA_HOUSE_PICTURES_PER_BATCH` picture tasks (default 1 of 3), so the live board stays mostly typed work.

A platform task is **listed without money behind it** (`chain_state = listed`). The reward and fee are reserved from the pool the moment a worker takes it. In the default wallet mode (`HA_HOUSE_PAYOUT=wallet`) the reservation is in the books and the reward is sent from the platform's wallet when the worker claims it; in contract mode it is locked in the escrow contract. See [6. Payments](#6-payments-and-escrow).

#### 2. The scouts (Sources)

Every 15 minutes (`HA_SCOUT_INTERVAL_SECONDS`, when `HA_SCOUTS_ENABLED=true` and `HA_AI_GATEWAY_API_KEY` is set), each of the five assistants is asked through the Vercel AI Gateway to propose tasks it cannot do itself. Up to 3 proposals per run, at most 200 gateway calls a day.

Every proposal is treated as untrusted and checked: it is mapped onto a task body (instruction-style verify, answer or choose proposals become `do`), refused if it is a `read` task, if it contains a phone number, a street address or a link, if it is invalid, if the title is under 12 characters, if moderation does not allow it, if it duplicates an open title or a proposal from the last 7 days (Jaccard similarity 0.6 or more), or if the chatbot gate says a chatbot could do it alone. The price always comes from the platform formula, never from the model.

Accepted proposals wait for review (`review`) unless `HA_SCOUT_AUTO_POST=true`. An operator posts or refuses them on `/scouts` or `/operator`. Posting draws on the house pool. The proposing assistant becomes the task's `requester`.

#### 3. Software through the API

A client posts `POST /v1/tasks` (or a batch of up to 100) and pays with x402. The task exists only after the payment is settled. Full detail in [5. Clients and the API](#5-clients-and-the-api).

#### Templates versus live tasks

`GET /v1/catalogue/templates` lists 100 seed problems (`HUM-001` to `HUM-065`, `TEC-066` to `TEC-085`, `WEB-086` to `WEB-100`), each with a title, a place, a category, a type and a proof kind. They carry no price and are never live tasks. A template becomes a task only when a client funds a concrete case or the house catalogue carries a concrete version of it.

#### Team runs

The team tests the payment path on mainnet with its own wallets (`POST /v1/admin/team/run` and `api/scripts/team_run.py`). Those tasks are marked `teamRun` and those wallets `team`; the site shows a "H402 team" badge and the public totals leave them out.

### Prices and the fee

**What a client pays.**

```text
pool  = pricePerWorker × workers
fee   = ceil(pool × 20%)            HA_PLATFORM_FEE_BPS = 2000
total = pool + fee
```

A task of 3 workers at $1.50 costs $4.50 plus $0.90, so $5.40. The fee is paid by the client on top; nothing is deducted from the worker's reward. If `pricePerWorker` is omitted it is raised to the $1.50 minimum; an explicit price below the minimum is refused.

**The platform formula** (`standard_price`), used for house tasks, scout proposals and team runs:

| Type | Price |
| --- | --- |
| verify, choose, rate, label | $1.50 + $0.50 × minutes (minutes clamped to 1 to 3), so $2 to $3 |
| read | $3.00 |
| answer | $5.00 + $0.30 × minutes (clamped 2 to 10), so $5.60 to $8 |
| do | $5.00 + $0.30 × minutes (clamped 5 to 45), so $6.50 to $18.50, plus $1 for `blocked_sites`, $3 for `calls`, $25 for `go_and_see` |

The result is clamped to the type base at the bottom and $50 at the top. A phone call of 12 minutes prices at $11.60; a go-and-see photo task of 35 minutes at $40.50.

**Quotes.** The price of a task body is fixed in a quote (`qt_…`) that lives 5 minutes (`HA_QUOTE_TTL_SECONDS`). The same body within that window reuses the same quote. When the payment arrives it is matched to the quote by the body hash and the amount.

**What is paid out when a task is decided** (`settle_money`):

- each agreeing worker receives `pricePerWorker`;
- the fee earned is `min(fee, ceil(fee × answered / workersWanted))`, counting every answer whether it agreed or not;
- whatever is left (`held − paid − feeEarned`) is refunded to the payer as "unfilled slots".

Example: 3 slots at $0.08 with one disagreeing answer pays two workers $0.08 each, keeps a $0.048 fee and refunds $0.08.

On a platform task each agreeing worker's reward is marked **ready to claim** and is sent when they press Claim. On a client task it is paid by the contract's settlement transaction.

### The lifecycle

#### States

| State | Meaning | On the client page |
| --- | --- | --- |
| `paid` | Payment settled (or house money booked); the task exists but is not routed yet. A task that moderation holds stays here | |
| `open` | Listed; workers can take it | Waiting for workers |
| `claimed` | At least one worker holds a slot | Being worked on |
| `submitted` | At least one answer is in | Proof in, your decision |
| `done` | Decided and paid | Done |
| `disputed` | Waiting for an operator | In dispute |
| `expired` | Deadline passed or undecidable; refunded in full | Expired, refunded |
| `rejected` | Refused by moderation or the operator; refunded in full | Refused, refunded |
| `cancelled` | Cancelled by the client or operator before any answer; refunded in full | Cancelled, refunded |

`done`, `expired`, `rejected` and `cancelled` are terminal.

#### Transitions

```text
paid      -> open | rejected | cancelled
open      -> claimed | expired | rejected | cancelled
claimed   -> open | submitted | expired
submitted -> done | expired | claimed | disputed
done      -> disputed
disputed  -> done | expired
```

Only one module (`states.py`) writes the state. Every move records an event (from, to, reason, actor) that appears in the task's timeline and receipt. Entering a terminal state stamps `completedAt` and schedules the purge 30 days later.

#### What triggers each move

| Move | Trigger |
| --- | --- |
| created → `paid` | The x402 payment settled, or the house booked the money (or listed the task) |
| `paid` → `open` | Moderation allowed it ("routed"); or an operator approved a held task |
| `paid`/`open` → `rejected` | Moderation rejected it; or an operator rejected a held task. Full refund. A client with 2 rejected tasks (`HA_MODERATION_BLOCK_AFTER`) is blocked |
| `open` → `claimed` | The first worker takes a slot |
| `claimed` → `open` | The last hold is released or expires with no answer |
| `claimed` → `submitted` | The first answer or proof arrives. Further answers stay in `submitted` |
| `submitted` → `done` | Consensus reached, or proof accepted (by the client, by the verifier, by auto-accept, or by an operator rejecting a dispute). Money settles first |
| `submitted` → `disputed` | The client rejects the proof; or the verifier says wrong or unsure |
| `done` → `disputed` | The client disputes within 24 hours (`HA_DISPUTE_WINDOW_SECONDS`) |
| `disputed` → `done` | The operator rejects the dispute (the work stands), or upholds a dispute on an already-paid task (the client is refunded from the fee pool) |
| `disputed` → `expired` | The operator upholds a dispute on a proof that was never accepted: full refund, the worker is not paid |
| any live state → `expired` | The deadline passes with no answers, or with answers that cannot decide. Full refund. A `do` task with a proof already in does not expire; its acceptance window governs it |
| `paid`/`open`/`claimed` → `cancelled` | The client (with the buyer token or the client session) or the operator cancels, and no answer exists. Holds are released, full refund |

#### Timing

| What | Value | Setting |
| --- | --- | --- |
| Hold on a short task | 120 s | `HA_CLAIM_HOLD_SECONDS` |
| Hold on an action task | the task's time limit, capped at the deadline | |
| Auto-accept of an action task's proof | 1 hour after submission; never for a proof with photos or a screenshot (the operator approves those) | `TASK_TYPES["do"]["accept_window"]`, not configurable |
| Dispute window after `done` | 24 hours | `HA_DISPUTE_WINDOW_SECONDS` |
| Quote validity | 5 minutes | `HA_QUOTE_TTL_SECONDS` |
| Platform listing | 24 hours | `HA_HOUSE_LIST_SECONDS` |
| Purge of content | 30 days after a terminal state | fixed in code (`HA_RETENTION_DAYS` exists but is unused) |
| Photo storage | at most 90 days (Redis TTL); purged at 30 days with the task | |
| Background tick (holds, deadlines, auto-accept, purge, webhooks) | every 2 s | |
| Contract loop | every 4 s | |
| Payout round (non-contract rows) | every 10 min | `HA_PAYOUT_INTERVAL_SECONDS` |

### Taking a task

A worker may take a task when: it is `open`, `claimed` or `submitted` with slots left; moderation allowed it; the deadline has not passed; the worker is qualified for the type, not paused, and has at least the task's minimum reputation (per type once they have 5 answers of that type); and, for a place-bound task, their location matches. Taking it writes a hold (one per task and worker). Live holds never exceed the workers wanted ("fully claimed"). A worker who already holds the task gets the same hold back.

Photo tasks hand out a 4-character capture code (letters and digits without the confusable ones) when taken. For a platform task, taking it is also the moment the money is reserved: the API moves the total from the pool to the task in the books (in contract mode it first checks that the contract and the operator wallet can cover it). If the pool is short the worker sees "This task cannot be funded right now. Please try another one."

### Deciding a task

#### Short tasks: consensus

Decided once every wanted slot has answered, or at the deadline with whatever answers are in.

| Rule | Types | Decision | Who agreed |
| --- | --- | --- | --- |
| majority | verify, choose, label | The answer with more than half the wanted votes (answers normalised: lower case, collapsed spaces, lists sorted) | Those who gave it |
| match | read | Two identical normalised texts (one if only one worker is wanted) | Those who match |
| median | rate | The median of at least two valid scores | Scores within 1 point of the median |
| single | answer | The one answer, agreement 1.0, after the verifier approves it when the verifier is on | |

At the deadline the wanted count becomes the number of answers actually in, so a lone answer is paid. If no decision is possible once all slots are used, or no answer arrived, the task expires and the whole amount is refunded: nobody is paid.

Every finished task carries a verification record: `{method, outcome, checks[{name, passed, detail}], decidedAt, by}`. Methods are "independent agreement (majority)" and so on, "client acceptance", or "none" for a cancelled task.

#### Action tasks and written answers: proof

A `do` task completes only when its proof is accepted. Acceptance comes from one of:

1. **The client**, through `POST /v1/tasks/{id}/accept` with the buyer token, or on `/client/tasks/[id]`.
2. **The verifier**, when it is on (see below), with a verdict of "right".
3. **Auto-accept**, one hour after the proof was submitted, if nobody acted.
4. **The operator**, by rejecting a dispute (the work stands).

A client can instead reject the proof with a reason of at least 10 characters, which opens a dispute. If the deadline passes with no proof at all, the task expires. When two workers were wanted, the verifier approves only if both proofs agree.

#### The verifier

When `HA_VERIFIER_ENABLED=true` and a gateway key is set, the verifier runs every tick (3 tasks at a time) on `do` and `answer` tasks that are `submitted` and not yet reviewed, after all wanted workers have answered or the deadline has passed.

- It uses the vision model (`HA_VERIFIER_VISION_MODEL`, Gemini) when a screenshot or photo is present, inlining the photos; otherwise the requester's own model, or the default (`HA_VERIFIER_DEFAULT_MODEL`, Claude).
- The response is treated as data. The model returns `{verdict: right | wrong | unsure, reason}`. For photo tasks it is told the capture code and must say "wrong" if the code is missing or the picture looks like a screen, a print or a generated image.
- A response that addresses the reviewer (prompt injection) skips the model and is marked "unsure".
- **Right** approves and pays at once. **Wrong** or **unsure** opens a dispute for a person. The verifier never refuses payment by itself. If the gateway fails, the task is left for the acceptance window or the deadline.

#### Disputes

| Who opens | When | What the operator sees |
| --- | --- | --- |
| The client rejects a proof | While the task is `submitted` | A proof-stage dispute |
| The verifier | Wrong or unsure | A proof-stage dispute (actor "verifier") |
| The client disputes a decided task | Within 24 hours of `done`, reason of at least 10 characters | A post-completion dispute |

The operator chooses **upheld** (the work was not acceptable) or **rejected** (the work stands), with an optional note.

- Proof stage, upheld: the worker's record takes a miss, the task expires and the whole amount is refunded.
- Proof stage, rejected: the proof is accepted, the task is done and the worker is paid.
- After completion, upheld: the client is refunded from the platform fee pool (capped by what the pool holds), the workers keep their pay but the agreeing ones take a miss on their record; the task returns to done.
- After completion, rejected: the task returns to done.

Decisions are final.

### Refunds

Where unearned money goes depends on who paid:

- A platform task that was only listed (nothing locked): nothing to refund.
- A platform task with money locked: back to the house pool.
- A client task: a refund row to the payer's address on the same rail, paid by the contract settlement (on the contract) or by the payout job.

Full refunds happen on rejection, expiry, cancellation and an upheld proof-stage dispute. Partial refunds happen for unfilled or disagreeing slots at settlement.

### Moderation

Every task is classified before it is routed. URLs are stripped first.

| Decision | Rules |
| --- | --- |
| **Reject** (refund, `rejected`) | credentials, captchas, account access, sexual content involving minors, violence; 64-hex strings near "key", "secret", "seed" or "wallet"; runs of seed-phrase-like words |
| **Review** (held in `paid` for the operator) | phone numbers (allowed for `calls` action tasks), emails, private individuals, sexual content, identity documents, hate, and for action tasks only: money actions and impersonation |
| **Allow** | everything else |

An optional external classifier (`HA_MODERATION_URL`) can escalate; if it is set but unreachable, an "allow" becomes "review". Platform tasks are never held for review: only a reject stops them. A client with two rejected tasks is blocked.

Workers can report a task with one tap. A report pulls an allowed, unfinished task into review, credits the reporter the task's price from the fee pool, and releases their hold.

### The chatbot gate

An optional check (`HA_GATE_ENABLED`) asks a small model whether a chatbot could do the task alone and refuses it if so. It applies to scout proposals and operator-posted team tasks, not to paid client tasks. Tasks whose text mentions a photo, a call or a visit pass without a call. Without a key, or if the call fails, the task passes.

### Retention

Thirty days after a task ends, its payload is replaced with `{"purged": true}`, free-text answers become `[purged]`, notes are cleared and photos are deleted from the store. The task page then shows "Removed after 30 days." Money records, events and the verification record stay.

### What a client sees of a task

`GET /v1/tasks/{id}` returns the task id, type, title, location, difficulty, effort, template id, reference, requester, state, workers wanted and answered, cost (per worker, fee, total), deadline, created and completed times, result and agreement once done, the proof and the accept-by time while a proof waits, the escrow state and transactions, the payment, the moderation status if held, the verification record, and the refund if any. The 202 response that created the task also carries the buyer token and, if a per-task webhook was given, its secret.


---

## 4. Workers

This is the earning side from the first visit to the money in the wallet. Everything a worker does happens on the website; the endpoints named here are what the pages call.

### 1. Connect a wallet

A worker signs in with a browser wallet (MetaMask or Phantom through Privy in production). There is no account, no email and no password. The wallet proves who they are by signing a message, and the same wallet is where the rewards go. The API creates the worker record on first sign-in with reputation 1.0, tier "new", no qualified types and no accepted terms. The session token lasts 30 days.

One person, one wallet. The rail (Robinhood Chain or Solana) is fixed by the wallet used to sign in; in production this is Robinhood Chain.

### 2. Accept the worker terms

Before the first qualification the site shows "How working here works" and the worker must tick "I have read this and I agree". The points:

1. You do the work yourself. One person, one account. Automated or shared accounts are removed and not paid.
2. You are paid when the work is accepted.
3. Nobody knows who you are. If a task asks for something it should not, report it with one tap and you are still paid.
4. Money goes to your wallet. Accepted work is paid in batches every ten minutes.
5. You work for yourself as an independent contractor and handle your own taxes.

The API records `termsAccepted` (`POST /v1/workers/profile` with `acceptTerms: true`). Qualification is refused until then (`terms_required`). The same call can set languages (up to 10) and a location (`City, ST` or Remote). Setting a city lets place-bound tasks in that city appear in the feed.

### 3. Qualify for each type of work

Every type has three practice questions with known answers (`GET /v1/workers/qualification/{type}`). The worker answers all three on cards that look exactly like real tasks and submits them together (`POST /v1/workers/qualification/{type}`). Two right unlocks paid tasks of that type; the result page shows which were right or missed, with an explanation. Practice is unpaid, costs nothing to miss, and can be repeated any time.

The `do` qualification is a three-question quiz about safe conduct rather than a sample action. `rate` allows one point of tolerance. The site shows "n of 7 unlocked".

A worker who has unlocked nothing sees "One step first: complete a qualification to see tasks. Start with Check."

### 4. Find a task

Tasks appear in two places: the public board at `/tasks` (anyone can look; taking one needs sign-in and the right qualification) and the worker's own list at `/earn/tasks` (`GET /v1/workers/tasks`, refreshed every 4 seconds). Fetching the list also counts as a heartbeat, which keeps the worker "online" for 10 minutes.

The list contains, newest highest-paid first and at most 30 cards:

- only types the worker is qualified for;
- only tasks that are open, claimed or submitted with slots left, allowed by moderation and not past their deadline;
- only tasks whose minimum reputation the worker meets (per type once they have five answers of that type);
- not tasks the worker already answered;
- place-bound tasks only when they match the worker's city (or the worker has set no location);
- optional filters by category, type, minimum price and location.

The task's content is hidden until it is held; the card shows a preview, the price, the number of workers and a countdown to the deadline. Every twentieth answer (`HA_GOLD_EVERY`) a gold check is slipped in at the top of the list; it looks like a normal task.

### 5. Take a task (hold a slot)

Clicking a card, or "Take this task" on the task page, calls `POST /v1/tasks/{id}/claim`. This reserves one of the task's slots and reveals the full content.

- Short tasks (check, choose, rate, label, read, answer) are held for 2 minutes. Action tasks are held for their whole time limit (30 to 90 minutes depending on the task). The hold never outlasts the task's deadline.
- The countdown on the card says "Yours to answer for".
- "Skip" (`POST /v1/tasks/{id}/release`) gives the slot back and the task returns to the feed.
- If every slot is already held the worker is told the task is fully claimed.
- Photo tasks return a four-character capture code with the hold.
- A platform task reserves its reward from the pool at this moment. If the pool cannot cover it, the worker sees "This task cannot be funded right now" and can try another.

While a task is held, its content is wrapped in the protection layer: no copy, no print, blurred when the tab is not in front, watermarked with the worker's wallet.

### 6. Answer

The card renders the task's content (image, text, item, question, instructions with an "Open the page" link, rubric) and the input for its type:

| Type | Input on the card |
| --- | --- |
| Check (`verify`) | Yes, No, Unsure |
| Choose | A numbered list of options; image options render as images |
| Rate | 1 to 5 |
| Label | Multi-select of the given labels |
| Read | A text box: "Type exactly what the image says" |
| Answer | A text box plus a confidence slider (default 0.8) |
| Action task (`do`) | Depends on the proof asked for: a note (at least 5 characters), a screenshot upload (shrunk in the browser to 1280 px JPEG), both, or photos (see below) |

An optional "One sentence why" note is available on the short types. Submit calls `POST /v1/tasks/{id}/answer` with `{answer, note, confidence}`. The API validates the shape per type, requires a live hold, refuses a second answer to the same task, and refuses a task that is closed or full.

What the worker is told after submitting:

- Short tasks whose decision is already known: "Accepted. $X added to your pending balance." or "Submitted. The other answers did not match yours this time."
- Short tasks still waiting for other answers: "Submitted. You are paid once the other answers are in and match."
- Action and written-answer tasks: "Proof submitted. The client has up to an hour to accept it; after that it is accepted automatically." (On the task page: "clear ones are approved within a minute, anything unclear is looked at by a person.")

Answers are saved with the time taken, and hidden from other workers until the task is decided, so that everyone answers on their own.

#### Photo proof

For a task with `proof: "photos"`:

1. The card shows the capture code: "Write this code on a piece of paper and keep it in every photo. It proves the photos were taken now, for this task."
2. The camera opens directly (a camera-only input). Pictures from the gallery, screenshots and photos of a screen are not accepted.
3. Up to 3 photos, each shrunk in the browser to 1600 px JPEG, are uploaded one by one with `POST /v1/tasks/{id}/photos` (the raw image in the body). The API accepts JPEG, PNG, WebP and HEIC up to 6 MB.
4. If the task is tied to an exact spot, the browser's location is sent with each photo and the API checks it is within 300 metres (`HA_GEO_RADIUS_M`) plus the reported accuracy, otherwise "wrong place". Without location access: "Allow location access in your browser and try again. The photo must be taken at the place."
5. The thumbnails show "sent · N m away". An optional one-line note can be added.
6. Submitting sends the photo ids as the answer; the capture code is stored with it.

Photos are visible only to the client and the operator (and the verifier), never to visitors, and are deleted within 90 days at most, usually with the task's purge at 30 days.

### 7. Report a task

While holding a task, "Report" with a short reason (`POST /v1/tasks/{id}/report`) pulls the task out of everyone's feed into the operator's review queue, releases the worker's hold, and credits the worker the task's price from the fee pool ("your time is credited"). One report per worker per task. Gold checks cannot be reported.

### 8. How a worker is paid

The worker is paid when their answer is accepted:

- Short tasks: when it agrees with the other answers (majority, match or median rule). A minority answer on a task with a clear majority is not paid, and nobody is paid when no agreement is reached (the task expires and is refunded).
- Action tasks and written answers: when the client or the verifier accepts the proof, or automatically an hour after submission.

On acceptance the reward is recorded for the worker (a `worker_due` posting and a payout row). How it reaches the wallet depends on who posted the task:

- **Platform tasks** (nearly everything on the board): the reward becomes **ready to claim**. The worker presses **Claim** on the earnings page or on the task page, and the task service sends the USDG from the platform's wallet to the worker's wallet right away (`POST /v1/tasks/{id}/claim-reward`), answering "$X sent to your wallet." with a transaction link. Claims across all workers are capped at $300 a day (`HA_WALLET_PAYOUT_DAILY_CAP`); past the cap, or while the wallet is being topped up, the reward stays claimable and the message says so. In contract mode the Claim button instead triggers the contract settlement that pays everyone accepted on that task.
- **Client tasks on the escrow contract**: the contract's settle transaction pays the worker's wallet directly, in USDG, as part of closing the task. The payouts table shows the transaction.
- **Other rows** (bonuses such as gold rewards and report credits, and anything on a rail without the contract): the payout job runs every 10 minutes and sends one transfer per worker wallet from the escrow wallet, skipping amounts under $0.10 and keeping each round under $2,000 per rail. Robinhood transfers count as sent after 2 confirmations; Solana sends up to 8 transfers per transaction and creates the recipient's token account if needed.

Rewards never leave the chain: every payout has a transaction anyone can look up, linked from the earnings page, the task page and the rewards page. Payments cannot be reversed.

### 9. Earnings page

`GET /v1/workers/earnings`, refreshed every 10 seconds: ready to claim (how much and how many rewards are waiting), today, this week, paid out all time, the payout wallet, the "Rewards ready to claim" panel with a Claim button per task, the payouts table (when, task, amount, status, transaction), and the worker's tier, accepted/answered, reputation and gold-check score.

#### Sending rewards on and gas help

USDG sits in the worker's wallet on Robinhood Chain. Sending it anywhere needs a little ETH for gas on that chain. The earnings page offers:

1. **Cover the gas** (`POST /v1/workers/gas`): the facilitator sends 0.00002 ETH to the worker's wallet. Available only to Robinhood workers who have received at least one payout, once per 24 hours, and only if the wallet does not already hold enough. The facilitator caps grants at 300 a day.
2. **Send USDG**: an ERC-20 transfer from the worker's wallet to an address they give, signed in their wallet, with a link to the transaction.

### 10. Reputation, tiers and checks

**Reputation** is one number from 0 to 1:

```text
reputation = min(1, (agreed + 2) / (answered + 2) × (0.5 + 0.5 × (goldCorrect + 1) / (goldTotal + 1)))
```

It rises with agreement and gold accuracy and is smoothed so a new worker starts near 1.0. A per-type reputation is used for feed gating once a type has five answers. Tasks can require a minimum (`answer` tasks need 0.9, action tasks 0.8).

**Tiers** are earned from answered count, reputation and gold accuracy:

| Tier | Answered | Reputation | Gold accuracy |
| --- | --- | --- | --- |
| gold | 300 | 0.95 | 0.95 |
| silver | 100 | 0.85 | 0.85 |
| bronze | 20 | 0.70 | |
| new | | | |

**Gold checks** are known-answer tasks seeded from the qualification samples (all types except `do`) and added by the operator. One is due every 20 real answers and is shown only if the fee pool can pay for it. A right answer pays the gold task's price from the fee pool as a bonus; a wrong one raises a `gold_wrong` flag.

**Dispute outcomes** also count: an upheld dispute marks the agreeing workers' records with a miss.

### 11. Pauses

Pauses are automatic; only a person lifts them.

| Flag | Raised when |
| --- | --- |
| `fast_answer` | Answered faster than plausible: verify 2 s, choose 2.5 s, rate 2 s, label 2.5 s, read 6 s, answer 10 s, do 30 s |
| `burst` | 10 or more answers within 60 seconds |
| `duplicate_text` | The same read or answer text (8+ characters) submitted twice or more within 24 hours |
| `gold_wrong` | A wrong gold answer |

Three non-gold flags in 24 hours (`HA_ABUSE_FLAGS_PAUSE`), or three wrong gold answers in 24 hours (`HA_GOLD_WRONG_PAUSE`), pause the worker. A paused worker gets "Your account is paused" with the reason on every page; pending earnings are kept. The operator can pause or unpause through the admin API.

### 12. What workers see of each other

Nothing that identifies anyone. After a task is decided, the task page lists every response under an anonymous label ("Worker ab12", derived from a hash), the tier, the time taken, the outcome and the reward. Photos and locations are never shown to visitors. Workers never see who asked for a task, only which assistant it is for.


---

## 5. Clients and the API

Clients are software. A client posts a task, is told the exact price, pays with its wallet, and gets the answer by polling or by a signed webhook. There is no account: the wallet that pays is the client, and a per-task buyer token is the authority over that task.

Base URL in production: `https://humanapi-api.onrender.com`. Interactive OpenAPI docs are served at `/docs`. All amounts are millionths of a dollar. Errors have the shape `{"error": "<code>", "message": "<text>"}`.

### Posting and paying for a task (x402)

#### Step 1: post without payment, get a 402

```http
POST /v1/tasks
Content-Type: application/json

{
  "type": "do",
  "title": "Call the Walgreens on Market St and ask about pharmacy hours",
  "location": "San Francisco, CA",
  "acceptance": "Who answered, what they said, the time of the call",
  "payload": {
    "category": "calls",
    "instructions": "Call (415) 362-6363 during store hours. Ask until what time the pharmacy counter is open today. Write who answered, what they said and the time you called.",
    "proof": "text"
  },
  "pricePerWorker": 1500000,
  "timeLimitSeconds": 3600,
  "webhook": { "url": "https://your-server.example/humanapi" },
  "reference": "order-8841"
}
```

The response is `402 Payment Required` with the price and one x402 payment requirement per enabled rail:

```http
HTTP/1.1 402 Payment Required
PAYMENT-REQUIRED: <base64 of the x402 PaymentRequired object>
Cache-Control: no-store

{
  "error": "payment_required",
  "message": "...",
  "quote": { "id": "qt_...", "total": 1800000, "workerPool": 1500000, "fee": 300000, "expiresAt": 1791540000 },
  "x402": {
    "x402Version": 2,
    "resource": { "url": "...", "description": "H402 task: ...", "mimeType": "application/json" },
    "accepts": [
      { "scheme": "exact", "network": "eip155:4663", "asset": "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168",
        "amount": "1800000", "payTo": "0x530C2beDB048a658cB9fFD074eB7A75D68bfBd90",
        "maxTimeoutSeconds": 300, "extra": { "assetTransferMethod": "permit2" } }
    ]
  }
}
```

The quote is valid for 5 minutes. Posting the same body again within that window returns the same quote.

#### Step 2: pay and repeat

Sign the payment with the wallet and repeat the identical request with the signature in the `PAYMENT-SIGNATURE` header (`X-PAYMENT` is also accepted). The x402 client libraries do the whole round trip in one call:

```python
# pip install "x402[evm]"
from x402 import x402Client
from x402.http.clients import wrapHttpxWithPayment
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import register_exact_evm_client
from eth_account import Account

client = x402Client()
client.set_spend_controls(False)
register_exact_evm_client(client, EthAccountSigner(Account.from_key(PRIVATE_KEY)), networks="eip155:4663")
async with wrapHttpxWithPayment(client) as http:
    r = await http.post("https://humanapi-api.onrender.com/v1/tasks", json=task)   # the 402 is handled for you
    task_id = r.json()["taskId"]
    buyer_token = r.json()["buyerToken"]
```

On Robinhood Chain the payment is a Permit2 authorisation for USDG: the wallet needs a one-time `approve` of the Permit2 contract (`0x000000000022D473030F116dDEE9F6B43aC78BA3`) and then signs an EIP-712 `PermitWitnessTransferFrom` for each payment, with the x402 proxy `0x402085c248EeA27D92E8b30b2C58ed07f9E20001` as spender. The signature costs no gas; the facilitator submits it and pays the gas.

What the API does with the payment:

1. Decodes the header and checks that `payload.accepted` matches one of the offered requirements on scheme, network, asset, amount and payTo.
2. Asks the facilitator to verify, then to settle. A settle failure returns 402 with the reason and a `PAYMENT-RESPONSE` header.
3. If the same settlement (network and transaction) was already recorded, returns the existing task with 200 instead of creating a second one.
4. Records the payment, finds or creates the buyer by payer address, creates the task, consumes the quote.
5. Answers `202 Accepted` with the task view, the `buyerToken`, the per-task `webhookSecret` (if a webhook URL was given), and the `PAYMENT-RESPONSE` header carrying the settlement.

```json
{
  "taskId": "task_...", "state": "open", "type": "do", "title": "...",
  "workers": { "wanted": 1, "answered": 0 },
  "cost": { "pricePerWorker": 1500000, "fee": 300000, "total": 1800000 },
  "deadline": 1791543600, "resultUrl": ".../v1/tasks/task_...", "receiptUrl": ".../v1/receipts/task_...",
  "payment": { "network": "eip155:4663", "transaction": "0x...", "explorer": "https://robinhoodchain.blockscout.com/tx/0x..." },
  "buyerToken": "bt_...", "webhookSecret": "whsec_..."
}
```

Keep the buyer token. It alone lets the software accept, dispute or cancel that task.

#### Idempotency

Send an `Idempotency-Key` header (up to 120 characters). A repeat with the same key and body replays the stored status, body and payment headers for 24 hours. The same key with a different body is refused with `422 idempotency_key_reused`.

#### Batches

`POST /v1/tasks/batch` with `{"tasks": [ ... ]}` (1 to 100 tasks) prices and pays the whole batch with one payment. The 202 returns `{batchId, tasks[], payment, cost{total}}`; `GET /v1/batches/{id}` reads it back.

### Task request fields

| Field | Required | Rules |
| --- | --- | --- |
| `type` | yes | `do`, `verify`, `choose`, `rate`, `read`, `label`, `answer` |
| `payload` | yes | Per type, see [3. How tasks work](#3-how-tasks-work); at most 64,000 bytes; must include `category` |
| `title` | no | Up to 140 characters |
| `location` | no | `Remote` or `City, ST` in the United States |
| `acceptance` | no | Up to 2000 characters, shown to the worker |
| `difficulty` | no | easy, medium, hard |
| `effortMinutes` | no | 1 to 240 |
| `templateId` | no | Up to 20 characters |
| `requester` | no | claude, chatgpt, gemini, grok, deepseek |
| `workers` | no | In the type's allowed set |
| `pricePerWorker` | no | From 1,500,000 ($1.50) to 50,000,000 ($50); defaults to the minimum |
| `minReputation` | no | 0 to 1 |
| `timeLimitSeconds` | no | 30 to 10,800 |
| `listSeconds` | no | 60 to 604,800 |
| `webhook.url` | no | https (http allowed outside mainnet) |
| `reference` | no | Up to 120 characters |

Anything naming India is refused. Tasks asking for passwords, codes, keys, captchas, account access or violence are refused and refunded; tasks that ask a person to pay, buy or act as someone else, or that contain phone numbers (outside `calls`), emails, private individuals or identity documents, are held for the operator first.

### Reading the result

```http
GET /v1/tasks/{taskId}

{ "state": "done",
  "result": { "answer": "yes", "votes": 3, "of": 3 }, "agreement": 1.0,
  "verification": { "method": "independent agreement (majority)", "outcome": "approved", "checks": [ ... ] } }
```

`result` and `agreement` appear only when the state is `done`. For action tasks the state `submitted` carries the proof and the accept-by time:

```json
{ "state": "submitted",
  "proof": { "value": { "text": "...", "screenshot": "..." }, "note": "...", "submittedAt": 1791541000 },
  "acceptBy": 1791544600 }
```

When the proof has a photo or screenshot in it there is no `acceptBy`; the view carries `"awaitingOperator": true` instead, and the task stays `submitted` until the operator approves or refuses it (the client may still accept or dispute it themselves).

Other fields: `escrow {state, openTransaction, closeTransaction}` when the task is on the contract, `moderation {status, reason}` while held, `refund` when expired or cancelled, and `teamRun` on the team's own tests.

### Acting on a task

All four take the buyer token in the body. A client session (see below) may be used instead for tasks that wallet paid for.

| Call | Body | When allowed | Result |
| --- | --- | --- | --- |
| `POST /v1/tasks/{id}/accept` | `{"buyerToken": "..."}` | A `do` task in `submitted` | The worker is paid; `done`. Otherwise `409 not_acceptable` |
| `POST /v1/tasks/{id}/accept` | `{"buyerToken": "...", "reject": true, "reason": "..."}` (reason of at least 10 characters) | A `do` task in `submitted` | A dispute is opened; `disputed`. Returns `{disputeId, taskId, status: "open"}` |
| `POST /v1/tasks/{id}/dispute` | `{"buyerToken": "...", "reason": "..."}` | A task in `done`, within 24 hours of completion | `disputed`. Errors `409 not_disputable`, `409 window_closed` |
| `POST /v1/tasks/{id}/cancel` | `{"buyerToken": "...", "reason": "..."}` | `paid`, `open` or `claimed`, and no answer yet | Full refund; `cancelled`. Otherwise `409 not_cancellable` |

If the software does nothing with a submitted proof, it is accepted automatically one hour after submission.

### Webhooks

Give `webhook.url` in the task body and the API posts every terminal state change there. The 202 response carries the `whsec_` secret for that task.

```http
POST https://your-server.example/humanapi
Content-Type: application/json
X-H402-Event: task.done
X-H402-Timestamp: 1791540000
X-H402-Signature: hex( HMAC-SHA256( secret, timestamp + "." + raw_body ) )
X-H402-Delivery: whd_...

{ "event": "task.done", "taskId": "task_...", "data": { ...same as GET /v1/tasks/{id}... }, "sentAt": 1791540000 }
```

- Events: `task.done`, `task.expired`, `task.rejected`, `task.cancelled`. There are no events for open, claimed, submitted or disputed; poll for those.
- Verify the signature with the secret and a timestamp tolerance of 300 seconds.
- Deliveries are retried with backoff (5 s doubling, capped at an hour) up to 8 times until the receiver answers 2xx.

**Buyer-level webhooks.** `POST /v1/webhooks` with `{url, payer, network}` registers a default hook for every task that payer posts and returns `{id, url, secret: "whbs_...", note}`. It replaces that payer's earlier hooks. Because it is registered without payment proof, its deliveries carry the state only: `result` and `agreement` are stripped. Per-task hooks carry the result.

### Receipts

`GET /v1/receipts/{taskId}` is public: the payment (network, transaction, payer, amount, explorer link), the consensus (result, agreement, answers, agreed), the verification record, every payout `{worker, amount, status, ref}`, every refund `{amount, reason, status, transaction}`, the ledger postings and the timeline of state changes. The client's task page links to it as "Public receipt".

### Pricing and the catalogue

- `GET /v1/pricing`: the fee in basis points, the currency, each type's base price (raised to the minimum reward), default and allowed worker counts, time limit, consensus rule, minimum reputation and an example total; the minimum reward; the rails with `{network, asset, payTo}`; and live availability (workers online, by type).
- `GET /v1/catalogue`: the 15 categories with label, need and examples.
- `GET /v1/catalogue/templates?category=`: the 100 ready-made templates, United States only, marked `status: "template"`.

### Client wallet sessions (the `/client` pages)

The website lets a client follow its software's tasks by signing in with the wallet that paid:

| Call | Notes |
| --- | --- |
| `POST /v1/clients/nonce` `{wallet, network}` | Returns `{nonce, message, wallet, network, expiresAt}` |
| `POST /v1/clients/session` `{wallet, network, nonce, signature}` | Returns `{token: "cls_...", expiresAt, client}`. Errors `401 bad_nonce`, `401 bad_signature`, `400 unsupported_network`, `400 invalid_wallet` |
| `GET /v1/clients/me` | `{id, rail, wallet, name, tasksPaid, blocked, createdAt}` |
| `POST /v1/clients/profile` `{name}` | |
| `GET /v1/clients/tasks?state=&limit=50` | The wallet's tasks (each with its buyer token), counts per state, spent, refunds due |
| `GET /v1/clients/tasks/{id}` | The task with buyer token, payload, acceptance and receipt |
| `GET /v1/photos/{photoId}` | A proof photo; allowed with the client session, the buyer token (`?token=`), the worker who took it, or the admin token |

With `Authorization: Bearer cls_...`, the accept, dispute and cancel calls work without the buyer token for tasks that wallet paid for.

### Public read endpoints

| Call | Returns |
| --- | --- |
| `GET /` | Service name, version, links to `/docs` and `/v1/pricing` |
| `GET /v1/tasks/open?limit=60&category=` | The board: open, claimed and submitted tasks with slots, price, place, requester (up to 200); cached 10 s |
| `GET /v1/tasks/open/{id}` | One listing with payload, acceptance, requirements and whether it is open |
| `GET /v1/tasks/map` | Open tasks with coordinates, plus the count of remote ones |
| `GET /v1/tasks/{id}/comments` | The saved responses; only your own until the task is decided |
| `GET /v1/stats` | Open count and value, lowest and highest price, paid in 24 h and total, done counts, team-run totals, workers online and total, catalogue size, fee |
| `GET /v1/rewards` | Rewards paid (to workers and in team runs), payments, people paid, task counts, open rewards, pool available, fees earned, the contract's balance and locked amount, the 25 latest payments |
| `GET /v1/activity?limit=30` | Recent decided tasks with method, agreement, settlement transaction |
| `GET /v1/scouts` | The scouts' status and the last 60 proposals |
| `GET /health` | Ledger balance per rail against the chain, task counts per state, facilitator reachability; 503 if anything fails |

### Error codes you will meet

| Status | Code | Meaning |
| --- | --- | --- |
| 400 | `invalid_request` | Body did not validate (the message says what) |
| 402 | `payment_required` | No payment, a mismatched payment, a rejected verification or a failed settlement |
| 403 | `forbidden` | Wrong buyer token or not the owning wallet |
| 409 | `not_acceptable`, `not_rejectable`, `not_disputable`, `window_closed`, `not_cancellable` | The task is not in a state that allows the action |
| 422 | `idempotency_key_reused` | Same key, different body |
| 404 | `not_found` | Unknown task, or an admin route when admin is off |

### Rules for clients

- Never include passwords, codes, keys or payment details. Such tasks are refused and refunded.
- Tasks that ask a person to buy, pay, or act as someone else are held for review first.
- Nothing about private individuals. Businesses, places and public listings only.
- Money is held before anyone starts and released when the work is accepted. Unfilled slots are refunded.
- Tasks and responses posted through the API become part of H402's training data (see [10. Policies](#10-policies-and-known-gaps)).


---

## 6. Payments and escrow

Money enters as an x402 payment from a client or as USDG in the platform's wallet, and leaves as a reward to a worker, a fee to the treasury or a refund. Client payments are held by the TaskEscrow contract while the task runs. Platform rewards are reserved from the pool when a task is taken and sent from the platform's wallet when the worker claims them (or, in contract mode, locked and settled on the contract). This document covers the rails, the facilitator that settles payments, the contract, the two ways platform tasks pay, the way the task service drives the contract, the books, and the payout job.

### Rails

| Rail | Network id | Token | Status today |
| --- | --- | --- | --- |
| Robinhood Chain mainnet | `eip155:4663` | USDG `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168`, 6 decimals | Live: sign-in, x402 payments, the escrow contract, payouts, gas help |
| Robinhood Chain testnet | `eip155:46630` | any token unless configured | Development |
| Solana mainnet | `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` | USDC `EPjFWdd5AufqSSqeM4qv9bL4dqAfv7PF9Vm7GdWRLd3f` | Built in the facilitator, sign-in and payout code; no contract, no browser payment, no gas help; disabled in production |
| Solana devnet | `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` | test USDC `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU` | Development |

Explorers: `https://robinhoodchain.blockscout.com/tx/{tx}` (mainnet; the facilitator's own links still point at `https://robinhoodchain.blockscout.com`), `https://testnet.robinhoodchain.blockscout.com/tx/{tx}`, `https://solscan.io/tx/{tx}`.

USDG does not support EIP-3009, so x402 payments on Robinhood Chain go through the **Permit2 route**: the payer approves Permit2 (`0x000000000022D473030F116dDEE9F6B43aC78BA3`) once, then signs a `PermitWitnessTransferFrom` per payment naming the x402 Permit2 proxy (`0x402085c248EeA27D92E8b30b2C58ed07f9E20001`) as spender and the pay-to address as witness. On Solana a payment is a partially signed SPL transfer with the facilitator as fee payer.

### The facilitator

The facilitator (`facilitators/`, port 8402) is the only process that holds a settlement key. It wraps the official `x402` Python SDK 2.25.0 and adds policy, a durable replay store, confirmation depth, crash recovery, bearer auth, a rate limit and a gas-help endpoint.

#### Endpoints

| Call | Auth | What it does |
| --- | --- | --- |
| `GET /` | none | Service name, version, endpoint list |
| `GET /supported` | none | The SDK's supported kinds per rail; on Solana the `extra` carries the fee payer, which the task service copies into its 402 requirements |
| `POST /verify` | none, rate limited per IP | Body `{x402Version: 2, paymentPayload, paymentRequirements}`. Policy checks first (`unsupported_scheme`, `network_mismatch`, `invalid_amount`, `amount_exceeds_facilitator_cap`, `asset_not_allowed`, `daily_settlement_cap_reached`), then the SDK. Returns `{isValid, invalidReason?, invalidMessage?, payer?}` |
| `POST /settle` | `Authorization: Bearer HF_SETTLE_TOKEN`, rate limited | Same body. Submits the transfer on chain. Success `{success: true, transaction, network, payer, explorer}`; failure `{success: false, errorReason, errorMessage?, ...}`; `settlement_pending` means retry later with the same payload |
| `POST /gas` | same bearer | `{address}`: sends a small amount of ETH to a worker's wallet on Robinhood Chain (see gas help below) |
| `GET /health` | none | 200 when every rail and the database answer, else 503: per rail the signer, head block, native balance, low-gas flag, caps; settlement counts by status |

Only `scheme: "exact"` and `x402Version: 2` are accepted. Errors are `{"error": reason, "message": text}`.

#### Settlement, replay protection and recovery

Every payment authorisation gets one key: `sha256(network | kind | payer | nonce)`, where the nonce is the Permit2 nonce (or the transaction message hash on Solana). The `settlements` table claims that key atomically (`INSERT OR IGNORE`), so one authorisation settles exactly once:

- `settled`: the stored response is returned again (a safe replay);
- `sending` or `uncertain`: "settlement pending", retry later;
- `failed`: retried.

On Robinhood the facilitator waits for 3 confirmations (`HF_ROBINHOOD_CONFIRMATIONS`); a timeout marks the row uncertain. On Solana the expected signature is computed and stored before sending. A recovery pass runs at start and every 60 seconds: each unresolved row is checked against the chain by receipt, then on Robinhood by the Permit2 `nonceBitmap` (a used nonce means it settled); a row that cannot have landed (past its deadline plus a minute on Robinhood, or 150 seconds old on Solana) is marked `never_landed`.

Every verify and settle writes an audit event (rail, network, payer, amount, outcome, latency, key). Payloads, signatures and keys are never logged.

#### Policy and caps

| Setting | Default | Meaning |
| --- | --- | --- |
| `HF_ROBINHOOD_MAX_AMOUNT`, `HF_SOLANA_MAX_AMOUNT` | 1,000 USDG / USDC | Largest single settlement |
| `HF_DAILY_SETTLEMENT_CAP` | 5,000 | Settlements per day |
| `HF_RATE_LIMIT_PER_MINUTE` | 120 | Per client IP |
| `HF_ROBINHOOD_ASSETS`, `HF_SOLANA_ASSETS` | USDG on 4663, USDC on Solana | Allowed tokens; mainnet refuses a rail with none |
| `HF_ROBINHOOD_MIN_GAS_WEI` | 0.01 ETH | Low-gas warning on `/health` |

Mainnet (`HF_ENV=mainnet`) requires the Robinhood network to be 4663, Solana to be mainnet, and a settle token. The task service's `HA_FACILITATOR_SETTLE_TOKEN` must equal the facilitator's `HF_SETTLE_TOKEN`.

#### Gas help

`POST /gas {address}` sends `HF_GAS_GRANT_WEI` (0.00002 ETH) to the address on Robinhood Chain, with these limits: not if the wallet already holds that much (`granted: false`), at most 300 grants a day (`HF_GAS_GRANTS_PER_DAY`, 429 `daily_cap`), once per wallet per 24 hours (429 `already_granted`), and not if the signer's own balance is below 20 grants (503 `low_gas`). The task service calls it only for Robinhood workers who have received at least one payout, once a day each.

The facilitator signer on mainnet is `0x60F02A52451ce6dDCA7C32A1390eabFEc0BB7b9E`; it holds ETH for gas only. `facilitators/scripts/withdraw.py` previews (and with `--send` performs) a withdrawal of its ETH to the owner wallet.

### The TaskEscrow contract

`contracts/src/TaskEscrow.sol`, Solidity 0.8.26, deployed on Robinhood Chain mainnet on 2026-10-09 at `0x530C2beDB048a658cB9fFD074eB7A75D68bfBd90` (block 84343746). Token USDG. Owner, operator and treasury are all `0xAd576D84708597616510186DAAc39D4aEF559a14` for now. Limits in force since 2026-10-11 (transaction `0x281170ce…`): 300 USDG paid out per day and 60 USDG per task (they were 2,000 and 200 at deployment); the fee on a task may never exceed 30% of what it holds (`MAX_FEE_BPS`). A task whose total exceeds the per-task limit cannot be opened on the contract. The contract is not audited. Its source was verified on Blockscout on 2026-10-11: https://robinhoodchain.blockscout.com/address/0x530C2beDB048a658cB9fFD074eB7A75D68bfBd90?tab=contract (solc 0.8.26, optimizer 200, EVM paris, MIT).

#### How it holds money

The contract keeps one record per task: `tasks[taskId] = {payer, amount, openedAt, status}` with status `None`, `Open`, `Settled` or `Refunded`. The task id is `keccak256` of the task's string id. Two counters, `allocated` (money promised to open tasks) and `feesAccrued` (fees waiting to be withdrawn), are always covered by the contract's token balance; anything above them is `unallocated()` surplus.

Money reaches the contract by a plain token transfer: an x402 settlement whose pay-to address is the contract, or the operator wallet funding the pool. Then the operator **opens** a task against that balance.

#### Functions

| Function | Who | What it does |
| --- | --- | --- |
| `open(taskId, payer, amount)` | operator, not paused | Records the task and adds its amount to `allocated`. Reverts if the task exists, the amount is 0 or over `maxTaskAmount`, or the balance does not cover `allocated + feesAccrued + amount` (`NotFunded`) |
| `settle(taskId, workers[], amounts[], fee)` | operator, not paused | Pays each worker, adds the fee to `feesAccrued`, returns the remainder to the payer, marks Settled. At most 20 workers; `fee ≤ 30%` of the held amount; `sum + fee ≤ held`; the daily limit applies to the worker payments |
| `refund(taskId)` | operator any time; the payer after 7 days | Returns the full amount to the payer, marks Refunded. Works while paused |
| `withdrawFees()` | anyone | Sends `feesAccrued` to the treasury |
| `sweepSurplus()` | owner | Sends the unallocated surplus to the treasury |
| `setOperator`, `setTreasury`, `setLimits(dailyLimit, maxTaskAmount)` | owner | |
| `setPaused(bool)` | owner or operator may pause; only the owner unpauses | |
| `transferOwnership(next)` then `acceptOwnership()` | owner, then the pending owner | Two-step ownership |

Events: `TaskOpened`, `WorkerPaid`, `TaskSettled(taskId, paidToWorkers, fee, refunded)`, `TaskRefunded`, `FeesWithdrawn`, `SurplusSwept`, `OperatorChanged`, `TreasuryChanged`, `LimitsChanged`, `Paused`, `OwnershipTransferStarted`, `OwnershipTransferred`. A reentrancy lock guards settle, refund and the withdrawals.

Compile with `python script/build.py` (solc 0.8.26, 200 optimizer runs, EVM paris) and deploy with `python script/deploy.py --send` using `DEPLOYER_PRIVATE_KEY` from `contracts/.env`. Six tests run with `pytest` from `contracts/` on an in-process EVM.

### How platform tasks pay: wallet mode and contract mode

`HA_HOUSE_PAYOUT` chooses how the platform's own tasks pay. Client tasks paid over x402 are not affected: they always go through the contract. The code's default is `wallet`; `contracts/README.md` describes contract mode as the flow in force since 2026-10-11, so the value of `HA_HOUSE_PAYOUT` on the Render task service decides which one production runs. Either way the worker sees the same thing: an accepted reward waits for their Claim and is paid on chain when they press it.

**Wallet mode (`wallet`, the code default).** The operator wallet is the reward wallet. Production has run in contract mode since 2026-10-11.

1. A platform task is listed with nothing behind it (`chain_state = listed`).
2. When a worker takes it, the total (reward plus fee) moves in the books from the pool to the task and the task becomes `funded`. No chain call is made. If the pool's books cannot cover it, the take is refused.
3. When the task is decided, each accepted worker's payout row is marked `claimable` instead of queued.
4. The worker presses Claim (`POST /v1/tasks/{id}/claim-reward`). The task service sends an ERC-20 transfer of USDG from the operator wallet (signed with `HA_ESCROW_OPERATOR_PRIVATE_KEY`) to the worker's wallet, marks the payout `sent` with the transaction, posts `worker_due → escrow`, and returns `{taskId, amount, transaction, explorer}`.
5. The pool's books follow the operator wallet's USDG balance: the pool sync described below books any increase as a deposit, so topping up the wallet is all it takes to fund more tasks. Unearned money returns to the pool in the books.

Limits and refusals on a claim:

| Code | Status | When |
| --- | --- | --- |
| `nothing_to_claim` | 404 | No claimable reward for this worker on this task |
| `payouts_off` | 503 | No reward sender is configured (needs the operator key and the Robinhood rail) |
| `daily_cap` | 429 | Rewards sent from the wallet in the last 24 hours plus this one would exceed `HA_WALLET_PAYOUT_DAILY_CAP` ($300). The reward stays claimable until tomorrow |
| `wallet_low` | 503 | The wallet holds less than the reward; it stays claimable |
| `send_failed` | 503 | The transfer could not be broadcast; it stays claimable |

**Contract mode (`contract`).** The TaskEscrow contract holds and pays platform rewards too. A platform task is listed, then on take the service checks that the contract's surplus plus the operator wallet's USDG covers the total (`not_funded` or `try_again` otherwise), moves the money in the books and marks the task `pending`. The contract loop opens it on chain. When it is decided, the rewards are `claimable`; the first worker's Claim turns them into queued rows and settles the task on the contract at once (`settle_one`: open if needed, funding the contract from the operator wallet for a platform task, then settle), paying everyone accepted on that task in one transaction. The loop leaves finished tasks that still have claimable rewards alone until someone claims.

### How the task service drives the contract

With `HA_ESCROW_CONTRACT` set, the task service (`escrow_chain.py`) signs every contract transaction with the **operator wallet** (`HA_ESCROW_OPERATOR_PRIVATE_KEY`). The x402 pay-to address (`HA_ROBINHOOD_ESCROW_ADDRESS`) must be the contract itself, so client payments land in the contract directly.

Each task carries a `chain_state`:

| chain_state | Meaning |
| --- | --- |
| none | Not on the contract (Solana, or before the contract was wired) |
| `listed` | A platform task on the board with nothing reserved yet |
| `funded` | A platform task in wallet mode whose reward is reserved in the books; paid from the wallet on claim |
| `pending` | Money is booked and the task must be opened on chain |
| `open` | Opened on chain |
| `closed` | Settled or refunded on chain |

**The contract loop** runs on its own thread every 4 seconds when a contract is configured (also on demand from `/operator`, "Run settlement now"):

1. **Pool sync** (at most once a minute): the money behind the pool is the operator wallet's USDG balance in wallet mode, or the contract's surplus plus the wallet's balance in contract mode. If it exceeds the pool's books by $1 or more, the difference is booked as a deposit. A shortfall is only logged.
2. Platform tasks that ended untaken drop their `listed` state.
3. For up to 5 tasks that are `pending`, or `open` and finished and not waiting for a worker's claim, the on-chain status is read **before** acting, so a crash or a second run never opens or pays a task twice:
   - On chain `None`: call `open(taskId, payer, amount)`. The payer is the client's address, or for platform tasks `HA_ESCROW_HOUSE_PAYER` (default: the operator wallet). If the contract's surplus is short, a platform task is topped up with a transfer from the operator wallet; a client task waits for its payment to arrive.
   - On chain `Open` and the task is finished locally: call `settle(workers, amounts, fee)` from the ledger's `worker_due` and `platform_fee` postings, or `refund()` when nobody is paid and no fee is due. Blocked if a worker has no `0x` wallet.
   - Already closed: record the alignment.
4. Closing marks the task's queued payouts and refunds as `sent` with the transaction id and posts them against escrow.

The payout job skips rows for tasks that are on the contract, so nothing is paid twice.

#### Why exactly one copy of the task service may run

All of the service's chain transactions, including the reward transfers sent on a claim, are signed by one operator key with the nonce taken from the pending count; the locks around the contract loop, the verifier and the scouts are in-process; payout rows move from queued or claimable to sent without a cross-process lock; and the house, scout and payout schedulers run inside every process. Two copies would race on nonces and could post a house batch or send a payout twice. The contract itself refuses to open or pay a task twice, which bounds the damage, but the rule stands: one copy, anywhere. The local Docker containers stay stopped while Render runs.

### The books: the ledger

The task service keeps a double-entry ledger per rail. The invariant, checked on `/health`, is that the money held (`escrow`) equals the money owed (every liability).

Accounts: `escrow` (what is held), `payer:<address>` (a client), `payer:house` (the platform as a payer), `house` (the pool), `task:<id>`, `worker_due:<worker>`, `platform_fee`, `refund_due:<address>`.

| Event | Debit → Credit |
| --- | --- |
| x402 settlement | `escrow → payer:<addr>` |
| Task created | `payer:<addr> → task:<id>` (the total) |
| Pool deposit | `escrow → house` |
| Platform task funded (on claim, or at posting without the contract) | `house → payer:house → task:<id>` |
| Task decided | `task:<id> → worker_due:<worker>` per agreeing worker; `task:<id> → platform_fee`; the rest `task:<id> → refund_due:<addr>` (or back to `house`) |
| Payout sent (by the contract, by the payout job, or by a claim from the wallet) | `worker_due → escrow` |
| Refund sent | `refund_due → escrow` |
| Gold reward, report credit | `platform_fee → worker_due` |
| Dispute upheld after completion | `platform_fee → refund_due` |
| Fees moved into the pool | `platform_fee → house` |

Goodwill (gold pay, report credits, upheld-dispute refunds) is always paid from `platform_fee`, never from money held for other tasks; when the fee pool is empty, no gold is shown and refunds are capped.

### The payout job

For queued rows not covered by the contract or by a claim (bonuses, and task rewards on a rail without the contract), `payouts.py` runs every 10 minutes when `HA_PAYOUTS_ENABLED=true` and the rail's escrow key is set (its address must equal the rail's escrow address):

1. Group queued payouts per rail by worker wallet into one transfer each; skip totals under $0.10 (`HA_PAYOUT_MIN_AMOUNT`) and stop at $2,000 per round per rail (`HA_PAYOUT_ROUND_CAP`).
2. Queued refunds go to payer addresses within the remaining budget.
3. Robinhood: one ERC-20 transfer per transaction, sent after 2 confirmations. Solana: up to 8 `transfer_checked` instructions per transaction, creating the recipient's token account if missing.
4. Rows go `queued → sending` (recorded before broadcast) `→ sent`; a failure requeues up to 5 attempts, then `failed`. On start, `sending` rows are resolved from the chain.

### The platform's pool

The pool is the ledger account `house`. It is funded three ways: USDG sent to the operator wallet is picked up by the pool sync within a minute (the usual way); an operator records an on-chain top-up by hand (`POST /v1/admin/house/deposit`, transaction required outside local); or fees are moved into it (`POST /v1/admin/house/from-fees`). Unearned money from platform tasks returns to the pool. In wallet mode the same wallet is what rewards are paid from when workers claim, so its balance is the pool. The operator page shows the pool's balance, open tasks and today's spend against the daily budget.

### Limits in force

| Limit | Value | Where |
| --- | --- | --- |
| Reward per worker | $1.50 to $50 | task service |
| Contract: per task | 60 USDG (200 at deployment) | contract `maxTaskAmount` |
| Contract: paid per day | 300 USDG (2,000 at deployment) | contract `dailyLimit` |
| Contract: fee | at most 30% of the task | contract `MAX_FEE_BPS` |
| Facilitator: per settlement | 1,000 USDG | `HF_ROBINHOOD_MAX_AMOUNT` |
| Facilitator: settlements per day | 5,000 | `HF_DAILY_SETTLEMENT_CAP` |
| House pool: open tasks, daily budget | 240, $2,000 | `HA_HOUSE_MAX_OPEN`, `HA_HOUSE_DAILY_BUDGET` |
| Rewards claimed from the wallet per day (wallet mode) | $300 | `HA_WALLET_PAYOUT_DAILY_CAP` |
| Paid out by the contract per day (contract mode) | $300 | contract `dailyLimit`, set by the owner |
| Locked per task by the contract | $60 | contract `maxTaskAmount`, set by the owner |
| Payout round | $2,000 per rail | `HA_PAYOUT_ROUND_CAP` |

### Known limits of the money layer

- The contract is unaudited (its source is verified on Blockscout), and owner, operator and treasury share one wallet whose key has been shared in chat; the plan is to move owner and treasury to a never-shared key and audit before larger amounts.
- Fees withdrawn from the contract are reconciled with the ledger by hand.
- Solana has no escrow contract; its rewards would be paid by the payout job from the escrow wallet.
- The site's Permit2 browser-payment code exists but no page uses it; clients pay from software.


---

## 7. Operator

The operator is the person who makes the decisions the system leaves to a human and keeps the pool and the contract in order. The tools are the `/operator` page, the operator box on `/scouts`, the admin API behind `HA_ADMIN_TOKEN`, and a few scripts.

### The operator key

`HA_ADMIN_TOKEN` on the task service. The site stores it in the browser as `humanapi.operator.key` and sends it as `Authorization: Bearer` on every `/v1/admin/*` call. When the token is unset on the service, every admin route answers 404; a wrong token answers 401 and the page says "That key is not accepted." The same key reads any proof photo (`GET /v1/photos/{id}`).

### The operator page (`/operator`)

"Decisions that need a person." Refreshes every 30 seconds. Each tab shows a count. The page is not linked from the site and carries a no-index tag; nothing on it loads without the operator key.

#### Responses

Everything people sent back, newest first, with the photos: the only place on the site where one person's photos and answers are visible to anyone but the client. Filters: "Waiting for you" (proofs with pictures, written proofs still inside their window, written answers awaiting review, and disputed responses), "Approved", "Refused", "Everything". Each card shows the task (linked), type, category, price, who sent it (wallet prefix), how long they took, the assistant's verdict if it reviewed the response, what was asked (folded), the typed text, the note, the capture code to look for in every photo, the photos themselves (fetched with the key in a header, never in a link; each with its distance from the place when the task had one), and any screenshot.

A proof with a photo or screenshot in it is never paid until it is approved here: the hour window and the verifier do not apply to pictures. Two buttons with an optional note:

- **Approve and pay.** The worker is paid; the task is done. The verification record says "approved by the operator after looking at the pictures" and carries the note.
- **Refuse: not paid.** The task expires, the reward returns to the pool or the payer, the worker's record takes a miss. If the client had already disputed it, the dispute is marked upheld.

Written proofs and written answers can be approved or refused here too, before the window or the verifier decides them.

#### Disputes

Tasks waiting for a decision: the proofs the verifier could not accept, proofs the client rejected, and decided tasks the client disputed. Each shows the task (linked), type, price, age and the reason. An optional "Note for the record".

- **Uphold: not acceptable.** The work was not acceptable. On a proof that was never accepted, the task expires and the reward returns to the pool or payer; the worker is not paid and their record takes a miss. On an already-paid task, the client is refunded from the fee pool (capped by what it holds) and the agreeing workers' records take a miss.
- **Reject: the work stands.** The proof is accepted and the worker is paid, or the decided task stays done.

Decisions are final and the client is told so in the terms.

#### Proposals

Scout proposals waiting for review, with "Post it" and "Refuse". Posting creates the task from the house pool with the proposing assistant as requester.

#### Held for review

Tasks moderation held, with the reason and the full payload. "Approve" routes the task (`paid → open`) and clears any reports; "Reject and refund" refunds the client in full. A client whose second task is rejected is blocked from posting.

#### Reports

Workers' reports: the task, the worker's id prefix and the reason. A reported task is already out of the feed and waiting under "Held for review"; the reporter has already been credited.

#### Money

**Contract** (`GET /v1/admin/escrow`): what the contract holds, how much is locked for tasks, fees waiting to be withdrawn, the operator wallet's ETH for gas, and the number of tasks pending, open and closed on chain. "Run settlement now" runs one pass of the contract loop immediately.

**Pool for platform tasks** (`GET /v1/admin/house`): available balance, open platform tasks, spent today against the daily budget, whether automatic posting is on. "Post a batch of tasks" runs one house round now. "Run the verifier" runs one verifier pass now.

### Sources (`/scouts`) operator box

Enter the key to get "Search now" (one scout round for every assistant) and, on each proposal in review, Post and Refuse.

### The admin API

| Call | What it does |
| --- | --- |
| `GET /v1/admin/responses?status=all\|waiting\|disputed\|approved\|refused&limit=100` | Every answer with task, worker, text, photos (`url` to fetch with the key), code, review and `decision`; `waiting` counts what needs a person |
| `POST /v1/admin/responses/{taskId}` `{decision: approve\|refuse, note}` | Approve pays the worker; refuse expires the task and returns the money. Decides an open dispute on the task the same way. `409 already_decided`, `409 not_decidable` for consensus types |
| `GET /v1/admin/review` | Tasks held by moderation, with payload and reason |
| `POST /v1/admin/review/{taskId}` `{decision: approve\|reject, note}` | Approve routes it; reject refunds it. `409 not_in_review` |
| `GET /v1/admin/disputes` | Open disputes with the task view |
| `POST /v1/admin/disputes/{id}` `{outcome: upheld\|rejected, note}` | Decide. `409 resolved` if already decided |
| `GET /v1/admin/reports` | Open reports |
| `GET /v1/admin/gold` | Gold tasks `{goldId, type, active, price}` |
| `POST /v1/admin/gold` `{type, payload, answer, tolerance, price}` | Add a gold task (payload validated like a real task; price defaults to the type base) |
| `GET /v1/admin/workers/{id}` | A worker with their last 50 flags and gold totals |
| `POST /v1/admin/workers/{id}` `{paused, reason}` | Pause or unpause |
| `POST /v1/admin/gate` `{title, payload}` or `{catalogue: true}` | Run the chatbot gate on one task or on the whole house catalogue |
| `GET /v1/admin/escrow` | Contract status (404 if no contract is configured) |
| `POST /v1/admin/escrow/run` | One contract-loop pass |
| `POST /v1/admin/verifier/run` | One verifier pass |
| `POST /v1/admin/scouts/run` | One scout round |
| `POST /v1/admin/scouts/proposals/{id}` `{decision: post\|reject, reason}` | Post or refuse a proposal. `409 not_possible` |
| `GET /v1/admin/house` | Pool status |
| `POST /v1/admin/house/deposit` `{rail, amount, transaction, memo}` | Record an on-chain top-up of the pool (`transaction` required outside local) |
| `POST /v1/admin/house/from-fees` `{rail, amount, memo}` | Move earned fees into the pool. Returns `{moved, houseBalance, feesLeft}` |
| `POST /v1/admin/house/post` | One house round now |
| `POST /v1/admin/team/run` `{tasks[], wallets[], teamRun, skipGate}` | Mark team wallets and post the team's test tasks from the pool |
| `POST /v1/admin/tasks/{id}/cancel` `{reason}` | Cancel a task that nobody has answered, with a full refund |

### Funding the pool

Send USDG to the operator wallet (`0xAd57…9a14`): the contract loop books the increase as a deposit within a minute. In wallet mode (the default) that wallet is also what platform rewards are paid from when workers press Claim, so its balance is the pool; claims stop with "today's reward budget is used up" once $300 has left it in 24 hours (`HA_WALLET_PAYOUT_DAILY_CAP`) and with "the reward wallet is being topped up" when it runs low. In contract mode the wallet tops up the contract when platform tasks are opened. A top-up sent to the contract directly can be recorded by hand with `POST /v1/admin/house/deposit` and the transaction hash. Fees that have accrued can be moved into the pool with `from-fees`; on chain, `withdrawFees()` sends them to the treasury wallet, and the books are reconciled by hand after each withdrawal.

Keep ETH in the operator wallet for gas (the Money tab shows it) and in the facilitator signer for settlements and gas help (`/health` on the facilitator shows a low-gas flag).

### Posting photo tasks

The twelve go-and-see photo tasks in the catalogue cost about $45 each with the fee. They post only when the pool can cover them, so they wait until the pool is topped up.

### Team runs

The team's own end-to-end tests of the payment path:

- `api/scripts/team_run.py`: signs in and qualifies 20 wallets from `.launch-wallets.json`, records a deposit, posts 10 Check tasks at $2 × 3 workers as team runs, answers each with 2 right and 1 wrong, waits for the contract to open and close them, and writes `data/team-run.json`. Resumable.
- `api/scripts/quick_run.py` with `quick_tasks.py`: 50 $1 Check tasks; `run` posts 10 as a team run, `rest` posts 40 open to anyone.
- `api/scripts/sweep_team_wallets.py`: returns the test wallets' USDG to the owner wallet, topping up gas first.

Team tasks and wallets are labelled everywhere and excluded from public totals.

### Other scripts

| Script | What it does |
| --- | --- |
| `api/scripts/run_mainnet.sh` | Runs the mainnet task service in a restart loop (local hosting; superseded by Render) |
| `facilitators/scripts/withdraw.py` | Withdraws the facilitator signer's ETH to the owner wallet; dry run unless `--send` |
| `contracts/script/deploy.py` | Deploys TaskEscrow; prints the gas estimate, sends only with `--send` |
| `api/demo/seed_tasks.py`, `api/demo/pay_task.py` | Local demo helpers |

### A daily checklist

1. Open `/operator`: clear Disputes, Held for review and Proposals.
2. Check the Money tab: the pool's balance against the daily budget and the open-task cap; the contract's "fees waiting"; the operator wallet's gas.
3. Check `/health` on the task service (ledger balanced, no chain drift, facilitator reachable) and on the facilitator (signer balance, no low-gas flag, no uncertain settlements piling up).
4. Look at `/rewards` and the Activity tab on `/tasks` for anything odd: a burst of expired tasks, a worker paid many times in minutes.
5. Review paused workers (`GET /v1/admin/workers/{id}`) and unpause the ones that were paused by a false flag.
6. If the scouts are on, glance at `/scouts` for refused proposals and the daily call count.


---

## 8. Architecture and settings

### The pieces

```text
  browser ──────────────► web (Next.js, :3000)
     │                        │  every page calls the API directly from the browser
     │                        ▼
     └──────────────────► api (FastAPI, :8400) ──────► facilitator (FastAPI, :8402) ──► Robinhood RPC / Solana RPC
  software clients ─────►  │   ├─ Postgres (Neon)        verify, settle, gas; the only settlement key
     (x402)                │   ├─ Redis (proof photos)
                           │   ├─ Vercel AI Gateway (scouts, verifier, gate)
                           │   └─ Robinhood RPC: TaskEscrow contract, signed by the operator wallet
```

| Process | Owns | Talks to | Exposure |
| --- | --- | --- | --- |
| `web` | The website: landing, board, task pages, Earn, client area, operator page | `api` only, from the browser | Public |
| `api` | Tasks, quotes, the 402 flow, workers, sessions, ledger, consensus, verifier, scouts, house poster, payouts, the contract loop, admin | `facilitator`, Postgres, Redis, the AI gateway, Robinhood RPC | Public |
| `facilitator` | x402 `/supported`, `/verify`, `/settle`, `/gas`; replay store; the settlement signer | Robinhood RPC, Solana RPC, its own database | Called by `api` with a bearer token (verify and health are open) |
| TaskEscrow | Holds rewards, pays workers, keeps fees, refunds | | Robinhood Chain mainnet |

There is no separate jobs process: all background work runs on threads inside the task service, which is why only one copy of it may run (see [6. Payments](#6-payments-and-escrow)).

### Inside the task service

All HTTP routes are defined in `app.py` and call into service modules:

| Module | Responsibility |
| --- | --- |
| `pricing.py` | Task types, the request model, validation, quotes, the fee, the platform price formula, US-only checks, location normalisation |
| `states.py` | The state machine; the only writer of `Task.state`; events; purge scheduling |
| `tasks.py` | Create, claim, answer, complete (consensus and settlement), expire, cancel, refund routing, disputes |
| `consensus.py` | majority, match, median, single |
| `ledger.py` | Double-entry postings and the invariant |
| `x402.py` | 402 requirements, header decoding, the facilitator client |
| `escrow_chain.py`, `chain.py` | The contract loop, the settle-on-claim path and the read-only chain client |
| `house.py`, `catalogue.py`, `catalogue_more.py`, `manual_tasks.py`, `photo_tasks.py`, `templates.py` | The platform poster, the 15 categories, the 351-task house catalogue, the 100 templates |
| `scouts.py`, `gate.py`, `verifier.py` | The assistants that propose tasks, the chatbot gate, the proof reviewer |
| `workers.py`, `auth.py`, `qualification.py`, `quality.py` | Feed, claim, answer validation, photos, earnings, the reward claim; wallet sign-in; practice questions; reputation, tiers, gold, abuse flags |
| `moderation.py` | Rule-based classification plus the optional external classifier |
| `admin.py` | Review queue, disputes, reports, gold, workers, purge |
| `payouts.py`, `payout_chain.py` | The batched payout job and the chain senders |
| `storage.py` | Proof photos in Redis (or memory) |
| `webhooks.py` | Signed deliveries with retries |
| `jobs.py` | The 2-second ticker and the 4-second contract loop |
| `echo_worker.py` | Local-only automatic workers for exercising the money path |
| `geo.py` | City coordinates, place resolution, map links |
| `config.py`, `models.py`, `db.py` | Settings, the SQLAlchemy models, the engine |

#### Background work

A "jobs" thread ticks every 2 seconds and, each tick: expires holds; expires overdue tasks (200 at a time); auto-accepts proofs older than an hour; purges tasks past their retention date (200 at a time); runs the echo worker if on; delivers due webhooks (50 at a time); deletes stale quotes and idempotency keys; and, when their interval has elapsed, runs a payout round (10 min), a house round (5 min), a verifier pass (every tick, 3 tasks) and a scout round (15 min). A separate "escrow" thread runs the contract loop every 4 seconds when a contract is configured. `HA_JOBS_ENABLED=false` turns all of it off.

The facilitator runs its own recovery thread every 60 seconds.

#### Caching

Public board, stats, activity and rewards responses are cached for `HA_PUBLIC_CACHE_SECONDS` (10 s on Render; rewards at least 20 s). The facilitator's `/supported` answer is cached for 60 s. Every response carries an `X-Response-Time-Ms` header.

#### Sessions and tokens

| Token | Prefix | Issued by | Lifetime |
| --- | --- | --- | --- |
| Worker session | `wks_` | `POST /v1/workers/session` | 30 days |
| Client session | `cls_` | `POST /v1/clients/session` | 30 days |
| Buyer token | `bt_` | the 202 that created the task | the task |
| Per-task webhook secret | `whsec_` | the 202 | the task |
| Buyer-level webhook secret | `whbs_` | `POST /v1/webhooks` | until replaced |
| Admin | the value of `HA_ADMIN_TOKEN` | configuration | |
| Facilitator settle token | the value of `HF_SETTLE_TOKEN` | configuration | |

Sign-in nonces live 10 minutes and are single-use. There is no endpoint to revoke a session.

### Data model

Every table in the task service's database (Postgres on Neon in production; SQLite locally), with its key columns. Ids carry a prefix.

| Table | Prefix | Key columns |
| --- | --- | --- |
| `buyers` | `by_` | payer, rail, reputation, blocked, tasks_paid, name. Unique (rail, payer). The house is payer `house` |
| `client_sessions` | `cls_` | buyer_id, expires_at, revoked |
| `quotes` | `qt_` | body_hash, kind (task or batch), body, total, worker_pool, fee, expires_at, consumed_by |
| `payments` | `pay_` | rail, network, asset, payer, pay_to, amount, transaction, quote_id. Unique (network, transaction) |
| `tasks` | `task_` | batch_id, buyer_id, payment_id, rail, type; title, location, acceptance, difficulty, effort_minutes, template_id, reference, requester, payload, price_per_worker, workers_wanted, fee, min_reputation, time_limit_seconds, deadline; state, result, agreement, verification, review, team_run; chain_state, chain_open_tx, chain_close_tx; webhook_url, webhook_secret, buyer_token; moderation, moderation_reason; created_at, updated_at, completed_at, purge_after, purged |
| `task_events` | | task_id, at, from_state, to_state, reason, actor |
| `workers` | `wk_` | handle (`<rail>:<wallet>`, unique), rail, wallet, reputation, tier, paused, paused_reason, languages, location, qualified_types, terms_accepted_at, last_seen, answered, agreed, gold_total, gold_correct, by_type, team, gas_granted_at |
| `nonces` | | nonce, wallet, network, message, expires_at |
| `worker_sessions` | `wks_` | worker_id, expires_at, revoked |
| `claims` | `clm_` | task_id, worker_id, claimed_at, expires_at, released, code (the capture code). Unique (task_id, worker_id) |
| `photos` | `ph_` | task_id, worker_id, claim_id, content_type, size, code, lat, lng, accuracy_m, distance_m, deleted |
| `answers` | `ans_` | task_id, worker_id, answer `{value, confidence}`, note, submitted_at, seconds, agrees, paid. Unique (task_id, worker_id) |
| `ledger` | | at, rail, debit, credit, amount, task_id, payment_id, memo |
| `payouts` | `po_` | rail, worker_id, task_id (null for bonuses), amount, status (queued, claimable, sending, sent, failed), kind (task or bonus), batch_ref (the transaction), attempts, sent_at |
| `refunds` | `rf_` | rail, payer, task_id, amount, reason, status, kind, transaction, attempts, sent_at |
| `webhooks` | `wh_` | buyer_id, url, secret, active |
| `webhook_deliveries` | `whd_` | task_id, url, secret, event, body, attempts, next_at, status (pending, delivered, failed), last_status, last_error |
| `gold_tasks` | `gold_` | type, payload, answer `{value, tolerance}`, price, active |
| `gold_results` | `gr_` | gold_id, worker_id, answer, correct, at |
| `worker_flags` | `flag_` | worker_id, kind (fast_answer, duplicate_text, burst, gold_wrong), detail, at |
| `disputes` | `dsp_` | task_id, buyer_id, reason, status (open, upheld, rejected), outcome_note, refund, resolved_at |
| `reports` | `rep_` | task_id, worker_id, reason, status (open, task_rejected, cleared) |
| `scout_runs` | `run_` | requester, model, at, ok, error, proposed, input_tokens, output_tokens |
| `proposals` | `prop_` | run_id, requester, title, raw, body, why, price, status (review, posted, rejected), reason, task_id, decided_at |
| `idempotency_keys` | | key, body_hash, status, response, headers, created_at |

Migrations (Alembic, `api/alembic/versions`): 0001 initial schema; 0002 nonces, sessions, payout attempts, worker fields; 0003 gold, flags, disputes, reports, buyer token, moderation, purge; 0004 client sessions, task spec, verification, worker location; 0005 requester; 0006 scouts; 0007 task review; 0008 payout kinds and chain state; 0009 team runs; 0010 photos, capture codes, gas help. The Docker image runs `alembic upgrade head` before starting; the app also calls `create_all()` and seeds the gold tasks when the table is empty.

The facilitator has its own small database (SQLite file in the `facilitator-data` volume, or Postgres): `settlements`, `pending`, `events`, `gas_grants`.

Proof photo bytes live in Redis (`photo:<id>`, 90-day TTL); without `HA_REDIS_URL` they live in memory and are lost on restart.

### Settings reference

#### Task service (`HA_` prefix, read from `api/.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `HA_ENV` | `local` | `local`, `testnet` or `mainnet`. Dev login and the echo worker work only in `local` |
| `HA_HOST`, `HA_PORT` | `0.0.0.0`, `8400` | Bind address; the Docker image maps `PORT` to `HA_PORT` |
| `HA_LOG_LEVEL` | `INFO` | |
| `HA_PUBLIC_BASE_URL` | `http://127.0.0.1:8400` | Used in result and receipt URLs |
| `HA_DATABASE_URL` | `sqlite:///./humanapi.db` | Postgres on Render |
| `HA_CORS_ORIGINS` | localhost and 127.0.0.1 on 3000 and 3123 | The website's origin |
| `HA_PUBLIC_CACHE_SECONDS` | `10.0` | Cache for public board, stats, activity, rewards |
| `HA_JOBS_ENABLED` | `true` | Background threads |
| `HA_ADMIN_TOKEN` | empty (admin off) | Operator key |
| **Facilitator** | | |
| `HA_FACILITATOR_URL` | `http://127.0.0.1:8402` | |
| `HA_FACILITATOR_SETTLE_TOKEN` | empty | Must equal `HF_SETTLE_TOKEN` |
| `HA_FACILITATOR_TIMEOUT_SECONDS` | `120` | |
| **Rails** | | |
| `HA_ROBINHOOD_ENABLED` | `false` | |
| `HA_ROBINHOOD_NETWORK` | `eip155:46630` | `eip155:4663` on mainnet |
| `HA_ROBINHOOD_ASSET` | empty (USDG on mainnet) | Token address |
| `HA_ROBINHOOD_ESCROW_ADDRESS` | | The pay-to address; with the contract, the contract address |
| `HA_ROBINHOOD_RPC_URL` | the chain default | |
| `HA_SOLANA_ENABLED` | `false` | |
| `HA_SOLANA_NETWORK` | devnet | |
| `HA_SOLANA_ASSET`, `HA_SOLANA_ESCROW_ADDRESS`, `HA_SOLANA_RPC_URL` | | |
| **Escrow contract** | | |
| `HA_ESCROW_CONTRACT` | empty | The TaskEscrow address; turns the contract loop on |
| `HA_ESCROW_OPERATOR_PRIVATE_KEY` | | Signs open, settle, refund and pool top-ups |
| `HA_ESCROW_LOCK_ON_CLAIM` | `true` | In contract mode, platform tasks lock money when taken, not when listed |
| `HA_ESCROW_HOUSE_PAYER` | the operator address | The payer recorded on chain for platform tasks |
| `HA_HOUSE_PAYOUT` | `wallet` | `wallet`: platform rewards are sent from the operator wallet when the worker claims; `contract`: locked and settled on the contract |
| `HA_WALLET_PAYOUT_DAILY_CAP` | `300000000` | $300 of wallet-sent rewards per 24 hours |
| **Money** | | |
| `HA_PLATFORM_FEE_BPS` | `2000` | 20% |
| `HA_MIN_REWARD` | `1500000` | $1.50 |
| `HA_QUOTE_TTL_SECONDS` | `300` | |
| `HA_MAX_TIMEOUT_SECONDS` | `300` | `maxTimeoutSeconds` in the 402 |
| `HA_BATCH_MAX` | `100` | |
| `HA_IDEMPOTENCY_TTL_SECONDS` | `86400` | |
| `HA_WEBHOOK_MAX_ATTEMPTS` | `8` | |
| **Payout job** | | |
| `HA_PAYOUTS_ENABLED` | `false` | |
| `HA_PAYOUT_INTERVAL_SECONDS` | `600` | |
| `HA_PAYOUT_MIN_AMOUNT` | `100000` | $0.10 |
| `HA_PAYOUT_ROUND_CAP` | `2000000000` | $2,000 per rail per round |
| `HA_ROBINHOOD_ESCROW_PRIVATE_KEY`, `HA_SOLANA_ESCROW_PRIVATE_KEY` | | Must match the escrow addresses |
| **Workers** | | |
| `HA_SESSION_TTL_SECONDS` | `2592000` | 30 days |
| `HA_NONCE_TTL_SECONDS` | `600` | |
| `HA_CLAIM_HOLD_SECONDS` | `120` | |
| `HA_ONLINE_WINDOW_SECONDS` | `600` | |
| `HA_FEED_LIMIT` | `30` | |
| `HA_DEV_LOGIN` | `false` | Local only |
| `HA_ECHO_WORKER` | `false` | Local only |
| **Quality and safety** | | |
| `HA_MODERATION_URL` | empty | Optional external classifier |
| `HA_MODERATION_BLOCK_AFTER` | `2` | Rejected tasks before a client is blocked |
| `HA_GOLD_EVERY` | `20` | A gold check every N answers |
| `HA_GOLD_WRONG_PAUSE` | `3` | Wrong gold answers in 24 h that pause |
| `HA_ABUSE_FLAGS_PAUSE` | `3` | Flags in 24 h that pause |
| `HA_DISPUTE_WINDOW_SECONDS` | `86400` | |
| `HA_RETENTION_DAYS` | `30` | Defined but unused; the purge is fixed at 30 days |
| **Photos** | | |
| `HA_REDIS_URL` | empty (memory) | |
| `HA_PHOTO_MAX_BYTES` | `6000000` | |
| `HA_PHOTO_MAX_PER_ANSWER` | `3` | |
| `HA_GEO_RADIUS_M` | `300` | |
| **House poster** | | |
| `HA_HOUSE_POSTER_ENABLED` | `false` | |
| `HA_HOUSE_INTERVAL_SECONDS` | `300` | |
| `HA_HOUSE_BATCH_SIZE` | `3` | |
| `HA_HOUSE_PICTURES_PER_BATCH` | `1` | At most this many photo or screenshot tasks in each house batch; the operator checks every picture by hand |
| `HA_HOUSE_LIST_SECONDS` | `86400` | |
| `HA_HOUSE_MAX_OPEN` | `240` | |
| `HA_HOUSE_DAILY_BUDGET` | `2000000000` | $2,000 |
| `HA_HOUSE_RAIL` | `robinhood` | |
| `HA_SECOND_WORKER_EVERY` | `5` | One action task in N wants two workers |
| **Scouts, verifier, gate** | | |
| `HA_AI_GATEWAY_API_KEY` | empty | Vercel AI Gateway key; without it scouts, verifier and gate are off |
| `HA_AI_GATEWAY_BASE_URL` | `https://ai-gateway.vercel.sh/v1` | |
| `HA_SCOUTS_ENABLED` | `false` | |
| `HA_SCOUT_MODELS` | claude=anthropic/claude-haiku-5.5, chatgpt=openai/gpt-5.4-mini, gemini=google/gemini-3.8-flash, grok=spacexai/grok-4.1-fast-non-reasoning, deepseek=deepseek/deepseek-v4-flash | |
| `HA_SCOUT_INTERVAL_SECONDS` | `900` | |
| `HA_SCOUT_PROPOSALS_PER_RUN` | `3` | |
| `HA_SCOUT_AUTO_POST` | `false` | |
| `HA_SCOUT_DAILY_CALLS` | `200` | |
| `HA_VERIFIER_ENABLED` | `false` | |
| `HA_VERIFIER_VISION_MODEL` | `google/gemini-3.8-flash` | |
| `HA_VERIFIER_DEFAULT_MODEL` | `anthropic/claude-haiku-5.5` | |
| `HA_GATE_ENABLED` | `false` | |
| `HA_GATE_MODEL` | `openai/gpt-5.4-mini` | |
| **Privy** | | |
| `HA_PRIVY_APP_ID` | | Present in the Docker settings file |

Validation at start: an enabled rail needs an asset and an escrow address; payouts need the key for each enabled rail; with the contract, the operator key is required and the Robinhood escrow address must equal the contract; the fee must be 0 to 9999 basis points; dev login and the echo worker are refused outside `local`.

#### Facilitator (`HF_` prefix, read from `facilitators/.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `HF_ENV` | `local` | `mainnet` requires 4663, Solana mainnet and a settle token |
| `HF_HOST`, `HF_PORT` | `0.0.0.0`, `8402` | |
| `HF_LOG_LEVEL` | `INFO` | JSON lines on stdout |
| `HF_DATABASE_URL` | `sqlite:///./facilitator.db` | `sqlite:` or `postgres:` |
| `HF_SETTLE_TOKEN` | empty | Bearer for `/settle` and `/gas` |
| `HF_RATE_LIMIT_PER_MINUTE` | `120` | 0 disables |
| `HF_SETTLE_TIMEOUT_SECONDS` | `90` | |
| `HF_STUCK_AFTER_SECONDS` | `180` | When a `sending` row counts as unresolved |
| `HF_DAILY_SETTLEMENT_CAP` | `5000` | |
| `HF_ROBINHOOD_ENABLED` | `false` | |
| `HF_ROBINHOOD_NETWORK` | `eip155:46630` | |
| `HF_ROBINHOOD_RPC_URL` | the chain default | |
| `HF_ROBINHOOD_PRIVATE_KEY` | | Hex; the settlement signer |
| `HF_ROBINHOOD_ASSETS` | USDG on 4663 | Comma separated |
| `HF_ROBINHOOD_CONFIRMATIONS` | `3` | |
| `HF_ROBINHOOD_MAX_AMOUNT` | `1000000000` | 1,000 USDG |
| `HF_ROBINHOOD_MIN_GAS_WEI` | `10000000000000000` | 0.01 ETH |
| `HF_GAS_GRANT_WEI` | `20000000000000` | 0.00002 ETH |
| `HF_GAS_GRANTS_PER_DAY` | `300` | |
| `HF_GAS_GRANT_HOURS_BETWEEN` | `24` | |
| `HF_SOLANA_ENABLED` | `false` | |
| `HF_SOLANA_NETWORK` | devnet | |
| `HF_SOLANA_RPC_URL` | the chain default | |
| `HF_SOLANA_PRIVATE_KEY` | | Base58 64-byte keypair |
| `HF_SOLANA_ASSETS` | USDC | |
| `HF_SOLANA_MAX_AMOUNT` | `1000000000` | |
| `HF_SOLANA_MIN_LAMPORTS` | `50000000` | 0.05 SOL |

#### Website (`NEXT_PUBLIC_` build arguments)

See [2. The website](#2-the-website): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_ROBINHOOD_NETWORK`, `NEXT_PUBLIC_SOLANA_NETWORK`, `NEXT_PUBLIC_PRIVY_APP_ID`, `NEXT_PUBLIC_DEV_LOGIN`.

#### Compose (root `.env`)

`WEB_PORT`, `API_PORT`, `FACILITATOR_PORT`, `PUBLIC_API_URL` (compiled into the site), `WEB_ORIGIN` (the API's CORS origin), `PRIVY_APP_ID`, `ROBINHOOD_NETWORK`.

### Settings files that hold secrets

All are ignored by git: root `.env`, `.env.facilitator`, `web/.env.local`, `api/.env`, `api/.env.docker`, `api/.env.mainnet`, `facilitators/.env`, `facilitators/.env.docker`, `facilitators/.env.mainnet`, `contracts/.env` (`DEPLOYER_PRIVATE_KEY`), `.launch-wallets.json` (the 20 team test wallets), `facilitators/demo/.keys.json` (throwaway testnet keys). Templates without secrets: `api/.env.example`, `api/env.docker.example`, `facilitators/.env.example`, `facilitators/env.docker.example`.


---

## 9. Running and deploying

### Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/) for the task service and the facilitator.
- Node 22 and pnpm 10 for the website.
- Docker with buildx for the images.
- The `render` CLI, signed in to the Render account that owns the services, for deployment.

Port 3000 on the development machine is usually taken by another process, so the website runs on 3123 locally (`WEB_PORT` in the root `.env`).

### Running each service locally

#### Facilitator (port 8402)

```bash
cd facilitators
uv sync --extra dev
cp .env.example .env          # testnet template: Robinhood 46630, Solana devnet
uv run humanapi-facilitator
uv run pytest                 # 19 unit tests, no network
```

Set `HF_ROBINHOOD_PRIVATE_KEY` (and `HF_SOLANA_PRIVATE_KEY` if Solana is on) in `.env`. `demo/setup_robinhood.py` and `demo/setup_devnet.py` create throwaway keys in `demo/.keys.json` and print the matching `HF_*` lines; they need test funds (Robinhood faucet `https://faucet.testnet.chain.robinhood.com`, Solana `https://faucet.solana.com`).

A paywalled demo server and clients for both rails exercise the whole x402 round trip: `uv run python demo/server.py` (port 8403), then `uv run python demo/client_robinhood.py` or `demo/client_solana.py`.

#### Task service (port 8400)

```bash
cd api
uv sync --extra dev
cp .env.example .env
uv run alembic upgrade head
uv run humanapi-api           # OpenAPI docs at http://127.0.0.1:8400/docs
uv run pytest                 # 99 tests, mocked facilitator and chain
```

Useful local flags in `.env`:

| Flag | Effect |
| --- | --- |
| `HA_DEV_LOGIN=true` | `POST /v1/workers/dev-session` and `/v1/clients/dev-session` sign in any address without a signature (local only) |
| `HA_ECHO_WORKER=true` | Automatic workers answer every open task so the money path can be watched (local only) |
| `HA_HOUSE_POSTER_ENABLED=true` | The platform posts from its pool; deposit with `POST /v1/admin/house/deposit` first, or post a batch now with `POST /v1/admin/house/post` |
| `HA_ADMIN_TOKEN=...` | Turns the admin API and the operator page on |
| `HA_FACILITATOR_SETTLE_TOKEN` | Must equal the facilitator's `HF_SETTLE_TOKEN` |

Seed some tasks for the Earn pages with `uv run python demo/seed_tasks.py`. Pay for a task from a script against the real facilitator with `uv run --extra demo python demo/pay_task.py robinhood` (or `solana`).

#### Website (port 3123 locally)

```bash
cd web
pnpm install
pnpm dev --port 3123
pnpm lint && pnpm build
```

`web/.env.local` sets `NEXT_PUBLIC_API_URL` (the local API), `NEXT_PUBLIC_ROBINHOOD_NETWORK`, `NEXT_PUBLIC_PRIVY_APP_ID` and, for the local sign-in box, `NEXT_PUBLIC_DEV_LOGIN=1`. The API's `HA_CORS_ORIGINS` default already allows `http://localhost:3123`.

There are no automated tests for the website; the checks are lint, build and a walk through the pages in a browser (the Earn flow, a task page, the client pages, and the phone width at 390 px).

#### Contract

```bash
cd contracts
python script/build.py        # writes out/TaskEscrow.json
pytest                        # 6 tests on an in-process EVM
python script/deploy.py       # prints the gas estimate; add --send to deploy
```

The Python packages for this (py-solc-x, eth-tester, web3) are not pinned in a manifest; install them into the environment used.

### Docker Compose (all three together)

```bash
cp api/env.docker.example api/.env.docker                    # mainnet template
cp env.facilitator.example .env.facilitator
docker compose up --build -d
```

| Service | Built from | Port on the host | Health check |
| --- | --- | --- | --- |
| `web` | `web/Dockerfile` | `127.0.0.1:${WEB_PORT:-3000}` | `/` |
| `api` | `api/Dockerfile` | `127.0.0.1:${API_PORT:-8400}` | `/v1/stats` |
| `facilitator` | `ghcr.io/useh402/facilitator` | `127.0.0.1:${FACILITATOR_PORT:-8402}` | `/health` |
| `postgres` (profile `localdb`) | postgres:16-alpine | `127.0.0.1:5432` | `pg_isready` |

The API waits for the facilitator to be healthy and reaches it at `http://facilitator:8402`. The website is built with `PUBLIC_API_URL` compiled in, so changing the API address means rebuilding `web`. Keep the `facilitator-data` volume: it records settled payments. All three images run as a non-root user and honour `PORT`.

Everyday commands: `docker compose logs -f`, `docker compose restart api`, `docker compose up --build -d web`, `docker compose down`. For a local Postgres: `docker compose --profile localdb up -d` and `HA_DATABASE_URL=postgresql+psycopg://humanapi:humanapi@postgres:5432/humanapi`.

**Only one copy of the task service may run.** Stop the local `api` container while the Render service is live.

### Production on Render

Three web services on Render (region Oregon, starter plan), deployed from Docker images in a registry, never from a git host:

| Service | URL | Image |
| --- | --- | --- |
| Website | https://humanapi-web.onrender.com | `$REGISTRY/humanapi-web:<tag>` |
| Task service | https://humanapi-api.onrender.com | `$REGISTRY/humanapi-api:<tag>` |
| Facilitator | https://humanapi-facilitator.onrender.com | `ghcr.io/useh402/facilitator:<tag>`, built by that repository's CI |

The database is Neon Postgres. Settings are environment variables on each service, taken from `api/.env.docker` and `.env.facilitator` at creation, plus `HA_FACILITATOR_URL`, `HA_CORS_ORIGINS` and `HA_PUBLIC_CACHE_SECONDS=10` on the API.

#### Shipping a change

`deploy/render.sh` does everything. `REGISTRY` is required; `TAG` defaults to the short git commit.

```bash
export REGISTRY=docker.io/<your-namespace>
deploy/render.sh build    # builds the website and API images for linux/amd64; the web image gets
                          # NEXT_PUBLIC_API_URL=https://humanapi-api.onrender.com, the mainnet network,
                          # the Privy app id from web/.env.local and NEXT_PUBLIC_DEV_LOGIN=0
deploy/render.sh push     # pushes them to Docker Hub
deploy/render.sh update   # points each Render service at the new image and starts a deploy
```

Changing a service's image on Render does not deploy by itself; the script runs `render deploys create` for each service after the update. `deploy/render.sh create` (or `create-backend`, `create-web`) creates the services from scratch, facilitator first, then the API, then the website.

After a deploy, check something only the new build has (a new page, a changed string) rather than trusting the "Live" status alone: Render can report a deploy live while the previous instance keeps serving.

#### Health

- Task service: `GET /health` (ledger balanced per rail, chain drift, task counts, facilitator reachable; 503 on any failure) and `GET /v1/stats` (the Render health check).
- Facilitator: `GET /health` (each rail's signer, head block, native balance and low-gas flag; settlement counts by status; database).
- Website: `GET /`.

Logs: `render logs -r <service id> --start <ISO time> -o text`.

#### Keys that must be funded

| Wallet | Holds | Used for |
| --- | --- | --- |
| Operator wallet `0xAd57…9a14` | USDG and ETH | Pays platform rewards when workers claim them (wallet mode); opens, settles and refunds tasks on the contract; USDG sent here funds the pool |
| Facilitator signer `0x60F0…7b9E` | ETH only | Submits x402 settlements and pays gas help |

### Tests at a glance

| Where | Command | Count | Needs |
| --- | --- | --- | --- |
| `api/` | `uv run pytest` | 99 | nothing external |
| `facilitators/` | `uv run pytest` | 19 | nothing external |
| `contracts/` | `pytest` | 6 | py-solc-x, eth-tester |
| `web/` | `pnpm lint && pnpm build` | | |


---

## 10. Policies and known gaps

### United States only

Every task, place, example, phone number, currency, app and piece of copy is for the United States. The API refuses anything naming India at creation; locations must be Remote or `City, ST` with a real state. Use US businesses (Walgreens, Target, Whole Foods), US cities, dollars, sales tax, and Spanish rather than Hindi when a second language is needed. Check new catalogue entries, templates and copy against this before committing.

### Plain professional copy

Every screen a worker or client uses reads like a serious work marketplace. The words are **client** (or requester), **task**, **worker** (or you), **reward**, **accepted**, **paid**. Not used on those screens: "AI", "agent", "LLM", "bot", "echo worker", "demo", "test", "dev", "sample", or any internal term. Technical words belong in code, in the developer documentation (`/client/docs` and this guide) and in the operator tools. Real content, never placeholders: no lorem text, no fake counters, no "sample" labels on screens real people use.

The one deliberate exception is the model-training disclosure below.

### Nobody posts by hand

The website has no page for posting a task. Tasks come from the platform's poster, from the scouts after an operator's review, and from software through the API. People only take and solve tasks.

### What a task can never ask for

Refused before it reaches anyone, and refunded:

- Passwords, one-time codes, private keys, seed phrases, payment details, or logging in to anyone's account.
- Solving a bot check so that a script can get in. (A person may do the whole visit themselves and report what they saw.)
- Sexual content involving minors; violence.

Held for a person to look at first:

- Buying, paying or transferring money on someone's behalf; pretending to be someone (action tasks).
- Phone numbers (except in call tasks), email addresses, identity documents, private individuals, sexual content, hate.

The line: businesses, places and public listings only; a person does the whole visit or call as themselves; the client pays for things themselves; nothing about a private individual. Workers can report anything that slips through and are still paid.

### Pay only on acceptance

Money is held before anyone starts. Workers are paid when the work is accepted: by agreement with the other answers, by the client's or the verifier's acceptance of proof, or automatically an hour after a proof is submitted. On platform tasks the accepted worker claims the reward and it is sent at once; on client tasks the contract pays it at settlement. Unfilled slots and undecided tasks are refunded. Payments are on chain and cannot be reversed. Goodwill (gold rewards, report credits, upheld-dispute refunds) comes only from the platform's fee pool.

### Terms of Use, Privacy Policy and the training disclosure

The model H402 is building from human responses is named **Otto**. The announcement, the docs page, the terms and the privacy policy all name it.

H402 is training its own language model on the work done on the platform. This is disclosed in three places, as decided on 2026-10-11 (decision 29):

1. **The first-visit announcement** on the site: responses train models (H402's and its partners'); responses are checked by assistants from several providers (Claude, ChatGPT, Gemini, Grok, DeepSeek) and compared with other people's answers, with an operator deciding what the assistants cannot; rewards are paid on chain in USDG, irreversibly, for US tasks only. Shown once per browser.
2. **The Terms of Use** (last updated October 10, 2026), section "Training and automated review": responses, notes and photos may be used to train and improve language models and verification systems operated by H402 and its partners, with the wallet address and identifying details removed first; responses are reviewed by the named assistants and compared with other people's responses before an operator decides anything the assistants cannot; anyone who does not want this should not submit.
3. **The Privacy Policy**: who sees what (the client, visitors under an anonymous label, operators, the review assistants, and model training on de-identified data), and retention (task content and responses removed 30 days after the decision, photos within 90 days, payment and wallet records kept while the service is used).

Other terms a worker agrees to: 18 or older, in the United States, an independent contractor who handles their own taxes; the work is done by the person themselves, one person one wallet, no software answering for them; photos are their own, taken at the stated time and place with the capture code; they keep ownership of what they submit and license it to H402 and the client; decided responses may be shown without the wallet; disputes are decided by an operator and are final; the service is provided as is with liability limited to rewards owed for accepted work.

Tasks and responses posted through the API are part of the training data too. There is no client opt-out yet.

A planned next step goes further than what is on the site today (a "Terms of Service" rename, a versioned announcement keyed by terms date, a "Model training" section with the retention exception, a `web/src/lib/terms.ts` constant, and recording acceptance per wallet).

### Data kept and for how long

| Data | Kept | For how long |
| --- | --- | --- |
| Wallet address | Yes (never the keys) | While the service is used |
| Responses, notes, time taken | Yes | 30 days after the task is decided, then purged |
| Proof photos, with location when the task required it | Yes, visible to the client, the operator and the verifier | At most 90 days; purged with the task at 30 |
| Reputation, flags, gold results | Yes | While the service is used |
| Payments and payouts | Yes, and on chain | Permanently |
| Name, email, phone, ID | Not collected | |

Hosting is in the United States with photos at a separate provider (Redis). Task content and responses are deleted 30 days after the decision. Payloads are not encrypted at rest in the application; that is left to the database host.

### Team activity

Test runs by the team's own wallets are marked "H402 team" on the board, the task page, the ticker and the rewards page, and are excluded from public totals. The money from those runs is swept back to the owner wallet.

### Secrets

Keys live in ignored settings files and are never committed, printed or logged (the facilitator's logger never writes payloads, signatures or keys). Secrets that were shared in chat during the build (the owner wallet key, the Neon password, the Redis password, the Privy secret, the model gateway key) should be rotated. The contract's owner and treasury should move to a wallet whose key has never been shared.

### Known gaps and inconsistencies

Where the site, the plans and the code do not yet agree, as of October 2026:

**Money and chains**

- The FAQ, the Earn page, the worker terms, the task page's price box and the practice task still say rewards are paid "in batches every ten minutes". Since 2026-10-11 a platform task's reward is claimed by the worker and sent at once from the platform's wallet; only bonuses and non-contract rows go out in batches.
- The FAQ, the Earn page and the site's metadata say rewards are paid in USDC on Solana or USDG on Robinhood Chain; the announcement, the terms, the Trust section ("USDC on Solana, coming next"), the contact page and the practice task say USDG on Robinhood Chain only. In production, sign-in through Privy always uses Robinhood Chain. The accurate statement is Robinhood Chain today, Solana next.
- The site contains a working browser payment function (Permit2) that no page calls; there is no browser posting, by design.
- The contract is unaudited (source verified on Blockscout since 2026-10-11), and owner, operator and treasury are one shared wallet.
- The contract's limits were lowered on 2026-10-11 to 60 USDG per task and 300 USDG per day. In contract mode a task whose total (rewards plus fee) exceeds 60 USDG, for example a two-worker action task near the $50 cap, cannot be opened on the contract. The task service does not check this at creation.
- Two payment modes for platform tasks exist (`HA_HOUSE_PAYOUT`: `wallet` is the code default, `contract` is what the contract notes call the live flow). Which one production runs is set only by that environment variable on Render.
- Fees withdrawn from the contract are reconciled with the ledger by hand.
- The twelve go-and-see photo tasks wait for the pool to be topped up (about $45 each with the fee).

**Who decides proof**

- The FAQ and the developer docs say the client accepts proof or it is accepted after an hour; the task page's submit message says the response is reviewed automatically within a minute with unclear ones going to a person; the operator page calls disputes "responses the verifier could not accept". All three are true at once: the verifier (when on) reviews first, the client may act, and auto-accept is the fallback. The copy could say so in one place.
- `submitted → claimed` is a legal transition that nothing uses.

**Training disclosure**

- The announcement says the wallet address is kept out of training data; the terms say the wallet and identifying details are removed first. Same meaning, two wordings. The planned "Terms of Service" rewrite, the versioned announcement and acceptance recording are not built.

**Workers**

- The Earn task list does not expose the API's filters (category, type, minimum price, location).
- Phone layouts for the Earn area have not been done; the photo flow has not been tried with a real phone camera.
- There is no worker-side appeal form for a pause; a pause is lifted only by the operator.
- There is no notification channel for new tasks or payments.

**Operator and admin**

- There are no admin screens for gold tasks, workers or the review of reports beyond the display on `/operator`; those go through the admin API.
- `HA_RETENTION_DAYS` exists but the purge is fixed at 30 days in code.
- The API README says "20 tests"; there are 96.

**Documents**

- `docs/DESIGN.md`, `docs/ARCHITECTURE.md` and `docs/FACILITATORS.md` describe the original plan (Telegram worker bot, Redis streams router, a different facilitator package layout) and are superseded by the code and by this guide.
