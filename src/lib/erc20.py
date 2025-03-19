from typing import TypedDict
from abis.erc20 import ERC20_ABI


class TokenMetadata(TypedDict):
    address: str
    name: str
    symbol: str
    decimals: int


async def get_erc20_metadata(w3, token_address: str) -> TokenMetadata:
    # Create contract instance
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

    # Get token metadata
    try:
        decimals = token_contract.functions.decimals().call()
    except Exception:
        decimals = 18  # Default to 18 if decimals method fails

    try:
        symbol = token_contract.functions.symbol().call()
    except Exception:
        symbol = "UNKNOWN"  # Default if symbol method fails

    try:
        name = token_contract.functions.name().call()
    except Exception:
        name = "UnUNKNOWN"  # Default if name method fails

    return {
        "address": token_address,
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
    }
