from typing import Tuple, Literal, NamedTuple
from abis.univ2_lp import UNIV2_LP_ABI
from abis.erc20 import ERC20_ABI
from constants import (
    ETH_LP_ADDRESS,
    ETH_USDC_ADDRESS,
    ETH_ZERC_ADDRESS,
    POL_LP_ADDRESS,
    POL_USDC_ADDRESS,
    POL_ZERC_ADDRESS,
    ChainType,
)


class PoolReservesRaw(NamedTuple):
    usdc_reserves: int
    zerc_reserves: int


class PoolReservesFormatted(NamedTuple):
    usdc_reserves: float
    zerc_reserves: float


class PoolReserves(NamedTuple):
    raw: PoolReservesRaw
    formatted: PoolReservesFormatted


async def get_pool_reserves(w3, pool_address: str, chain: ChainType) -> PoolReserves:
    pool_contract = w3.eth.contract(address=pool_address, abi=UNIV2_LP_ABI)

    # Get token addresses for this pool
    token0_address = pool_contract.functions.token0().call().lower()
    token1_address = pool_contract.functions.token1().call().lower()

    # Determine USDC and ZERC addresses based on the chain
    if chain == "eth":
        usdc_address = ETH_USDC_ADDRESS.lower()
        zerc_address = ETH_ZERC_ADDRESS.lower()
    elif chain == "pol":
        usdc_address = POL_USDC_ADDRESS.lower()
        zerc_address = POL_ZERC_ADDRESS.lower()
    else:
        raise ValueError(f"Unsupported chain: {chain}")

    # Validate that the pool contains both USDC and ZERC
    pool_tokens = {token0_address, token1_address}
    required_tokens = {usdc_address, zerc_address}

    if not required_tokens.issubset(pool_tokens):
        missing_tokens = required_tokens - pool_tokens
        missing_names = []
        if usdc_address in missing_tokens:
            missing_names.append("USDC")
        if zerc_address in missing_tokens:
            missing_names.append("ZERC")
        raise ValueError(
            f"Pool {pool_address} on {chain} chain is missing required tokens: {', '.join(missing_names)}"
        )

    # Call getReserves function
    reserves = pool_contract.functions.getReserves().call()

    # Map the reserves to the correct tokens based on token order
    if token0_address == usdc_address:
        usdc_raw = reserves[0]
        zerc_raw = reserves[1]
    else:
        usdc_raw = reserves[1]
        zerc_raw = reserves[0]

    # Get token decimals
    usdc_contract = w3.eth.contract(address=usdc_address, abi=ERC20_ABI)
    zerc_contract = w3.eth.contract(address=zerc_address, abi=ERC20_ABI)

    usdc_decimals = usdc_contract.functions.decimals().call()
    zerc_decimals = zerc_contract.functions.decimals().call()

    # Format values with proper decimals
    usdc_formatted = usdc_raw / (10**usdc_decimals)
    zerc_formatted = zerc_raw / (10**zerc_decimals)

    raw_reserves = PoolReservesRaw(usdc_reserves=usdc_raw, zerc_reserves=zerc_raw)
    formatted_reserves = PoolReservesFormatted(
        usdc_reserves=usdc_formatted, zerc_reserves=zerc_formatted
    )

    return PoolReserves(raw=raw_reserves, formatted=formatted_reserves)
