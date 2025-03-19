from web3 import Web3


def get_web3_for_rpc(rpc: str):
    w3 = Web3(Web3.HTTPProvider(rpc))
    if w3.is_connected() == False:
        raise ConnectionError("Couldn't connect to rpc")
    return w3
