import math
from web3 import Web3
from constants import ETH_RPC, POL_RPC
from utils import get_web3_for_rpc

eth_w3 = get_web3_for_rpc(ETH_RPC)
pol_w3 = get_web3_for_rpc(POL_RPC)

print("Connected to both RPCs")


def calc_arb_profit(
    eth_usdc_reserves: float,
    eth_zerc_reserves: float,
    pol_usdc_reserves: float,
    pol_zerc_reserves: float,
) -> dict:
    # Calculate current prices in each pool in X USDC per ZERC
    eth_price = eth_usdc_reserves / eth_zerc_reserves
    pol_price = pol_usdc_reserves / pol_zerc_reserves

    # Determine direction of arbitrage
    if eth_price < pol_price:
        # Buy ZERC on Ethereum, sell on Polygon
        source_usdc = eth_usdc_reserves
        source_zerc = eth_zerc_reserves
        target_usdc = pol_usdc_reserves
        target_zerc = pol_zerc_reserves
    else:
        # Buy ZERC on Polygon, sell on Ethereum
        source_usdc = pol_usdc_reserves
        source_zerc = pol_zerc_reserves
        target_usdc = eth_usdc_reserves
        target_zerc = eth_zerc_reserves

    # Calculate constant products for both pools
    k_source = source_usdc * source_zerc
    k_target = target_usdc * target_zerc

    # Calculate optimal input amount (USDC to buy ZERC in source pool)
    r = math.sqrt((source_usdc * target_usdc * target_zerc) / source_zerc)
    optimal_usdc_in = r - source_usdc

    # If optimal amount is negative or zero, no profitable arbitrage exists
    if optimal_usdc_in <= 0:
        return {"usdc_in": 0, "zerc_bridged": 0, "usdc_out": 0, "profit": 0}

    # Calculate how much ZERC we get from source pool
    new_source_usdc = source_usdc + optimal_usdc_in
    new_source_zerc = k_source / new_source_usdc
    zerc_received = source_zerc - new_source_zerc

    # Calculate how much USDC we get from target pool
    new_target_zerc = target_zerc + zerc_received
    new_target_usdc = k_target / new_target_zerc
    usdc_received = target_usdc - new_target_usdc

    # Calculate profit
    profit = usdc_received - optimal_usdc_in

    # Return results with the specified format
    return {
        "usdc_in": optimal_usdc_in,
        "zerc_bridged": zerc_received,
        "usdc_out": usdc_received,
        "profit": profit,
    }
