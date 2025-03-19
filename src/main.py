import math
from typing import Literal, TypedDict, Union
from web3 import Web3
from constants import ETH_RPC, POL_RPC
from utils import get_web3_for_rpc

eth_w3 = get_web3_for_rpc(ETH_RPC)
pol_w3 = get_web3_for_rpc(POL_RPC)

print("Connected to both RPCs")


class ArbitrageResult(TypedDict):
    usdc_in: float
    zerc_bridged: float
    usdc_out: float
    profit: float
    direction: Union[Literal["eth_to_pol"], Literal["pol_to_eth"]]


def calculate_arbitrage(
    eth_usdc_balance: float,
    eth_zerc_balance: float,
    pol_usdc_balance: float,
    pol_zerc_balance: float,
) -> ArbitrageResult:
    # Calculate current prices in each pool (USDC per ZERC)
    eth_price: float = eth_usdc_balance / eth_zerc_balance
    pol_price: float = pol_usdc_balance / pol_zerc_balance

    # Initialize variables
    result: ArbitrageResult = {
        "usdc_in": 0.0,
        "zerc_bridged": 0.0,
        "usdc_out": 0.0,
        "profit": 0.0,
        "direction": "",
    }

    # Determine direction of arbitrage
    if eth_price < pol_price:
        # Buy ZERC on Ethereum, sell on Polygon
        direction: Literal["eth_to_pol"] = "eth_to_pol"
        source_usdc: float = eth_usdc_balance
        source_zerc: float = eth_zerc_balance
        target_usdc: float = pol_usdc_balance
        target_zerc: float = pol_zerc_balance
    else:
        # Buy ZERC on Polygon, sell on Ethereum
        direction: Literal["pol_to_eth"] = "pol_to_eth"
        source_usdc: float = pol_usdc_balance
        source_zerc: float = pol_zerc_balance
        target_usdc: float = eth_usdc_balance
        target_zerc: float = eth_zerc_balance

    # Calculate optimal USDC input for maximum profit
    # This formula is derived by taking the derivative of the profit function
    # with respect to the input amount and setting it to zero
    r: float = math.sqrt((source_usdc * target_usdc * target_zerc) / source_zerc)
    optimal_usdc_in: float = r - source_usdc

    # If optimal amount is negative or zero, no profitable arbitrage exists
    if optimal_usdc_in <= 0:
        return result

    # Calculate ZERC received from source pool (accounting for 0.3% fee)
    # For a Uniswap V2 swap, the formula is:
    # amount_out = (reserve_out * amount_in * 997) / (reserve_in * 1000 + amount_in * 997)
    zerc_received: float = (source_zerc * optimal_usdc_in * 997) / (
        source_usdc * 1000 + optimal_usdc_in * 997
    )

    # Calculate USDC received from target pool (accounting for 0.3% fee)
    usdc_received: float = (target_usdc * zerc_received * 997) / (
        target_zerc * 1000 + zerc_received * 997
    )

    # Calculate profit
    profit: float = usdc_received - optimal_usdc_in

    # Only return a result if arbitrage is profitable
    if profit <= 0:
        return result

    # Return results with the specified format
    result = {
        "usdc_in": optimal_usdc_in,
        "zerc_bridged": zerc_received,
        "usdc_out": usdc_received,
        "profit": profit,
        "direction": direction,
    }

    return result


import math
import asyncio
from typing import Literal, TypedDict, Union, NamedTuple, Tuple
from web3 import Web3

from constants import ETH_RPC, POL_RPC, ETH_LP_ADDRESS, POL_LP_ADDRESS, ChainType
from utils import get_web3_for_rpc
from lib.lp import get_pool_reserves

# Initialize Web3 instances
eth_w3 = get_web3_for_rpc(ETH_RPC)
pol_w3 = get_web3_for_rpc(POL_RPC)
print("Connected to both RPCs")


class ArbitrageResult(TypedDict):
    usdc_in: float
    zerc_bridged: float
    usdc_out: float
    profit: float
    direction: Union[Literal["eth_to_pol"], Literal["pol_to_eth"]]


def calculate_arbitrage(
    eth_usdc_balance: float,
    eth_zerc_balance: float,
    pol_usdc_balance: float,
    pol_zerc_balance: float,
) -> ArbitrageResult:
    # Calculate current prices in each pool (USDC per ZERC)
    eth_price: float = eth_usdc_balance / eth_zerc_balance
    pol_price: float = pol_usdc_balance / pol_zerc_balance

    # Initialize variables
    result: ArbitrageResult = {
        "usdc_in": 0.0,
        "zerc_bridged": 0.0,
        "usdc_out": 0.0,
        "profit": 0.0,
        "direction": "",
    }

    # Determine direction of arbitrage
    if eth_price < pol_price:
        # Buy ZERC on Ethereum, sell on Polygon
        direction: Literal["eth_to_pol"] = "eth_to_pol"
        source_usdc: float = eth_usdc_balance
        source_zerc: float = eth_zerc_balance
        target_usdc: float = pol_usdc_balance
        target_zerc: float = pol_zerc_balance
    else:
        # Buy ZERC on Polygon, sell on Ethereum
        direction: Literal["pol_to_eth"] = "pol_to_eth"
        source_usdc: float = pol_usdc_balance
        source_zerc: float = pol_zerc_balance
        target_usdc: float = eth_usdc_balance
        target_zerc: float = eth_zerc_balance

    # Calculate optimal USDC input for maximum profit
    # This formula is derived by taking the derivative of the profit function
    # with respect to the input amount and setting it to zero
    r: float = math.sqrt((source_usdc * target_usdc * target_zerc) / source_zerc)
    optimal_usdc_in: float = r - source_usdc

    # If optimal amount is negative or zero, no profitable arbitrage exists
    if optimal_usdc_in <= 0:
        return result

    # Calculate ZERC received from source pool (accounting for 0.3% fee)
    # For a Uniswap V2 swap, the formula is:
    # amount_out = (reserve_out * amount_in * 997) / (reserve_in * 1000 + amount_in * 997)
    zerc_received: float = (source_zerc * optimal_usdc_in * 997) / (
        source_usdc * 1000 + optimal_usdc_in * 997
    )

    # Calculate USDC received from target pool (accounting for 0.3% fee)
    usdc_received: float = (target_usdc * zerc_received * 997) / (
        target_zerc * 1000 + zerc_received * 997
    )

    # Calculate profit
    profit: float = usdc_received - optimal_usdc_in

    # Only return a result if arbitrage is profitable
    if profit <= 0:
        return result

    # Return results with the specified format
    result = {
        "usdc_in": optimal_usdc_in,
        "zerc_bridged": zerc_received,
        "usdc_out": usdc_received,
        "profit": profit,
        "direction": direction,
    }

    return result


async def find_optimal_arbitrage() -> Tuple[float, float, float, float]:

    # Get pool reserves from both chains
    eth_reserves = await get_pool_reserves(eth_w3, ETH_LP_ADDRESS, "eth")
    pol_reserves = await get_pool_reserves(pol_w3, POL_LP_ADDRESS, "pol")

    # Use the formatted values for arbitrage calculation
    result = calculate_arbitrage(
        eth_reserves.formatted.usdc_reserves,
        eth_reserves.formatted.zerc_reserves,
        pol_reserves.formatted.usdc_reserves,
        pol_reserves.formatted.zerc_reserves,
    )

    # Return the required values in the specified order
    return (
        result["usdc_in"],
        result["zerc_bridged"],
        result["usdc_out"],
        result["profit"],
    )


# Example of running the script
async def main():
    try:
        optimal_arb = await find_optimal_arbitrage()
        print(f"USDC In: {optimal_arb[0]:.2f}")
        print(f"ZERC Bridged: {optimal_arb[1]:.2f}")
        print(f"USDC Out: {optimal_arb[2]:.2f}")
        print(f"Profit: {optimal_arb[3]:.2f} USDC")
    except Exception as e:
        print(f"Error calculating arbitrage: {e}")


if __name__ == "__main__":
    asyncio.run(main())
