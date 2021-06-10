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

def check_testnet():
    """ Verifies communication with testnet by querying UTXOs """
    cmd = f"{config.CARDANO_CLI} query utxo " \
          f"--testnet-magic {config.TESTNET_ID}"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.communicate()
    response = str(out[0], 'UTF-8')
    logging.info(response)


def get_current_slot():
    """ Gets blockchain tip returns current slot """
    cmd = f"{config.CARDANO_CLI} query tip " \
          f"--testnet-magic {config.TESTNET_ID}"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.communicate()
    response = str(out[0], 'UTF-8')
    logging.info(response)
    data = json.loads(response)
    logging.info(f"Current Slot:  {data['slot']}")
    return data['slot']

def get_tx_details(tx_hash):
    """ Get TX details from BlockFrost.io """
    url = f'https://cardano-testnet.blockfrost.io/api/v0/txs/{tx_hash}/utxos'
    headers = {"project_id": f"{config.BLOCKFROST_TESTNET}"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    if res.status_code == 200:
        logging.info("Got TX Details.")
        # logging.info(res.json())
        return res.json()
    else:
        logging.info("Something failed here? blockfrost failed")
        return False



