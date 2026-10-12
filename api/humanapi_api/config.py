"""Settings, prefixed HA_ (H402 API)."""

from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROBINHOOD_MAINNET = "eip155:4663"
ROBINHOOD_TESTNET = "eip155:46630"
SOLANA_MAINNET = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"
SOLANA_DEVNET = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
USDG_ROBINHOOD_MAINNET = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
USDC_SOLANA_MAINNET = "EPjFWdd5AufqSSqeM4qv9bL4dqAfv7PF9Vm7GdWRLd3f"

EXPLORER_TX = {
    ROBINHOOD_MAINNET: "https://robinhoodchain.blockscout.com/tx/{tx}",
    ROBINHOOD_TESTNET: "https://explorer.testnet.chain.robinhood.com/tx/{tx}",
    SOLANA_MAINNET: "https://solscan.io/tx/{tx}",
    SOLANA_DEVNET: "https://solscan.io/tx/{tx}?cluster=devnet",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HA_", env_file=".env", extra="ignore")

    env: str = "local"  # local | testnet | mainnet
    host: str = "0.0.0.0"
    port: int = 8400
    log_level: str = "INFO"
    public_base_url: str = "http://127.0.0.1:8400"
    database_url: str = "sqlite:///./humanapi.db"

    facilitator_url: str = "http://127.0.0.1:8402"
    facilitator_settle_token: str = ""
    facilitator_timeout_seconds: float = 120.0

    platform_fee_bps: int = 2000  # DECISIONS B: 20%
    min_reward: int = 1_000_000  # no task pays a person less than this (1.00)
    quote_ttl_seconds: int = 300
    max_timeout_seconds: int = 300  # validity window offered to payers
    batch_max: int = 100
    idempotency_ttl_seconds: int = 86400
    webhook_max_attempts: int = 8

    # Local only: answers tasks automatically so the money path can be tested without workers.
    echo_worker: bool = False
    jobs_enabled: bool = True
    # Local only: POST /v1/workers/dev-session signs a worker in without a wallet signature.
    dev_login: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3123,http://127.0.0.1:3123"
    session_ttl_seconds: int = 30 * 86400
    nonce_ttl_seconds: int = 600
    claim_hold_seconds: int = 900  # a quick task is yours for 15 minutes once taken
    online_window_seconds: int = 600
    public_cache_seconds: float = 10.0  # the public board, numbers and activity are cached this long
    feed_limit: int = 30
    # True: every response, of every type, waits for the operator's approval before anyone is paid: consensus tasks are
    # not decided by agreement alone, written proofs are not accepted by the clock, and the verifier only advises.
    operator_decides_all: bool = False
    # The site's translations: made once through the AI gateway and kept. The cap bounds new translations per day.
    translate_daily_cap: int = 5000
    translate_model: str = ""  # empty: the verifier's default model
    # True: a worker must pass each type's practice questions before taking paid tasks of that type.
    # False: every worker may take every type of work; the practice questions stay available but unlock nothing.
    qualification_required: bool = True

    # House poster: the platform posts tasks itself from its own funded pool. People only solve them.
    house_poster_enabled: bool = False
    house_interval_seconds: int = 300  # a new batch every five minutes
    house_batch_size: int = 3
    house_pictures_per_batch: int = 1  # at most this many photo or screenshot tasks per batch; the operator checks each picture by hand
    house_list_seconds: int = 7 * 86400  # a platform task stays on the board for a week; the poster relists it after
    house_max_open: int = 240  # keep at most this many house tasks open at once
    house_daily_budget: int = 2_000_000_000  # 2000.00 per rail per day
    house_rail: str = "robinhood"

    # Scouts: each model proposes tasks through the Vercel AI Gateway; approved ones are posted from the house pool.
    scouts_enabled: bool = False
    ai_gateway_api_key: str = ""
    ai_gateway_base_url: str = "https://ai-gateway.vercel.sh/v1"
    scout_models: str = "claude=anthropic/claude-haiku-5.5,chatgpt=openai/gpt-5.4-mini,gemini=google/gemini-3.8-flash,grok=spacexai/grok-4.1-fast-non-reasoning,deepseek=deepseek/deepseek-v4-flash"
    scout_interval_seconds: int = 900
    scout_proposals_per_run: int = 3
    scout_auto_post: bool = False  # False: proposals wait for an operator
    scout_daily_calls: int = 200  # gateway calls per day, all models together

    # Verifier: an assistant reviews action-task proofs and written answers. It can approve; it never refuses payment.
    verifier_enabled: bool = False
    # A written proof the client has not accepted or disputed is accepted by the clock after this long (seconds).
    # With the verifier on it is normally decided within seconds; this is the fallback when the review fails.
    do_accept_window_seconds: int = 3600
    verifier_vision_model: str = "google/gemini-3.8-flash"  # used when the proof includes a photo or screenshot
    verifier_default_model: str = "anthropic/claude-haiku-5.5"
    second_worker_every: int = 5  # one in N platform action tasks gets a second, independent worker

    # On-chain escrow (Robinhood rail): when set, payments land in the TaskEscrow contract and every task is
    # opened and settled there. HA_ROBINHOOD_ESCROW_ADDRESS must be the contract's address.
    escrow_contract: str = ""
    escrow_operator_private_key: str = ""
    # How the platform's own tasks pay: "wallet" sends each reward from the operator wallet when the worker claims it;
    # "contract" locks the reward in the TaskEscrow contract when the task is taken and settles there.
    house_payout: str = "wallet"
    wallet_payout_daily_cap: int = 300_000_000  # at most this much leaves the operator wallet in rewards per day (300.00)
    escrow_lock_on_claim: bool = True  # platform tasks are listed first; the contract locks the money when someone takes one
    escrow_house_payer: str = ""  # where unearned money from platform-posted tasks returns; default: the operator wallet

    # Proof photos
    redis_url: str = ""  # where photo bytes are kept; empty = memory (local only)
    photo_max_bytes: int = 6_000_000
    photo_max_per_answer: int = 3
    geo_radius_m: int = 300  # a go-and-see photo must be taken within this distance of the task's place

    # The gate: refuse tasks a chatbot can do alone
    gate_enabled: bool = False
    gate_model: str = "openai/gpt-5.4-mini"

    # Phase 4
    admin_token: str = ""  # bearer for /v1/admin/*; empty disables the admin surface
    admin_user: str = "admin"  # the id for the /admin page
    admin_password: str = ""  # the password for the /admin page; empty means the admin token itself is the password
    moderation_url: str = ""  # optional external classifier: POST {type, payload} -> {"decision": allow|review|reject, "reason"}
    moderation_block_after: int = 2  # rejections before a buyer is blocked
    gold_every: int = 20  # one gold task per N real answers per worker
    gold_wrong_pause: int = 3  # wrong gold answers in a day pauses the worker
    abuse_flags_pause: int = 3  # abuse flags in a day pauses the worker
    dispute_window_seconds: int = 86400
    retention_days: int = 30

    # Payouts and refunds: sent from the escrow wallet of each rail. The address must match
    # HA_*_ESCROW_ADDRESS. Without a key, rows stay queued (phase 2 behaviour).
    payouts_enabled: bool = False
    payout_interval_seconds: int = 600
    payout_min_amount: int = 100_000  # 0.10
    payout_round_cap: int = 2_000_000_000  # 2000 per round per rail
    robinhood_escrow_private_key: str = ""
    solana_escrow_private_key: str = ""

    robinhood_enabled: bool = False
    robinhood_network: str = ROBINHOOD_TESTNET
    robinhood_asset: str = ""  # token address; USDG on mainnet by default
    robinhood_escrow_address: str = ""  # payTo: where settlements land
    robinhood_rpc_url: str = ""  # optional, for escrow balance reconciliation

    solana_enabled: bool = False
    solana_network: str = SOLANA_DEVNET
    solana_asset: str = ""  # mint; USDC on mainnet by default
    solana_escrow_address: str = ""  # owner wallet of the escrow token account
    solana_rpc_url: str = ""

    @field_validator("env")
    @classmethod
    def _env(cls, v: str) -> str:
        if v not in {"local", "testnet", "mainnet"}:
            raise ValueError("HA_ENV must be local, testnet or mainnet")
        return v

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.robinhood_enabled:
            if not self.robinhood_asset and self.robinhood_network == ROBINHOOD_MAINNET:
                self.robinhood_asset = USDG_ROBINHOOD_MAINNET
            if not self.robinhood_asset or not self.robinhood_escrow_address:
                raise ValueError("HA_ROBINHOOD_ASSET and HA_ROBINHOOD_ESCROW_ADDRESS are required")
        if self.solana_enabled:
            if not self.solana_asset and self.solana_network == SOLANA_MAINNET:
                self.solana_asset = USDC_SOLANA_MAINNET
            if not self.solana_asset or not self.solana_escrow_address:
                raise ValueError("HA_SOLANA_ASSET and HA_SOLANA_ESCROW_ADDRESS are required")
        if self.env != "local" and (self.echo_worker or self.dev_login):
            raise ValueError("the echo worker and dev login are local only")
        if self.payouts_enabled:
            if self.robinhood_enabled and not self.robinhood_escrow_private_key:
                raise ValueError("HA_ROBINHOOD_ESCROW_PRIVATE_KEY is required for payouts")
            if self.solana_enabled and not self.solana_escrow_private_key:
                raise ValueError("HA_SOLANA_ESCROW_PRIVATE_KEY is required for payouts")
        if self.escrow_contract:
            if not self.escrow_operator_private_key:
                raise ValueError("HA_ESCROW_OPERATOR_PRIVATE_KEY is required with HA_ESCROW_CONTRACT")
            if self.robinhood_escrow_address.lower() != self.escrow_contract.lower():
                raise ValueError("HA_ROBINHOOD_ESCROW_ADDRESS must equal HA_ESCROW_CONTRACT so payments land in the contract")
        if not (0 <= self.platform_fee_bps < 10000):
            raise ValueError("HA_PLATFORM_FEE_BPS must be between 0 and 9999")
        return self

    def rails(self) -> list[dict]:
        out = []
        if self.robinhood_enabled:
            out.append({"name": "robinhood", "network": self.robinhood_network, "asset": self.robinhood_asset, "pay_to": self.robinhood_escrow_address, "rpc_url": self.robinhood_rpc_url})
        if self.solana_enabled:
            out.append({"name": "solana", "network": self.solana_network, "asset": self.solana_asset, "pay_to": self.solana_escrow_address, "rpc_url": self.solana_rpc_url})
        return out
