# Algo Trading – Home Assignment

Submit to david.ryan@dcentralab.com within 48 hours of receiving the assignment

## Question:

Write a Python function that finds the optimal trading volume and optimal profit, when the following
two USDC/ZERC Uniswap V2 pools are arbitraged, assuming that 1 USDC = 1 USD:

- Ethereum: https://etherscan.io/address/0x29eba991f9d9e71c6bbd69cb71c074193fd877fd
- Polygon PoS:
  https://polygonscan.com/address/0x514480cf3ed104b5c34a17a15859a190e38e97af

Assume we hold a large balance of USDC on both Ethereum and Polygon, with enough funds to run
an arbitrage of any size in either direction

Assume we can bridge ZERC between Ethereum and Polygon instantly and 1:1 in either direction

Trading route will look like USDC —> ZERC ~:> ZERC —> USDC

Where
—> means swap using one of the two pools above, and
~:> means bridge ZERC

Ignore blockchain transaction fees

After the trading route is complete, the trader should have a net cross-chain gain of USDC and no gain or loss of ZERC

This task is to find the maximum possible profit. You'll need to understand how Uniswap V2 pools work, which is in the Uniswap documentation.

## Function inputs:

- USDC token balance on the Ethereum pool
- ZERC token balance on the Ethereum pool
- USDC token balance on the Polygon pool
- ZERC token balance on the Polygon pool

## Function outputs:

- Amount in of USDC at one end
- Amount bridged of ZERC
- Amount out of USDC at the other end
- Optimal Profit in USD(C)

(Version: 25th Dec 2024)
