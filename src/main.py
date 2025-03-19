from web3 import Web3
from constants import ETH_RPC, POL_RPC
from utils import get_web3_for_rpc

eth_w3 = get_web3_for_rpc(ETH_RPC)
pol_w3 = get_web3_for_rpc(POL_RPC)
