"""Chain senders for payouts: one ERC-20 transfer per recipient on Robinhood Chain, several SPL
transfers per transaction on Solana. Keys never leave this module."""

from __future__ import annotations

import base64

ERC20_ABI = [
    {"type": "function", "name": "transfer", "stateMutability": "nonpayable", "inputs": [{"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}], "outputs": [{"type": "bool"}]},
    {"type": "function", "name": "balanceOf", "stateMutability": "view", "inputs": [{"name": "a", "type": "address"}], "outputs": [{"type": "uint256"}]},
]


class EvmSender:
    rail = "robinhood"

    def __init__(self, rpc_url: str, private_key: str, token: str, confirmations: int = 2):
        from eth_account import Account
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware

        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = Account.from_key(private_key)
        self.token = self.w3.eth.contract(address=Web3.to_checksum_address(token), abi=ERC20_ABI)
        self.confirmations = confirmations

    @property
    def address(self) -> str:
        return self.account.address

    def max_per_tx(self) -> int:
        return 1

    def prepare(self, transfers):
        from web3 import Web3

        (to, amount), = transfers
        tx = self.token.functions.transfer(Web3.to_checksum_address(to), int(amount)).build_transaction(
            {"from": self.account.address, "nonce": self.w3.eth.get_transaction_count(self.account.address, "pending"), "chainId": self.w3.eth.chain_id, "gasPrice": self.w3.eth.gas_price}
        )
        tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.3)
        signed = self.account.sign_transaction(tx)
        return signed.hash.hex() if signed.hash.hex().startswith("0x") else "0x" + signed.hash.hex(), signed.raw_transaction

    def broadcast(self, prepared) -> None:
        self.w3.eth.send_raw_transaction(prepared)

    def status(self, tx: str) -> str:
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx)
        except Exception:
            return "unknown"
        if receipt is None:
            return "unknown"
        if int(receipt["status"]) != 1:
            return "failed"
        return "sent" if self.w3.eth.block_number >= int(receipt["blockNumber"]) + self.confirmations - 1 else "unknown"

    def balance(self) -> int:
        return int(self.token.functions.balanceOf(self.account.address).call())


class SolanaSender:
    rail = "solana"

    def __init__(self, rpc_url: str, private_key: str, mint: str):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from solana.rpc.api import Client
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey

        self.client = Client(rpc_url, timeout=30)
        self.keypair = Keypair.from_base58_string(private_key)
        self.mint = Pubkey.from_string(mint)
        self._decimals: int | None = None

    @property
    def address(self) -> str:
        return str(self.keypair.pubkey())

    def max_per_tx(self) -> int:
        return 8

    def decimals(self) -> int:
        if self._decimals is None:
            from spl.token.client import Token
            from spl.token.constants import TOKEN_PROGRAM_ID

            self._decimals = Token(self.client, self.mint, TOKEN_PROGRAM_ID, self.keypair).get_mint_info().decimals
        return self._decimals

    def prepare(self, transfers):
        from solders.message import MessageV0
        from solders.pubkey import Pubkey
        from solders.transaction import VersionedTransaction
        from spl.token.constants import TOKEN_PROGRAM_ID
        from spl.token.instructions import (
            TransferCheckedParams,
            create_associated_token_account,
            get_associated_token_address,
            transfer_checked,
        )

        owner = self.keypair.pubkey()
        source = get_associated_token_address(owner, self.mint)
        ixs = []
        for to, amount in transfers:
            dest_owner = Pubkey.from_string(to)
            dest = get_associated_token_address(dest_owner, self.mint)
            if self.client.get_account_info(dest).value is None:
                ixs.append(create_associated_token_account(owner, dest_owner, self.mint))
            ixs.append(transfer_checked(TransferCheckedParams(program_id=TOKEN_PROGRAM_ID, source=source, mint=self.mint, dest=dest, owner=owner, amount=int(amount), decimals=self.decimals())))
        blockhash = self.client.get_latest_blockhash().value.blockhash
        msg = MessageV0.try_compile(owner, ixs, [], blockhash)
        tx = VersionedTransaction(msg, [self.keypair])
        return str(tx.signatures[0]), base64.b64encode(bytes(tx)).decode()

    def broadcast(self, prepared) -> None:
        from solana.rpc.types import TxOpts

        self.client.send_raw_transaction(base64.b64decode(prepared), opts=TxOpts(skip_preflight=False))

    def status(self, tx: str) -> str:
        from solders.signature import Signature

        res = self.client.get_signature_statuses([Signature.from_string(tx)], search_transaction_history=True)
        st = res.value[0] if res.value else None
        if st is None:
            return "unknown"
        if st.err is not None:
            return "failed"
        return "sent" if st.confirmation_status is not None else "unknown"

    def balance(self) -> int:
        from spl.token.instructions import get_associated_token_address

        ata = get_associated_token_address(self.keypair.pubkey(), self.mint)
        return int(self.client.get_token_account_balance(ata).value.amount)


def build_senders(settings) -> dict:
    senders = {}
    if not settings.payouts_enabled:
        return senders
    for rail in settings.rails():
        if rail["name"] == "robinhood":
            s = EvmSender(rail["rpc_url"] or _default_rpc(rail["network"]), settings.robinhood_escrow_private_key, rail["asset"])
        else:
            s = SolanaSender(rail["rpc_url"] or _default_rpc(rail["network"]), settings.solana_escrow_private_key, rail["asset"])
        if s.address.lower() != rail["pay_to"].lower():
            raise ValueError(f"{rail['name']}: the escrow key does not match HA_*_ESCROW_ADDRESS ({s.address} vs {rail['pay_to']})")
        senders[rail["name"]] = s
    return senders


def _default_rpc(network: str) -> str:
    return {
        "eip155:4663": "https://rpc.mainnet.chain.robinhood.com",
        "eip155:46630": "https://rpc.testnet.chain.robinhood.com",
        "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp": "https://api.mainnet-beta.solana.com",
        "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1": "https://api.devnet.solana.com",
    }[network]
