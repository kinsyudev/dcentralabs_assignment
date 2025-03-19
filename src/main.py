import math
import asyncio
import logging
from typing import Literal, TypedDict, Union, NamedTuple, Tuple, List
from web3 import Web3

from constants import ETH_RPC, POL_RPC, ETH_LP_ADDRESS, POL_LP_ADDRESS, ChainType
from utils import get_web3_for_rpc
from lib.lp import get_pool_reserves

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("arbitrage")

# Initialize Web3 instances
eth_w3 = get_web3_for_rpc(ETH_RPC)
pol_w3 = get_web3_for_rpc(POL_RPC)
logger.info("Connected to both RPCs")


class ArbitrageResult(TypedDict):
    usdc_in: float
    zerc_bridged: float
    usdc_out: float
    profit: float
    direction: Union[Literal["eth_to_pol"], Literal["pol_to_eth"]]


# Calculate expected outputs
def calculate_amount_out(
    amount_in: float, reserve_in: float, reserve_out: float
) -> float:
    # Formula for constant product AMM (Uniswap V2)
    numerator: float = amount_in * reserve_out
    denominator: float = reserve_in + amount_in
    return numerator / denominator


def calculate_arbitrage(
    eth_usdc_balance: float,
    eth_zerc_balance: float,
    pol_usdc_balance: float,
    pol_zerc_balance: float,
) -> ArbitrageResult:
    logger.info(
        f"Calculating arbitrage with pool balances - ETH: {eth_usdc_balance:.2f} USDC / {eth_zerc_balance:.2f} ZERC, POL: {pol_usdc_balance:.2f} USDC / {pol_zerc_balance:.2f} ZERC"
    )

    # Calculate current prices in each pool (USDC per ZERC)
    eth_price: float = eth_usdc_balance / eth_zerc_balance
    pol_price: float = pol_usdc_balance / pol_zerc_balance
    logger.info(
        f"Current prices - ETH: {eth_price:.6f} USDC/ZERC, POL: {pol_price:.6f} USDC/ZERC"
    )

    # Initialize result
    result: ArbitrageResult = {
        "usdc_in": 0.0,
        "zerc_bridged": 0.0,
        "usdc_out": 0.0,
        "profit": 0.0,
        "direction": "",
    }

    # Skip if prices are identical (within rounding error)
    price_diff: float = abs(eth_price - pol_price)
    price_diff_pct: float = price_diff / min(eth_price, pol_price) * 100
    logger.info(f"Price difference: {price_diff_pct:.4f}%")

    if price_diff_pct < 0.001:  # If price difference is less than 0.001%
        logger.info("Price difference too small for profitable arbitrage")
        return result

    try:
        # Determine direction of arbitrage
        if eth_price < pol_price:
            # Buy ZERC on Ethereum, sell on Polygon
            direction: str = "eth_to_pol"
            source_usdc: float = eth_usdc_balance
            source_zerc: float = eth_zerc_balance
            target_usdc: float = pol_usdc_balance
            target_zerc: float = pol_zerc_balance
            logger.info(f"Arbitrage direction: ETH -> POL (Buy on ETH, sell on POL)")
        else:
            # Buy ZERC on Polygon, sell on Ethereum
            direction: str = "pol_to_eth"
            source_usdc: float = pol_usdc_balance
            source_zerc: float = pol_zerc_balance
            target_usdc: float = eth_usdc_balance
            target_zerc: float = eth_zerc_balance
            logger.info(f"Arbitrage direction: POL -> ETH (Buy on POL, sell on ETH)")

        # Calculate optimal input using the exact mathematical formula
        # Calculate price ratios
        source_ratio: float = source_usdc / source_zerc
        target_ratio: float = target_usdc / target_zerc

        # Calculate gamma coefficient (square root of price ratio)
        gamma: float = (target_ratio / source_ratio) ** 0.5

        # Calculate optimal input amount without any constraints
        optimal_usdc_in: float = source_usdc * (gamma - 1) / (1 + gamma)
        logger.info(
            f"Calculated optimal input using formula: {optimal_usdc_in:.2f} USDC"
        )

        # Calculate ZERC received from source pool
        zerc_out: float = calculate_amount_out(
            optimal_usdc_in, source_usdc, source_zerc
        )

        # Calculate USDC received from target pool
        usdc_out: float = calculate_amount_out(zerc_out, target_zerc, target_usdc)

        # Calculate profit
        profit: float = usdc_out - optimal_usdc_in

        # Calculate profit percentage
        profit_pct: float = (
            (profit / optimal_usdc_in) * 100 if optimal_usdc_in > 0 else 0
        )
        logger.info(f"Expected profit: {profit:.2f} USDC ({profit_pct:.4f}%)")

        # Validation - ensure final output is greater than input
        if profit <= 0:
            logger.info("No profitable arbitrage exists (profit <= 0)")
            return result

        # Calculate new pool states after arbitrage
        new_source_usdc: float = source_usdc + optimal_usdc_in
        new_source_zerc: float = source_zerc - zerc_out

        # Calculate new pool states after second swap
        new_target_usdc: float = target_usdc - usdc_out
        new_target_zerc: float = target_zerc + zerc_out

        # Calculate new prices
        new_source_price: float = new_source_usdc / new_source_zerc
        new_target_price: float = new_target_usdc / new_target_zerc

        logger.info(
            f"New prices after arbitrage - Source: {new_source_price:.6f}, Target: {new_target_price:.6f}"
        )
        new_price_diff_pct: float = (
            abs(new_source_price - new_target_price)
            / min(new_source_price, new_target_price)
            * 100
        )
        logger.info(f"New price difference: {new_price_diff_pct:.4f}%")

    except Exception as e:
        logger.error(f"Error calculating optimal input: {e}", exc_info=True)
        return result

    # Return results with the specified format
    result = {
        "usdc_in": optimal_usdc_in,
        "zerc_bridged": zerc_out,
        "usdc_out": usdc_out,
        "profit": profit,
        "direction": direction,
    }

    logger.info(f"Found profitable arbitrage: {profit:.2f} USDC profit")
    return result


def simulate_multi_round_arbitrage(
    eth_usdc_balance: float,
    eth_zerc_balance: float,
    pol_usdc_balance: float,
    pol_zerc_balance: float,
    max_rounds: int = 5,
    min_price_diff_pct: float = 0.1,
) -> List[ArbitrageResult]:
    """
    Simulate multiple rounds of arbitrage to extract maximum profit.

    Args:
        eth_usdc_balance: USDC balance in ETH pool
        eth_zerc_balance: ZERC balance in ETH pool
        pol_usdc_balance: USDC balance in POL pool
        pol_zerc_balance: ZERC balance in POL pool
        max_rounds: Maximum number of arbitrage rounds to perform
        min_price_diff_pct: Minimum price difference percentage to continue arbitrage

    Returns:
        List of ArbitrageResult for each round
    """
    results: List[ArbitrageResult] = []

    current_eth_usdc: float = eth_usdc_balance
    current_eth_zerc: float = eth_zerc_balance
    current_pol_usdc: float = pol_usdc_balance
    current_pol_zerc: float = pol_zerc_balance

    total_profit: float = 0.0

    logger.info(f"Starting multi-round arbitrage simulation (max {max_rounds} rounds)")

    for i in range(max_rounds):
        # Calculate current prices
        eth_price: float = current_eth_usdc / current_eth_zerc
        pol_price: float = current_pol_usdc / current_pol_zerc

        # Calculate price difference
        price_diff: float = abs(eth_price - pol_price)
        price_diff_pct: float = price_diff / min(eth_price, pol_price) * 100

        logger.info(f"Round {i+1} - Current price difference: {price_diff_pct:.4f}%")

        # Stop if price difference is below threshold
        if price_diff_pct < min_price_diff_pct:
            logger.info(
                f"Price difference below threshold ({min_price_diff_pct}%). Stopping."
            )
            break

        # Calculate arbitrage for current balances
        result = calculate_arbitrage(
            current_eth_usdc, current_eth_zerc, current_pol_usdc, current_pol_zerc
        )

        # If no profitable arbitrage found, stop
        if result["profit"] <= 0:
            logger.info("No more profitable arbitrage opportunities. Stopping.")
            break

        # Update pool balances based on the arbitrage
        if result["direction"] == "eth_to_pol":
            # Buy ZERC on Ethereum, sell on Polygon
            current_eth_usdc += result["usdc_in"]
            current_eth_zerc -= result["zerc_bridged"]
            current_pol_usdc -= result["usdc_out"]
            current_pol_zerc += result["zerc_bridged"]
        else:
            # Buy ZERC on Polygon, sell on Ethereum
            current_pol_usdc += result["usdc_in"]
            current_pol_zerc -= result["zerc_bridged"]
            current_eth_usdc -= result["usdc_out"]
            current_eth_zerc += result["zerc_bridged"]

        results.append(result)
        total_profit += result["profit"]

        # Log updated state
        logger.info(f"Round {i+1} - Profit: {result['profit']:.2f} USDC")
        logger.info(f"Round {i+1} - Cumulative profit: {total_profit:.2f} USDC")
        logger.info(
            f"Round {i+1} - New pool balances - ETH: {current_eth_usdc:.2f} USDC / {current_eth_zerc:.2f} ZERC, POL: {current_pol_usdc:.2f} USDC / {current_pol_zerc:.2f} ZERC"
        )
        logger.info(
            f"Round {i+1} - New prices - ETH: {current_eth_usdc/current_eth_zerc:.6f} USDC/ZERC, POL: {current_pol_usdc/current_pol_zerc:.6f} USDC/ZERC"
        )

    logger.info(f"Total profit across {len(results)} rounds: {total_profit:.2f} USDC")

    return results


async def find_optimal_arbitrage() -> Tuple[float, float, float, float]:
    logger.info("Starting optimal arbitrage calculation")

    try:
        # Get pool reserves from both chains
        logger.info(f"Fetching Ethereum pool reserves from {ETH_LP_ADDRESS}")
        eth_reserves = await get_pool_reserves(eth_w3, ETH_LP_ADDRESS, "eth")
        logger.info(
            f"Ethereum pool reserves: {eth_reserves.formatted.usdc_reserves:.2f} USDC, {eth_reserves.formatted.zerc_reserves:.6f} ZERC"
        )

        logger.info(f"Fetching Polygon pool reserves from {POL_LP_ADDRESS}")
        pol_reserves = await get_pool_reserves(pol_w3, POL_LP_ADDRESS, "pol")
        logger.info(
            f"Polygon pool reserves: {pol_reserves.formatted.usdc_reserves:.2f} USDC, {pol_reserves.formatted.zerc_reserves:.6f} ZERC"
        )

        # Use the formatted values for multi-round arbitrage calculation
        logger.info("Running multi-round arbitrage simulation")
        results = simulate_multi_round_arbitrage(
            eth_reserves.formatted.usdc_reserves,
            eth_reserves.formatted.zerc_reserves,
            # pol_reserves.formatted.usdc_reserves,
            100000,  # Using the same override as in the original code
            pol_reserves.formatted.zerc_reserves,
            max_rounds=10,  # Limit to 3 rounds for demonstration
            min_price_diff_pct=0.1,  # Continue until price difference is less than 1%
        )

        # Calculate total profit
        total_profit = sum(result["profit"] for result in results)

        # For compatibility with existing code, return the first round results
        if results:
            first_round = results[0]
            return (
                first_round["usdc_in"],
                first_round["zerc_bridged"],
                first_round["usdc_out"],
                first_round["profit"],
            )
        else:
            return (0.0, 0.0, 0.0, 0.0)
    except Exception as e:
        logger.error(f"Error in find_optimal_arbitrage: {e}", exc_info=True)
        raise


# Example of running the script
async def main():
    logger.info("Starting arbitrage calculation")
    try:
        optimal_arb = await find_optimal_arbitrage()
        logger.info("Arbitrage calculation completed successfully")
        logger.info(f"USDC In: {optimal_arb[0]:.2f}")
        logger.info(f"ZERC Bridged: {optimal_arb[1]:.6f}")
        logger.info(f"USDC Out: {optimal_arb[2]:.2f}")
        logger.info(f"Profit: {optimal_arb[3]:.2f} USDC")

        # Print summary for console
        print("\n===== ARBITRAGE SUMMARY =====")
        print(f"USDC In: {optimal_arb[0]:.2f}")
        print(f"ZERC Bridged: {optimal_arb[1]:.6f}")
        print(f"USDC Out: {optimal_arb[2]:.2f}")
        print(f"Profit: {optimal_arb[3]:.2f} USDC")
        print("=============================\n")

    except Exception as e:
        logger.error(f"Error calculating arbitrage: {e}", exc_info=True)
        print(f"Error calculating arbitrage: {e}")


if __name__ == "__main__":
    logger.info("Script execution started")
    asyncio.run(main())
    logger.info("Script execution completed")
