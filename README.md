# H402

**AI agents pay humans per task, over HTTP.** An agent calls one endpoint, gets a `402 Payment Required` with a price, pays with [x402](https://x402.org), and a person does the task and is paid the moment the answer is accepted.

Live at [h402.io](https://h402.io). Payments settle in USDG on Robinhood Chain (chain id 4663) and in USDC on Solana, through an escrow contract and an x402 facilitator.

## The repositories

| Repository | What it holds |
| --- | --- |
| **useh402/h402** (this one) | `web/`, the website (Next.js 16, React 19, Tailwind 4, Privy). `api/`, the task service (Python 3.12, FastAPI, SQLAlchemy 2, Alembic): 402 quotes, escrow, workers, consensus, payouts, operator tools. `deploy/` and `docker-compose.yml` to run and ship all three services. `docs/`, the guide and the design |
| [useh402/facilitator](https://github.com/useh402/facilitator) | The x402 facilitator: verifies and settles USDG payments on Robinhood Chain (Permit2 route) and USDC payments on Solana. The only process that holds a settlement key |
| [useh402/Contract](https://github.com/useh402/Contract) | `TaskEscrow.sol`, the contract on Robinhood Chain mainnet that holds each task's reward and can only pay the workers, the fee and the payer. Source matches the verified address `0x530C2beDB048a658cB9fFD074eB7A75D68bfBd90` |

## Documents

| Document | What it holds |
| --- | --- |
| [docs/GUIDE.md](docs/GUIDE.md) | **The complete guide.** The website page by page, how a task goes from posting to payment, workers, clients and the API, the escrow contract, the operator tools, settings, running and deploying, policies and known gaps |
| [docs/DESIGN.md](docs/DESIGN.md) | The product design in tables: task types, protocol, money, quality, abuse controls, data model, architecture, economics, risks |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The backend in phases: processes, stack, exit criteria |
| [docs/FACILITATORS.md](docs/FACILITATORS.md) | The facilitator specification: flows per chain, API, keys, tests |
| [docs/DOCKER.md](docs/DOCKER.md) | Running everything with Docker Compose |

## Run it locally

```bash
# task service
cd api && uv sync --extra dev && cp .env.example .env && uv run humanapi-api      # http://127.0.0.1:8400
# website
cd web && pnpm install && pnpm dev                                                # http://localhost:3000
# everything, including the facilitator image from its own repository
cp api/env.docker.example api/.env.docker && cp env.facilitator.example .env.facilitator
docker compose up --build -d
```

Tests: `cd api && uv run pytest`, `cd web && pnpm lint && pnpm build`.

## Secrets

None are in this repository. Every setting is an environment variable; the `*.example` files list them all with placeholders. `.env*`, databases and logs are ignored by git, and a `gitleaks` check runs on every push. See [SECURITY.md](SECURITY.md) to report a problem.

## Contributing

Clone, then `scripts/install-hooks.sh` once. Pull requests run lint, tests and the secret scan. Commit messages carry no tool attribution lines; the hook and CI both enforce that.
