"""Sign in with a wallet. The wallet proves ownership by signing a server nonce; it is also the payout address."""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Nonce, Worker, WorkerSession, new_id, now
from .tasks import ApiError


def rail_of(network: str, settings: Settings) -> str:
    for r in settings.rails():
        if r["network"] == network:
            return r["name"]
    raise ApiError(400, "unsupported_network", f"{network} is not a supported rail")


def normalize_wallet(rail: str, wallet: str) -> str:
    wallet = wallet.strip()
    if rail == "robinhood":
        from eth_utils import is_address, to_checksum_address

        if not is_address(wallet):
            raise ApiError(400, "invalid_wallet", "not an EVM address")
        return to_checksum_address(wallet)
    from solders.pubkey import Pubkey

    try:
        return str(Pubkey.from_string(wallet))
    except Exception as e:
        raise ApiError(400, "invalid_wallet", "not a Solana address") from e


def build_message(wallet: str, network: str, nonce: str) -> str:
    issued = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "H402 wants you to sign in with your wallet.\n\n"
        f"Wallet: {wallet}\nNetwork: {network}\nNonce: {nonce}\nIssued: {issued}\n\n"
        "This signature proves you own this wallet. It costs nothing and sends nothing."
    )


def issue_nonce(session: Session, settings: Settings, wallet: str, network: str) -> dict:
    rail = rail_of(network, settings)
    wallet = normalize_wallet(rail, wallet)
    nonce = secrets.token_hex(16)
    message = build_message(wallet, network, nonce)
    session.add(Nonce(nonce=nonce, wallet=wallet, network=network, message=message, expires_at=now() + settings.nonce_ttl_seconds))
    return {"nonce": nonce, "message": message, "wallet": wallet, "network": network, "expiresAt": int(now() + settings.nonce_ttl_seconds)}


def verify_signature(rail: str, wallet: str, message: str, signature: str) -> bool:
    if rail == "robinhood":
        from eth_account import Account
        from eth_account.messages import encode_defunct

        try:
            recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        except Exception:
            return False
        return recovered.lower() == wallet.lower()
    import base58
    from solders.pubkey import Pubkey
    from solders.signature import Signature

    try:
        raw = base58.b58decode(signature) if not signature.startswith("0x") else bytes.fromhex(signature[2:])
        sig = Signature.from_bytes(raw)
        return sig.verify(Pubkey.from_string(wallet), message.encode())
    except Exception:
        return False


def create_session(session: Session, settings: Settings, wallet: str, network: str, nonce: str, signature: str) -> dict:
    rail = rail_of(network, settings)
    wallet = normalize_wallet(rail, wallet)
    row = session.get(Nonce, nonce)
    if row is None or row.expires_at < now() or row.wallet != wallet or row.network != network:
        raise ApiError(401, "bad_nonce", "unknown or expired nonce; request a new one")
    if not verify_signature(rail, wallet, row.message, signature):
        raise ApiError(401, "bad_signature", "the signature does not match this wallet")
    session.delete(row)
    return _session_for(session, settings, rail, wallet)


def dev_session(session: Session, settings: Settings, wallet: str, network: str) -> dict:
    if not (settings.env == "local" and settings.dev_login):
        raise ApiError(404, "not_found", "not found")
    rail = rail_of(network, settings)
    return _session_for(session, settings, rail, normalize_wallet(rail, wallet))


def _session_for(session: Session, settings: Settings, rail: str, wallet: str) -> dict:
    handle = f"{rail}:{wallet}"
    worker = session.scalars(select(Worker).where(Worker.handle == handle)).first()
    if worker is None:
        worker = Worker(id=new_id("wk"), handle=handle, rail=rail, wallet=wallet, reputation=1.0, tier="new")
        session.add(worker)
        session.flush()
    token = "wks_" + secrets.token_urlsafe(32)
    session.add(WorkerSession(token=token, worker_id=worker.id, expires_at=now() + settings.session_ttl_seconds))
    worker.last_seen = now()
    return {"token": token, "expiresAt": int(now() + settings.session_ttl_seconds), "worker": worker_view(worker)}


def create_client_session(session: Session, settings: Settings, wallet: str, network: str, nonce: str, signature: str) -> dict:
    rail = rail_of(network, settings)
    wallet = normalize_wallet(rail, wallet)
    row = session.get(Nonce, nonce)
    if row is None or row.expires_at < now() or row.wallet != wallet or row.network != network:
        raise ApiError(401, "bad_nonce", "unknown or expired nonce; request a new one")
    if not verify_signature(rail, wallet, row.message, signature):
        raise ApiError(401, "bad_signature", "the signature does not match this wallet")
    session.delete(row)
    return _client_session_for(session, settings, rail, wallet)


def dev_client_session(session: Session, settings: Settings, wallet: str, network: str) -> dict:
    if not (settings.env == "local" and settings.dev_login):
        raise ApiError(404, "not_found", "not found")
    rail = rail_of(network, settings)
    return _client_session_for(session, settings, rail, normalize_wallet(rail, wallet))


def _client_session_for(session: Session, settings: Settings, rail: str, wallet: str) -> dict:
    from .models import ClientSession
    from .tasks import get_or_create_buyer

    buyer = get_or_create_buyer(session, rail, wallet)
    token = "cls_" + secrets.token_urlsafe(32)
    session.add(ClientSession(token=token, buyer_id=buyer.id, expires_at=now() + settings.session_ttl_seconds))
    return {"token": token, "expiresAt": int(now() + settings.session_ttl_seconds), "client": client_view(buyer, wallet)}


def authenticate_client(session: Session, token: str | None):
    from .models import Buyer, ClientSession

    if not token:
        raise ApiError(401, "unauthorized", "sign in first")
    row = session.get(ClientSession, token)
    if row is None or row.revoked or row.expires_at < now():
        raise ApiError(401, "unauthorized", "session expired; sign in again")
    buyer = session.get(Buyer, row.buyer_id)
    if buyer is None:
        raise ApiError(401, "unauthorized", "unknown client")
    return buyer


def client_view(buyer, wallet: str | None = None) -> dict:
    return {"id": buyer.id, "rail": buyer.rail, "wallet": wallet or buyer.payer, "name": buyer.name, "tasksPaid": buyer.tasks_paid, "blocked": buyer.blocked, "createdAt": int(buyer.created_at)}


def authenticate(session: Session, token: str | None) -> Worker:
    if not token:
        raise ApiError(401, "unauthorized", "sign in first")
    row = session.get(WorkerSession, token)
    if row is None or row.revoked or row.expires_at < now():
        raise ApiError(401, "unauthorized", "session expired; sign in again")
    worker = session.get(Worker, row.worker_id)
    if worker is None:
        raise ApiError(401, "unauthorized", "unknown worker")
    if worker.paused:
        raise ApiError(403, "paused", f"this worker is paused: {worker.paused_reason or 'contact support'}")
    return worker


def worker_view(w: Worker, settings: Settings | None = None) -> dict:
    # With the qualification gate off, every worker is shown as qualified for every type of work.
    from .pricing import TASK_TYPES

    qualified = list(TASK_TYPES) if settings is not None and not settings.qualification_required else (w.qualified_types or [])
    return {
        "id": w.id,
        "rail": w.rail,
        "wallet": w.wallet,
        "reputation": round(w.reputation, 3),
        "tier": w.tier,
        "languages": w.languages or [],
        "qualifiedTypes": qualified,
        "termsAccepted": bool(w.terms_accepted_at),
        "answered": w.answered,
        "agreed": w.agreed,
        "paused": w.paused,
        "pausedReason": w.paused_reason,
        "location": w.location or "",
        "createdAt": int(w.created_at),
    }


def cleanup(session: Session) -> None:
    for n in session.scalars(select(Nonce).where(Nonce.expires_at < time.time())).all():
        session.delete(n)
