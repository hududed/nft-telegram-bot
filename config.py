# config.py

import os

# Set a bot version
CODE_VERSION = '0.6'

# Database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'tokens_testnet.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
SQLALCHEMY_TRACK_MODIFICATIONS = True

# IPFS - blockfrost limited to 100mb, try nft-storage
BLOCKFROST_IPFS = os.getenv('BLOCKFROST_IPFS')

# NFTSTORAGE
NFTSTORAGE = os.getenv('NFTSTORAGE')

# Token
BLOCKFROST_TESTNET = os.getenv('BLOCKFROST_TESTNET')
CARDANO_CLI = "/Applications/Daedalus\ Testnet.app/Contents/MacOS/cardano-cli"
TESTNET_ID = os.getenv('TESTNET_ID')

# Misc
# Set the buffer to 1 hour
SLOT_BUFFER = 3600
