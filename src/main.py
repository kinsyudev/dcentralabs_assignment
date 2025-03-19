import math
import asyncio
import logging
from typing import Literal, TypedDict, Union, NamedTuple, Tuple
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

        # Calculate expected outputs
        def calculate_amount_out(
            amount_in: float, reserve_in: float, reserve_out: float
        ) -> float:
            # Formula for constant product AMM (Uniswap V2)
            numerator: float = amount_in * reserve_out
            denominator: float = reserve_in + amount_in
            return numerator / denominator

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

        # Use the formatted values for arbitrage calculation
        logger.info("Calculating arbitrage with formatted reserve values")
        result = calculate_arbitrage(
            eth_reserves.formatted.usdc_reserves,
            eth_reserves.formatted.zerc_reserves,
            # pol_reserves.formatted.usdc_reserves,
            100000,
            pol_reserves.formatted.zerc_reserves,
        )

        # Return the required values in the specified order
        return (
            result["usdc_in"],
            result["zerc_bridged"],
            result["usdc_out"],
            result["profit"],
        )
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
