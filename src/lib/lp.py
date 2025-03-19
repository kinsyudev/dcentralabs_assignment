from typing import Tuple
from abis.univ2_lp import UNIV2_LP_ABI


async def get_pool_reserves(w3, pool_address: str) -> Tuple[int, int]:
    pool_contract = w3.eth.contract(address=pool_address, abi=UNIV2_LP_ABI)

    # Call getReserves function
    reserves = pool_contract.functions.getReserves().call()

    # Return the reserves
    return (reserves[0], reserves[1])
