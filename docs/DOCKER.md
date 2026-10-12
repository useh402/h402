# Running H402 with Docker

Three images, one compose file. The website and the task service are built here; the facilitator image comes from its own repository.

| Service | Image built from | Port | Health check |
| --- | --- | --- | --- |
| Website | `web/Dockerfile` | 3000 | `/` |
| Task service | `api/Dockerfile` | 8400 | `/v1/stats` |
| Facilitator | `ghcr.io/useh402/facilitator` (built in [useh402/facilitator](https://github.com/useh402/facilitator)) | 8402 | `/health` |

All three run as a non-root user. The task service creates or upgrades its database tables on every start.

## First run

```
cp api/env.docker.example api/.env.docker
cp env.facilitator.example .env.facilitator
# fill both in, then:
docker compose up --build -d
docker compose ps
```

`HA_FACILITATOR_SETTLE_TOKEN` in the first file must equal `HF_SETTLE_TOKEN` in the second.

## Settings

- **Secrets** live in `api/.env.docker` and `.env.facilitator`. Both are ignored by git.
- **Compose settings** live in a root `.env` file, also ignored:

| Name | Default | Meaning |
| --- | --- | --- |
| `WEB_PORT`, `API_PORT`, `FACILITATOR_PORT` | 3000, 8400, 8402 | Ports on this machine |
| `PUBLIC_API_URL` | `http://localhost:8400` | Where browsers reach the task service. Compiled into the website, so changing it needs a rebuild |
| `WEB_ORIGIN` | `http://localhost:3000` | The website's address, allowed to call the task service |
| `PRIVY_APP_ID` | empty | Wallet connection. Empty falls back to the browser wallet directly |
| `ROBINHOOD_NETWORK` | `eip155:4663` | Chain the website signs in on |

The website's origin must also be on the allowed list in the Privy dashboard.

## Database

Point `HA_DATABASE_URL` at a hosted Postgres, or run one locally:

```
docker compose --profile localdb up -d
# HA_DATABASE_URL=postgresql+psycopg://humanapi:humanapi@postgres:5432/humanapi
```

The facilitator keeps its own small database in the `facilitator-data` volume. It records which payments were settled, so keep that volume.

## Everyday commands

```
docker compose logs -f api          # follow one service
docker compose restart api
docker compose up --build -d web    # rebuild after a website change
docker compose down                 # stop; volumes are kept
```

## Hosting

Each image runs on its own on any container host. Hosts that pass the port as `PORT` (Render, for example) are supported: the task service and the facilitator listen on `PORT` when it is set. Build the website image with `NEXT_PUBLIC_API_URL` set to the public address of the task service.

Run exactly one copy of the task service. It sends the contract's transactions, and two copies would compete for the same wallet.
