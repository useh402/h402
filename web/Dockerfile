# HumanAPI website
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# These are public values compiled into the pages, so they are set when the image is built.
ARG NEXT_PUBLIC_API_URL=http://localhost:8400
ARG NEXT_PUBLIC_ROBINHOOD_NETWORK=eip155:4663
ARG NEXT_PUBLIC_PRIVY_APP_ID=
ARG NEXT_PUBLIC_DEV_LOGIN=0
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_ROBINHOOD_NETWORK=$NEXT_PUBLIC_ROBINHOOD_NETWORK \
    NEXT_PUBLIC_PRIVY_APP_ID=$NEXT_PUBLIC_PRIVY_APP_ID NEXT_PUBLIC_DEV_LOGIN=$NEXT_PUBLIC_DEV_LOGIN NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD wget -qO- http://127.0.0.1:${PORT}/ >/dev/null || exit 1
CMD ["node", "server.js"]
