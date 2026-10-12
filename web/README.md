# H402 website

The public site at [h402.io](https://h402.io): landing, the Earn area for workers (tasks, qualification, earnings, rewards), the client and docs pages, and the operator and admin tools. Next.js 16, React 19, Tailwind 4, Framer Motion, Privy for wallet connection.

```bash
pnpm install
cp .env.example .env.local      # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_ROBINHOOD_NETWORK, NEXT_PUBLIC_PRIVY_APP_ID
pnpm dev                        # http://localhost:3000
pnpm lint && pnpm build
```

| Variable | Meaning |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Where the browser reaches the task service, for example `http://localhost:8400` |
| `NEXT_PUBLIC_ROBINHOOD_NETWORK` | `eip155:4663` on mainnet |
| `NEXT_PUBLIC_PRIVY_APP_ID` | Privy app id; empty falls back to the browser wallet |
| `NEXT_PUBLIC_DEV_LOGIN` | `1` enables the local sign-in shortcut; never set in production |

Docker: `docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t humanapi-web .`

How every page works is described in [../docs/GUIDE.md](../docs/GUIDE.md).
