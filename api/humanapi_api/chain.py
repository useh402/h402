"""Optional read-only escrow balance lookups for reconciliation. Imports chain libraries lazily."""

from __future__ import annotations

ERC20_BALANCE_ABI = [{"type": "function", "name": "balanceOf", "stateMutability": "view", "inputs": [{"name": "a", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]}]


def escrow_balance(rail: dict) -> int | None:
    if not rail.get("rpc_url"):
        return None
    if rail["name"] == "robinhood":
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider(rail["rpc_url"], request_kwargs={"timeout": 15}))
        token = w3.eth.contract(address=Web3.to_checksum_address(rail["asset"]), abi=ERC20_BALANCE_ABI)
        return int(token.functions.balanceOf(Web3.to_checksum_address(rail["pay_to"])).call())
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from solana.rpc.api import Client
    from solders.pubkey import Pubkey
    from spl.token.instructions import get_associated_token_address

    client = Client(rail["rpc_url"], timeout=15)
    ata = get_associated_token_address(Pubkey.from_string(rail["pay_to"]), Pubkey.from_string(rail["asset"]))
    resp = client.get_token_account_balance(ata)
    return int(resp.value.amount)
