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
) -> dict:
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
    result = {
        "usdc_in": 0.0,
        "zerc_bridged": 0.0,
        "usdc_out": 0.0,
        "profit": 0.0,
        "direction": "",
    }

    # Skip if prices are identical (within rounding error)
    price_diff = abs(eth_price - pol_price)
    price_diff_pct = price_diff / min(eth_price, pol_price) * 100
    logger.info(f"Price difference: {price_diff_pct:.4f}%")

    if price_diff_pct < 0.001:  # If price difference is less than 0.001%
        logger.info("Price difference too small for profitable arbitrage")
        return result

    try:
        # Determine direction of arbitrage
        if eth_price < pol_price:
            # Buy ZERC on Ethereum, sell on Polygon
            direction = "eth_to_pol"
            source_usdc = eth_usdc_balance
            source_zerc = eth_zerc_balance
            target_usdc = pol_usdc_balance
            target_zerc = pol_zerc_balance
            logger.info(f"Arbitrage direction: ETH -> POL (Buy on ETH, sell on POL)")
        else:
            # Buy ZERC on Polygon, sell on Ethereum
            direction = "pol_to_eth"
            source_usdc = pol_usdc_balance
            source_zerc = pol_zerc_balance
            target_usdc = eth_usdc_balance
            target_zerc = eth_zerc_balance
            logger.info(f"Arbitrage direction: POL -> ETH (Buy on POL, sell on ETH)")

        # Calculate optimal input using improved mathematical formula
        # Calculate price ratios
        source_ratio = source_usdc / source_zerc
        target_ratio = target_usdc / target_zerc

        # Calculate gamma coefficient (square root of price ratio)
        gamma = (target_ratio / source_ratio) ** 0.5

        # Calculate optimal input amount
        optimal_usdc_in = source_usdc * (gamma - 1) / (1 + gamma)

        # Apply constraints to prevent unreasonable inputs
        max_usdc_in = min(source_usdc * 0.3, 10000000)  # Cap at 30% of pool or $10M
        optimal_usdc_in = min(optimal_usdc_in, max_usdc_in)
        optimal_usdc_in = max(
            optimal_usdc_in, 1.0
        )  # Ensure minimum input is at least 1 USDC

        logger.info(
            f"Calculated optimal input using formula: {optimal_usdc_in:.2f} USDC"
        )

        # Calculate expected outputs and profit
        def calculate_amount_out(amount_in, reserve_in, reserve_out):
            # Apply the 0.3% fee that Uniswap V2 applies
            amount_in_with_fee = amount_in * 0.997
            numerator = amount_in_with_fee * reserve_out
            denominator = reserve_in + amount_in_with_fee
            return numerator / denominator

        # Calculate ZERC received from source pool
        zerc_out = calculate_amount_out(optimal_usdc_in, source_usdc, source_zerc)

        # Calculate USDC received from target pool
        usdc_out = calculate_amount_out(zerc_out, target_zerc, target_usdc)

        # Calculate profit
        profit = usdc_out - optimal_usdc_in

        # Calculate profit percentage
        profit_pct = (profit / optimal_usdc_in) * 100 if optimal_usdc_in > 0 else 0
        logger.info(f"Expected profit: {profit:.2f} USDC ({profit_pct:.4f}%)")

        # Additional validation - ensure final output is indeed greater than input
        if usdc_out <= optimal_usdc_in:
            logger.warning(
                f"Validation failed: Output {usdc_out:.2f} <= Input {optimal_usdc_in:.2f}"
            )
            profit = 0

            # Try a fixed set of input values as fallback
            logger.info("Trying fallback approach with fixed inputs")
            max_profit = 0
            best_input = 0
            best_zerc = 0
            best_usdc_out = 0

            # Try a few different percentages of the source pool
            test_percentages = [0.05, 0.1, 0.15, 0.2, 0.25]
            for pct in test_percentages:
                test_input = source_usdc * pct
                test_zerc = calculate_amount_out(test_input, source_usdc, source_zerc)
                test_usdc_out = calculate_amount_out(
                    test_zerc, target_zerc, target_usdc
                )
                test_profit = test_usdc_out - test_input

                if test_profit > max_profit:
                    max_profit = test_profit
                    best_input = test_input
                    best_zerc = test_zerc
                    best_usdc_out = test_usdc_out

            if max_profit > 0:
                logger.info(
                    f"Fallback found profit of {max_profit:.2f} USDC with {best_input:.2f} USDC input"
                )
                optimal_usdc_in = best_input
                zerc_out = best_zerc
                usdc_out = best_usdc_out
                profit = max_profit
                profit_pct = (
                    (profit / optimal_usdc_in) * 100 if optimal_usdc_in > 0 else 0
                )
                logger.info(f"Updated profit percentage: {profit_pct:.4f}%")

        # Calculate new pool states after arbitrage
        if profit > 0:
            # Calculate new pool states after first swap
            new_source_usdc = source_usdc + optimal_usdc_in
            new_source_zerc = source_zerc - zerc_out

            # Calculate new pool states after second swap
            new_target_usdc = target_usdc - usdc_out
            new_target_zerc = target_zerc + zerc_out

            # Calculate new prices
            new_source_price = new_source_usdc / new_source_zerc
            new_target_price = new_target_usdc / new_target_zerc

            logger.info(
                f"New prices after arbitrage - Source: {new_source_price:.6f}, Target: {new_target_price:.6f}"
            )
            new_price_diff_pct = (
                abs(new_source_price - new_target_price)
                / min(new_source_price, new_target_price)
                * 100
            )
            logger.info(f"New price difference: {new_price_diff_pct:.4f}%")

    except Exception as e:
        logger.error(f"Error calculating optimal input: {e}", exc_info=True)
        return result

    # If no profitable amount was found, return empty result
    if profit <= 0:
        logger.info("No profitable arbitrage exists (profit <= 0)")
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
