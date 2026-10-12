"""Settling tasks through the TaskEscrow contract.

The chain is the source of truth for where a task stands: before acting we read the task's status on the
contract, so a crash or a repeated run can never open or pay a task twice (the contract refuses both).

  not on chain  -> open(taskId, payer, amount)        the money is already in the contract
  open + finished here -> settle(...) or refund(...)   workers paid, fee set aside, the rest back to the payer
"""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy import select

from . import ledger
from .config import Settings
from .models import LedgerEntry, Payment, Payout, Refund, Task, Worker, now

logger = logging.getLogger("humanapi.api.escrow")

TERMINAL = ("done", "expired", "rejected", "cancelled", "disputed")
NONE, OPEN, SETTLED, REFUNDED = 0, 1, 2, 3

ABI = [
    {"type": "function", "name": "tasks", "stateMutability": "view", "inputs": [{"type": "bytes32"}], "outputs": [{"name": "payer", "type": "address"}, {"name": "amount", "type": "uint96"}, {"name": "openedAt", "type": "uint40"}, {"name": "status", "type": "uint8"}]},
    {"type": "function", "name": "unallocated", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "allocated", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "feesAccrued", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "open", "stateMutability": "nonpayable", "inputs": [{"type": "bytes32"}, {"type": "address"}, {"type": "uint256"}], "outputs": []},
    {"type": "function", "name": "settle", "stateMutability": "nonpayable", "inputs": [{"type": "bytes32"}, {"type": "address[]"}, {"type": "uint256[]"}, {"type": "uint256"}], "outputs": []},
    {"type": "function", "name": "refund", "stateMutability": "nonpayable", "inputs": [{"type": "bytes32"}], "outputs": []},
]
ERC20 = [
    {"type": "function", "name": "transfer", "stateMutability": "nonpayable", "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}]},
    {"type": "function", "name": "balanceOf", "stateMutability": "view", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]},
]


class Chain(Protocol):
    address: str  # the operator wallet

    def status(self, task_id: str) -> int: ...
    def unallocated(self) -> int: ...
    def available(self) -> int: ...
    def fund(self, amount: int) -> str: ...
    def open(self, task_id: str, payer: str, amount: int) -> str: ...
    def settle(self, task_id: str, workers: list[str], amounts: list[int], fee: int) -> str: ...
    def refund(self, task_id: str) -> str: ...
    def info(self) -> dict: ...


class Web3Chain:
    def __init__(self, rpc_url: str, contract: str, token: str, private_key: str):
        from eth_account import Account
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware

        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.contract = self.w3.eth.contract(address=Web3.to_checksum_address(contract), abi=ABI)
        self.token = self.w3.eth.contract(address=Web3.to_checksum_address(token), abi=ERC20)
        self._cs = Web3.to_checksum_address
        self._key = lambda task_id: Web3.keccak(text=task_id)

    def _send(self, fn) -> str:
        tx = fn.build_transaction({"from": self.address, "nonce": self.w3.eth.get_transaction_count(self.address, "pending"), "chainId": self.w3.eth.chain_id})
        tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.3)  # a call the contract would refuse fails here, before any gas is spent
        h = self.w3.eth.send_raw_transaction(self.account.sign_transaction(tx).raw_transaction)
        rc = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if int(rc["status"]) != 1:
            raise RuntimeError(f"transaction {h.hex()} reverted")
        return "0x" + h.hex().removeprefix("0x")

    def status(self, task_id: str) -> int:
        return int(self.contract.functions.tasks(self._key(task_id)).call()[3])

    def unallocated(self) -> int:
        return int(self.contract.functions.unallocated().call())

    def available(self) -> int:
        """What can be locked for new tasks right now: free money in the contract plus the operator wallet."""
        return self.unallocated() + int(self.token.functions.balanceOf(self.address).call())

    def fund(self, amount: int) -> str:
        if int(self.token.functions.balanceOf(self.address).call()) < amount:
            raise RuntimeError("the operator wallet does not hold enough to fund this task")
        return self._send(self.token.functions.transfer(self.contract.address, amount))

    def open(self, task_id: str, payer: str, amount: int) -> str:
        return self._send(self.contract.functions.open(self._key(task_id), self._cs(payer), amount))

    def settle(self, task_id: str, workers: list[str], amounts: list[int], fee: int) -> str:
        return self._send(self.contract.functions.settle(self._key(task_id), [self._cs(w) for w in workers], amounts, fee))

    def refund(self, task_id: str) -> str:
        return self._send(self.contract.functions.refund(self._key(task_id)))

    def info(self) -> dict:
        return {"contract": self.contract.address, "operator": self.address, "balance": int(self.token.functions.balanceOf(self.contract.address).call()), "allocated": int(self.contract.functions.allocated().call()), "feesAccrued": int(self.contract.functions.feesAccrued().call()), "operatorGasWei": int(self.w3.eth.get_balance(self.address))}


def build(settings: Settings) -> Web3Chain | None:
    if not settings.escrow_contract:
        return None
    rail = next(r for r in settings.rails() if r["name"] == "robinhood")
    rpc = rail["rpc_url"] or {"eip155:4663": "https://rpc.mainnet.chain.robinhood.com", "eip155:46630": "https://rpc.testnet.chain.robinhood.com"}[rail["network"]]
    return Web3Chain(rpc, settings.escrow_contract, rail["asset"], settings.escrow_operator_private_key)


def chain_ref(t: Task) -> str:
    """The string the contract key is made from: the task id, plus a round number once the task has been released and
    listed again (the contract never reopens a refunded key)."""
    return t.id if not t.chain_round else f"{t.id}#{t.chain_round}"


def _plan(session, settings: Settings, chain: Chain, t: Task) -> dict:
    payment = session.get(Payment, t.payment_id)
    house = payment.payer == "house"
    plan = {"id": t.id, "ref": chain_ref(t), "state": t.state, "chain_state": t.chain_state, "house": house, "payer": (settings.escrow_house_payer or chain.address) if house else payment.payer, "amount": t.price_per_worker * t.workers_wanted + t.fee, "workers": {}, "fee": 0, "blocked": None}
    if t.state in TERMINAL:
        for e in session.scalars(select(LedgerEntry).where(LedgerEntry.debit == f"task:{t.id}")).all():
            if e.credit.startswith("worker_due:"):
                w = session.get(Worker, e.credit.split(":", 1)[1])
                if w is None or not w.wallet.startswith("0x"):
                    plan["blocked"] = "a worker has no wallet on this chain"
                    continue
                plan["workers"][w.wallet] = plan["workers"].get(w.wallet, 0) + e.amount
            elif e.credit == "platform_fee":
                plan["fee"] += e.amount
    return plan


_last_pool_sync = 0.0


def sync_pool(db, settings: Settings, chain: Chain, min_interval: float = 60.0, sender=None) -> int:
    """Keeps the pool's books in line with the money actually behind it: the operator wallet's free USDG plus what
    the contract holds unallocated. Sending USDG to the operator wallet is all it takes to fund the pool."""
    import time as _t

    global _last_pool_sync
    if _t.time() - _last_pool_sync < min_interval:
        return 0
    _last_pool_sync = _t.time()
    from .house import HOUSE, deposit

    try:
        available = sender.balance() if (settings.house_payout == "wallet" and sender is not None) else chain.available()
    except Exception as e:
        logger.warning("pool sync: chain unreachable: %s", str(e)[:120])
        return 0
    with db.session() as s:
        # Tasks the books have funded but the contract has not locked yet still draw on the same money.
        committed = sum(t.price_per_worker * t.workers_wanted + t.fee for t in s.scalars(select(Task).where(Task.chain_state == "pending")).all())
        books = ledger.balance(s, settings.house_rail, HOUSE)
        target = available - committed
        gap = target - books
        if gap >= 1_000_000:
            deposit(s, settings.house_rail, gap, "wallet:sync", "USDG found in the operator wallet")
            logger.info("pool sync: books raised by %s to match the wallet", gap)
            return gap
        if gap <= -1_000_000:
            logger.warning("pool sync: books exceed the wallet by %s; new takes will stop at the wallet's real balance", -gap)
    return 0


def release_abandoned(db, settings: Settings, chain: Chain, grace: float = 60.0, limit: int = 5) -> int:
    """A task that was taken, locked on the contract, then dropped before any answer goes back to being listed:
    the contract refunds it and the money returns to the pool, instead of staying locked until the deadline."""
    from .models import Answer, Claim

    # Mark first, so nobody takes the task while its lock is being undone; the take path refuses "releasing".
    picked: list[tuple[str, int, str]] = []
    with db.session() as s:
        rows = s.scalars(select(Task).where(Task.chain_state == "open", Task.state == "open", Task.updated_at <= now() - grace).order_by(Task.updated_at).limit(limit * 4)).all()
        for t in rows:
            live = any(c.expires_at > now() for c in s.scalars(select(Claim).where(Claim.task_id == t.id, Claim.released.is_(False))).all())
            if live or s.query(Answer).filter(Answer.task_id == t.id).count():
                continue
            payment = s.get(Payment, t.payment_id)
            if payment is None or payment.payer != "house":
                continue  # a client's task keeps its money where the client put it
            t.chain_state = "releasing"
            picked.append((t.id, chain_ref(t), t.price_per_worker * t.workers_wanted + t.fee, payment.id))
            if len(picked) >= limit:
                break
    released = 0
    for task_id, ref, total, payment_id in picked:
        tx = None
        try:
            if chain.status(ref) == OPEN:
                tx = chain.refund(ref)
        except Exception as e:
            logger.error("release of %s failed: %s", task_id, str(e)[:300])
            with db.session() as s:
                s.get(Task, task_id).chain_state = "open"
            continue
        with db.session() as s:
            t = s.get(Task, task_id)
            t.chain_state = "listed"
            t.chain_round = (t.chain_round or 0) + 1  # the next take locks under a fresh contract key
            t.chain_open_tx, t.chain_close_tx = None, None
            ledger.post(s, t.rail, f"task:{t.id}", "house", total, task_id=t.id, payment_id=payment_id, memo=f"dropped before any answer; back to the pool {tx or ''}".strip()[:200])
        released += 1
        logger.info("task %s released: dropped before any answer, %s back to the pool (%s)", task_id, total, tx)
    return released


def sync(db, settings: Settings, chain: Chain, limit: int = 5, sender=None) -> dict:
    out = {"opened": 0, "settled": 0, "refunded": 0, "waiting": 0, "failed": 0}
    out["poolRaised"] = sync_pool(db, settings, chain, sender=sender)
    out["released"] = release_abandoned(db, settings, chain)
    with db.session() as s:
        rows = s.scalars(select(Task).where(Task.chain_state.in_(("pending", "open"))).order_by(Task.created_at).limit(limit * 6)).all()
        awaiting = {p.task_id for p in s.scalars(select(Payout).where(Payout.task_id.in_([t.id for t in rows]), Payout.status == "claimable")).all()} if rows else set()
        plans = [_plan(s, settings, chain, t) for t in rows if t.chain_state == "pending" or (t.state in TERMINAL and t.id not in awaiting)][:limit]
        # Listed tasks that ended before anyone took them never touched the contract.
        for t in s.scalars(select(Task).where(Task.chain_state == "listed", Task.state.in_(TERMINAL))).all():
            t.chain_state = None
    for p in plans:
        try:
            on_chain = chain.status(p["ref"])
            if on_chain == NONE:
                short = p["amount"] - chain.unallocated()
                if short > 0:
                    if not p["house"]:
                        out["waiting"] += 1  # the payment has not reached the contract yet
                        continue
                    chain.fund(short)
                tx = chain.open(p["ref"], p["payer"], p["amount"])
                _write(db, p["id"], "open", open_tx=tx)
                out["opened"] += 1
            elif on_chain == OPEN:
                if p["chain_state"] == "pending":
                    _write(db, p["id"], "open")
                if p["state"] not in TERMINAL:
                    continue
                if p["blocked"]:
                    logger.warning("task %s not settled: %s", p["id"], p["blocked"])
                    out["waiting"] += 1
                    continue
                if p["workers"] or p["fee"]:
                    tx = chain.settle(p["ref"], list(p["workers"]), list(p["workers"].values()), p["fee"])
                    out["settled"] += 1
                else:
                    tx = chain.refund(p["ref"])
                    out["refunded"] += 1
                _close(db, p["id"], tx)
            else:
                _close(db, p["id"], None)  # already closed on chain: bring our records in line
        except Exception as e:
            out["failed"] += 1
            logger.error("escrow sync for %s failed: %s", p["id"], str(e)[:300])
    return out


def _write(db, task_id: str, state: str, open_tx: str | None = None) -> None:
    with db.session() as s:
        t = s.get(Task, task_id)
        t.chain_state = state
        if open_tx:
            t.chain_open_tx = open_tx


def _close(db, task_id: str, tx: str | None) -> None:
    with db.session() as s:
        t = s.get(Task, task_id)
        t.chain_state = "closed"
        t.chain_close_tx = tx or t.chain_close_tx
        ref = tx or "settled on chain"
        for po in s.scalars(select(Payout).where(Payout.task_id == t.id, Payout.kind == "task", Payout.status == "queued")).all():
            po.status, po.batch_ref, po.sent_at = "sent", ref, now()
            ledger.post(s, t.rail, f"worker_due:{po.worker_id}", "escrow", po.amount, task_id=t.id, memo=f"paid by the contract {ref}")
        for rf in s.scalars(select(Refund).where(Refund.task_id == t.id, Refund.kind == "task", Refund.status == "queued")).all():
            rf.status, rf.transaction, rf.sent_at = "sent", ref, now()
            ledger.post(s, t.rail, f"refund_due:{rf.payer}", "escrow", rf.amount, task_id=t.id, memo=f"refunded by the contract {ref}")


def settle_one(db, settings: Settings, chain: Chain, task_id: str) -> str:
    """Settles one finished task on the contract now (the Claim button). Returns the transaction."""
    with db.session() as s:
        t = s.get(Task, task_id)
        if t is None or t.state not in TERMINAL or t.chain_state not in ("pending", "open"):
            raise ValueError("this task is not waiting for settlement")
        p = _plan(s, settings, chain, t)
    if p["blocked"]:
        raise ValueError(p["blocked"])
    ref = p["ref"]
    on_chain = chain.status(ref)
    if on_chain == NONE:
        if chain.unallocated() < p["amount"]:
            if not p["house"]:
                raise ValueError("the payment has not reached the contract yet")
            chain.fund(p["amount"] - chain.unallocated())
        _write(db, task_id, "open", open_tx=chain.open(ref, p["payer"], p["amount"]))
        on_chain = OPEN
    if on_chain == OPEN:
        tx = chain.settle(ref, list(p["workers"]), list(p["workers"].values()), p["fee"]) if (p["workers"] or p["fee"]) else chain.refund(ref)
        _close(db, task_id, tx)
        return tx
    _close(db, task_id, None)
    with db.session() as s:
        return s.get(Task, task_id).chain_close_tx or "settled on chain"
