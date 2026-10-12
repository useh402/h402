# Work item 1: the x402 facilitators

**Status:** Built on 2026-10-09 on top of the official x402 Python SDK. The service lives in its own repository, github.com/useh402/facilitator; see its README.
**Deliverable:** one Python service that is an x402 facilitator for two rails, USDG on Robinhood Chain and USDC on Solana, with tests on test networks and a demo of the full 402 round trip on each.

## 1. What a facilitator is

In x402 the resource server (H402's task API) never touches keys or chains itself. It hands the client's payment to a facilitator over HTTP:

| Facilitator endpoint | Does |
| --- | --- |
| `GET /supported` | Lists the `(scheme, network)` pairs this facilitator handles, with any extra data (for example the Permit2 proxy address) |
| `POST /verify` | Takes `paymentPayload` and `paymentRequirements`; checks the signature, amount, recipient, validity window, balance and replay; answers `{ isValid, invalidReason, payer }` without touching the chain's state |
| `POST /settle` | Takes the same; submits the transfer on-chain, waits for confirmation, answers `{ success, transaction, network, payer, errorReason }` |

Everything in this document must be checked against the current x402 specification before coding. Field names and payload shapes come from the spec, not from this file.

## 2. The two rails

| | Robinhood Chain | Solana |
| --- | --- | --- |
| Network id in x402 | The CAIP-2 style id for chain 4663 (confirm the exact string the spec uses; register it if the spec's list lacks it) | `solana` mainnet and `solana-devnet` |
| Asset | USDG `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168`, 6 decimals | USDC mint `EPjFWdd5AufqSSqeM4qv9bL4dqAfv7PF9Vm7GdWRLd3f`, 6 decimals; devnet uses the devnet USDC mint |
| Scheme | `exact`, Permit2 route, because USDG does not implement EIP-3009 `transferWithAuthorization` | `exact`, SVM route |
| What the client signs | A Permit2 `PermitTransferFrom` (EIP-712) authorizing the x402 Permit2 proxy to pull exactly `amount` USDG to the pay-to address, with a nonce and a deadline | A transaction that transfers exactly `amount` USDC from the payer's token account to the pay-to token account, with the facilitator's key as fee payer, signed by the payer only |
| One-time setup for a payer | An ERC-20 `approve` of USDG to the Permit2 contract (the payer pays this gas once) | None (the payer needs a USDC token account) |
| Who pays gas | The facilitator, when it submits the proxy transaction | The facilitator, as fee payer |
| Settlement | Facilitator calls the proxy with the permit and signature; the proxy pulls USDG to the pay-to address | Facilitator adds its signature and sends the transaction |
| Finality to wait for | Receipt confirmed by 3 blocks, then return the hash | `confirmed` commitment for `/settle`, `finalized` for anything that releases value to a third party |
| Explorer | https://robin.etherscan.io | https://solscan.io |
| Test network | Robinhood Chain testnet 46630, RPC `https://rpc.testnet.chain.robinhood.com`; needs a testnet USDG or a test token with the same shape | Solana devnet with the devnet USDC faucet |

## 3. Verify, in detail

| Check | Robinhood Chain | Solana |
| --- | --- | --- |
| Scheme and network match the requirement | yes | yes |
| Signature valid for the claimed payer | Recover the EIP-712 signer of the Permit2 message; must equal `from` | The transaction carries a valid signature from the payer for the message |
| Exact amount and asset | Permit `permitted.token` is USDG and `permitted.amount` equals `maxAmountRequired`; the transfer details name the pay-to address and the same amount | The only token instruction is a `TransferChecked` of exactly the amount, of the USDC mint, to the pay-to token account |
| Nothing else in the transaction | n/a (the facilitator builds the transaction) | No other instructions except compute-budget ones; fee payer is the facilitator; no instruction touches the facilitator's accounts |
| Validity window | Permit `deadline` is in the future and not farther than the requirement's `maxTimeoutSeconds` | Recent blockhash still valid, or a durable nonce the facilitator accepts |
| Balance and allowance | Payer's USDG balance at or above the amount; payer's allowance to Permit2 at or above the amount | Payer's USDC token account balance at or above the amount |
| Replay | The Permit2 nonce is unused on-chain and unseen in our store | The transaction signature is unseen in our store; the blockhash has not expired |
| Simulation | `eth_call` of the proxy call must succeed | `simulateTransaction` must succeed |

## 4. Settle, in detail

| Step | Robinhood Chain | Solana |
| --- | --- | --- |
| 1 | Run verify again on fresh state | Run verify again on fresh state |
| 2 | Record the intent in the replay store with status `sending` (nonce, payer, amount, requirement hash) | Record the intent with the transaction signature |
| 3 | Build the proxy call, estimate gas, sign with the facilitator key, send | Add the facilitator's fee-payer signature, send with `skipPreflight=false` |
| 4 | Wait for the receipt (3 confirmations); on success store the hash and mark `settled` | Confirm at `confirmed`; store the signature and mark `settled` |
| 5 | On a revert or timeout: mark `failed` with the reason; a timeout with a sent transaction is `uncertain` and is resolved later by looking the hash up | On failure: mark `failed`; an expired blockhash means it never landed |
| 6 | Return `{ success, transaction: hash, network, payer }` | Return `{ success, transaction: signature, network, payer }` |

A settlement that is asked for twice with the same authorization returns the first result. The replay store is Postgres (or SQLite for local runs), never memory only.

## 5. HTTP service

| Item | Decision |
| --- | --- |
| Framework | FastAPI with uvicorn |
| Endpoints | `GET /supported`, `POST /verify`, `POST /settle`, `GET /health` (chain reachability per rail, signer balances, pending settlements) |
| Auth | Optional bearer token for `/settle` so only our own task API can trigger spending of gas; `/verify` and `/supported` can be public |
| Config | Environment: RPC URLs per rail, facilitator private keys per rail (managed secrets, never logged), Permit2 and proxy addresses, USDG and USDC addresses, confirmation depths, database URL |
| Logging | Structured JSON: every verify and settle with payer, amount, requirement hash, outcome, latency; never a signature or a key |
| Limits | Rate limit per client; max amount per settlement as a safety cap; a daily gas budget per rail with an alert |

## 6. Code layout

```text
facilitators/
  pyproject.toml           uv or poetry; Python 3.12
  common/
    types.py               PaymentRequirements, PaymentPayload, VerifyResponse, SettleResponse (pydantic), kept in step with the x402 spec
    store.py               replay store: nonces, signatures, settlement records, statuses
    app.py                 FastAPI app, routing to the rail by (scheme, network)
    config.py              environment loading, validation at start
  robinhood/
    chain.py               web3 client, USDG, Permit2, proxy addresses, confirmation policy
    permit2.py             EIP-712 typed data for PermitTransferFrom, signer recovery
    verify.py / settle.py
  solana/
    chain.py               RPC client, USDC mint, ATA derivation, commitment policy
    transaction.py         decode, validate instructions, co-sign
    verify.py / settle.py
  demo/
    server.py              a paywalled resource that uses the facilitator, one route per rail
    client_robinhood.py    signs a Permit2 payment and completes the round trip
    client_solana.py       builds and signs the SVM payment and completes the round trip
  tests/
    test_types.py          payload parsing against spec examples
    test_robinhood.py      verify and settle on testnet 46630 (opt-in with env)
    test_solana.py         verify and settle on devnet (opt-in with env)
    test_replay.py         double settle is a no-op; concurrent settles act once
```

## 7. What is needed before coding

| Need | Detail |
| --- | --- |
| The x402 spec files | Clone the x402 repository and read the `exact` scheme for EVM (including the Permit2 variant), the SVM scheme, and the facilitator API; pin the version in REFERENCES.md |
| Permit2 proxy on 4663 | Find the canonical x402 Permit2 proxy address for Robinhood Chain and confirm it on the explorer |
| Test funds | Testnet 46630: native gas and a USDG-shaped test token; Solana devnet: SOL from the faucet and devnet USDC |
| Wallets | A facilitator key per rail for tests (new keys, never reused from other projects); mainnet keys only when the acceptance review passes |
| RPCs | Public endpoints for tests; a dedicated provider for mainnet later |
| Python | 3.12, `uv` for environments |

## 8. Acceptance criteria

| # | Criterion |
| --- | --- |
| 1 | `GET /supported` lists both rails |
| 2 | On each rail, the demo client gets a 402, pays, and receives the resource; the settlement hash or signature is visible on the explorer |
| 3 | A payment with the wrong amount, wrong recipient, expired window, insufficient balance, or a reused nonce or signature is rejected by `/verify` with the right reason |
| 4 | Calling `/settle` twice with the same payment settles once |
| 5 | A crash between send and confirmation is recovered: on restart the pending settlement is looked up on-chain and marked correctly |
| 6 | Keys never appear in logs or responses; the health endpoint shows signer balances |
| 7 | Tests pass locally; the opt-in testnet tests pass with funded keys |
| 8 | A run guide lets someone start the service with Docker and the environment file |

## 9. Open questions for this work item

| Question | Options |
| --- | --- |
| Testnet USDG | Does testnet 46630 have USDG? If not, deploy a 6-decimal test token and point the config at it |
| Durable nonces on Solana | Support them in v1 (payments valid longer than a blockhash) or only recent blockhashes |
| Network id for 4663 | Use the spec's CAIP-2 form; propose it upstream if missing |
| Public facilitator | Expose the service to other builders as a product (open) |
