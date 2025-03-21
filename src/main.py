import math
import asyncio
from typing import Literal, TypedDict, Union, NamedTuple, Tuple, List, Dict, Optional
from decimal import Decimal
from web3 import Web3

from constants import ETH_RPC, POL_RPC, ETH_LP_ADDRESS, POL_LP_ADDRESS, ChainType
from utils import get_web3_for_rpc
from lib.lp import get_pool_reserves

# Initialize Web3 instances
eth_w3 = get_web3_for_rpc(ETH_RPC)
pol_w3 = get_web3_for_rpc(POL_RPC)


class ArbitrageResult(TypedDict):
    usdc_in: float
    zerc_bridged: float
    usdc_out: float
    profit: float
    direction: Literal["eth_to_pol", "pol_to_eth"]


class MultiRoundResult(TypedDict):
    rounds: List[ArbitrageResult]
    total_profit: float
    final_eth_usdc: float
    final_eth_zerc: float
    final_pol_usdc: float
    final_pol_zerc: float
    round_count: int


def calculate_amount_out(
    amount_in: float, reserve_in: float, reserve_out: float
) -> float:
    numerator: float = amount_in * reserve_out
    denominator: float = reserve_in + amount_in
    return numerator / denominator


def calculate_arbitrage(
    eth_usdc_balance: float,
    eth_zerc_balance: float,
    pol_usdc_balance: float,
    pol_zerc_balance: float,
) -> ArbitrageResult:
    eth_price: float = eth_usdc_balance / eth_zerc_balance
    pol_price: float = pol_usdc_balance / pol_zerc_balance

    result: ArbitrageResult = {
        "usdc_in": 0.0,
        "zerc_bridged": 0.0,
        "usdc_out": 0.0,
        "profit": 0.0,
        "direction": "",
    }

    price_diff_pct: float = abs(eth_price - pol_price) / min(eth_price, pol_price) * 100

    if price_diff_pct < 0.001:
        return result

    try:
        if eth_price < pol_price:
            direction: Literal["eth_to_pol", "pol_to_eth"] = "eth_to_pol"
            source_usdc: float = eth_usdc_balance
            source_zerc: float = eth_zerc_balance
            target_usdc: float = pol_usdc_balance
            target_zerc: float = pol_zerc_balance
        else:
            direction: Literal["eth_to_pol", "pol_to_eth"] = "pol_to_eth"
            source_usdc: float = pol_usdc_balance
            source_zerc: float = pol_zerc_balance
            target_usdc: float = eth_usdc_balance
            target_zerc: float = eth_zerc_balance

        source_ratio: float = source_usdc / source_zerc
        target_ratio: float = target_usdc / target_zerc

        gamma: float = (target_ratio / source_ratio) ** 0.5

        optimal_usdc_in: float = source_usdc * (gamma - 1) / (1 + gamma)

        zerc_out: float = calculate_amount_out(
            optimal_usdc_in, source_usdc, source_zerc
        )

        usdc_out: float = calculate_amount_out(zerc_out, target_zerc, target_usdc)

        profit: float = usdc_out - optimal_usdc_in

        if profit <= 0:
            return result

        result = {
            "usdc_in": optimal_usdc_in,
            "zerc_bridged": zerc_out,
            "usdc_out": usdc_out,
            "profit": profit,
            "direction": direction,
        }

    except Exception:
        return result

    return result


def simulate_multi_round_arbitrage(
    eth_usdc_balance: float,
    eth_zerc_balance: float,
    pol_usdc_balance: float,
    pol_zerc_balance: float,
    max_rounds: int = 10,
    min_price_diff_pct: float = 0.1,
) -> MultiRoundResult:
    results: List[ArbitrageResult] = []

    current_eth_usdc: float = eth_usdc_balance
    current_eth_zerc: float = eth_zerc_balance
    current_pol_usdc: float = pol_usdc_balance
    current_pol_zerc: float = pol_zerc_balance

    total_profit: float = 0.0

    for i in range(max_rounds):
        eth_price: float = current_eth_usdc / current_eth_zerc
        pol_price: float = current_pol_usdc / current_pol_zerc

        price_diff_pct: float = (
            abs(eth_price - pol_price) / min(eth_price, pol_price) * 100
        )

        if price_diff_pct < min_price_diff_pct:
            break

        result: ArbitrageResult = calculate_arbitrage(
            current_eth_usdc, current_eth_zerc, current_pol_usdc, current_pol_zerc
        )

        if result["profit"] <= 0:
            break

        if result["direction"] == "eth_to_pol":
            current_eth_usdc += result["usdc_in"]
            current_eth_zerc -= result["zerc_bridged"]
            current_pol_usdc -= result["usdc_out"]
            current_pol_zerc += result["zerc_bridged"]
        else:
            current_pol_usdc += result["usdc_in"]
            current_pol_zerc -= result["zerc_bridged"]
            current_eth_usdc -= result["usdc_out"]
            current_eth_zerc += result["zerc_bridged"]

        results.append(result)
        total_profit += result["profit"]

    return {
        "rounds": results,
        "total_profit": total_profit,
        "final_eth_usdc": current_eth_usdc,
        "final_eth_zerc": current_eth_zerc,
        "final_pol_usdc": current_pol_usdc,
        "final_pol_zerc": current_pol_zerc,
        "round_count": len(results),
    }


class ArbitrageOutput(NamedTuple):
    total_usdc_in: float
    total_zerc_bridged: float
    total_usdc_out: float
    total_profit: float


async def find_optimal_arbitrage() -> ArbitrageOutput:
    try:
        eth_reserves = await get_pool_reserves(eth_w3, ETH_LP_ADDRESS, "eth")
        pol_reserves = await get_pool_reserves(pol_w3, POL_LP_ADDRESS, "pol")

        multi_result: MultiRoundResult = simulate_multi_round_arbitrage(
            eth_reserves.formatted.usdc_reserves,
            eth_reserves.formatted.zerc_reserves,
            pol_reserves.formatted.usdc_reserves,
            pol_reserves.formatted.zerc_reserves,
            max_rounds=10,
            min_price_diff_pct=0.1,
        )

        if multi_result["round_count"] == 0:
            return ArbitrageOutput(0.0, 0.0, 0.0, 0.0, 0)

        print(multi_result)

        total_usdc_in: float = 0
        total_zerc_bridged: float = 0
        total_usdc_out: float = 0
        total_profit: float = 0

        for round in multi_result["rounds"]:
            total_usdc_in += round["usdc_in"]
            total_zerc_bridged += round["zerc_bridged"]
            total_usdc_out += round["usdc_out"]
            total_profit += round["profit"]

        return ArbitrageOutput(
            total_usdc_in,
            total_zerc_bridged,
            total_usdc_out,
            total_profit,
        )

    except Exception:
        raise


async def main() -> None:
    result = await find_optimal_arbitrage()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
