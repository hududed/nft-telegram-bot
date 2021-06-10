# nft-telegram-bot

A simple bot to mint NFTs on the Cardano blockchain via the Telegram app pre-Alonzo HardFork

## Prerequisites

2 Blockfrost API keys - 1 for IPFS (holds NFT), 1 for Cardano Testnet (holds testADA).      
1 Telegram BotFather API keys https://t.me/botfather.   
Daedalus TestNet

## Process flow

1. Create and upload image to Telegram
2. Image is pinned to IPFS via Blockfrost
3. Receive IPFS hash
4. Input metadata e.g. Ticker, TokenName, Description
5. `token_util.py` creates staking keys, payment keys, payment address, retrieves blockchain protocol params, creates policy keys
6. Generates payment address (min. 5 ADA)
7. After payment confirmation, minting process begins
8. Finds funded address and burn UTxOs
9. Finds payer address, mints and sends token with change
10. End chat
