# token_utils.py

import json
import os
import requests
import subprocess
import time

import config
from db_model import Session, Tokens
import logging
logger = logging.getLogger(__name__)


def check_wallet_utxo(wallet):
    """ Querying all UTXOs in wallet """
    cmd = f"{config.CARDANO_CLI} query utxo " \
          f"--address {wallet} " \
          f"--testnet-magic {config.TESTNET_ID}"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.communicate()
    response = str(out[0], 'UTF-8')
    logging.info(response.split()[4:])
    return response.split()[4:]
