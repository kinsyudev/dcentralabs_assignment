from typing import Literal

from web3 import Web3


ETH_LP_ADDRESS = Web3.to_checksum_address("0x29eBA991F9D9E71C6bBd69cb71c074193fd877Fd")
ETH_USDC_ADDRESS = Web3.to_checksum_address(
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
)
ETH_ZERC_ADDRESS = Web3.to_checksum_address(
    "0xf8428A5a99cb452Ea50B6Ea70b052DaA3dF4934F"
)
ETH_ROUTER_ADDRESS = Web3.to_checksum_address(
    "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
)
POL_LP_ADDRESS = Web3.to_checksum_address("0x514480cF3eD104B5c34A17A15859a190E38E97AF")
POL_USDC_ADDRESS = Web3.to_checksum_address(
    "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
)
POL_ZERC_ADDRESS = Web3.to_checksum_address(
    "0xE1b3eb06806601828976e491914e3De18B5d6b28"
)
POL_ROUTER_ADDRESS = Web3.to_checksum_address(
    "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
)


ETH_RPC = "https://eth.llamarpc.com"
POL_RPC = "https://polygon.llamarpc.com"


ChainType = Literal["eth", "pol"]
