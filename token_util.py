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

def pre_mint(**kwargs):
    """ Sets up the token files and metadata
    User should provide all the details in dict """
    logging.info(f"pre_mint started: \n {kwargs}")
    session_uuid = kwargs.get('session_uuid')

    # Start DB Session
    session = Session()

    # Check to see if session already exists
    sesh_exists = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).scalar() is not None
    if sesh_exists:
        token_data = session.query(Tokens).filter(
            Tokens.session_uuid == session_uuid).one()
        logging.info(f'Session already exists {token_data}')
    else:
        # No token session yet, add the data
        logging.info(f"New Session {session_uuid}")
        token_data = Tokens(session_uuid=session_uuid)
        token_data.update(**kwargs)
        session.add(token_data)
        session.commit()

    # ### Start the actual minting process ###
    logging.info("Setting up the token data")

    # Create Stake keys
    # Check to see if we ran this step already
    stake_keys_created = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.stake_keys_created).scalar() is not None
    if stake_keys_created:
        logging.info("Stake Keys already created for session, skip.")
        # return False
    else:
        logging.info("Create Stake keys")
        stake_vkey_file = f'tmp/{session_uuid}-stake.vkey'
        stake_skey_file = f'tmp/{session_uuid}-stake.skey'
        cmd = f"{config.CARDANO_CLI} stake-address key-gen " \
              f"--verification-key-file {stake_vkey_file} " \
              f"--signing-key-file {stake_skey_file}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        response = str(out[0], 'UTF-8')
        if response == '':
            logging.info("Stake keys created.")
            token_data.stake_keys_created = True
            session.add(token_data)
            session.commit()
        else:
            # Stake keys are needed if we fail here we bail out
            logging.info("FAIL: Something went wrong creating stake keys.")
            return False

    # Create Payment keys
    # Check to see if we ran this step already
    payment_keys_created = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.payment_keys_created).scalar() is not None
    if payment_keys_created:
        logging.info("Payment Keys already created for session, skip.")
        # return False
    else:
        logging.info("Create Payment keys")
        payment_vkey_file = f'tmp/{session_uuid}-payment.vkey'
        payment_skey_file = f'tmp/{session_uuid}-payment.skey'
        cmd = f"{config.CARDANO_CLI} address key-gen " \
              f"--verification-key-file {payment_vkey_file} " \
              f"--signing-key-file {payment_skey_file}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        response = str(out[0], 'UTF-8')
        if response == '':
            logging.info("Payment keys created.")
            token_data.payment_keys_created = True
            session.add(token_data)
            session.commit()
        else:
            # Payment keys are needed if we fail here we bail out
            logging.info("FAIL: Something went wrong creating Payment keys.")
            return False

    # Create Payment Address
    stake_keys_created = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.stake_keys_created).scalar() is not None

    payment_keys_created = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.payment_keys_created).scalar() is not None

    if stake_keys_created and payment_keys_created:
        logging.info("Creating Bot Payment Address from stake and Payment keys.")
        stake_vkey_file = f'tmp/{session_uuid}-stake.vkey'
        payment_vkey_file = f'tmp/{session_uuid}-payment.vkey'
        cmd = f"{config.CARDANO_CLI} address build " \
              f"--payment-verification-key-file {payment_vkey_file} " \
              f"--stake-verification-key-file {stake_vkey_file} " \
              f"--testnet-magic {config.TESTNET_ID}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        response = str(out[0], 'UTF-8')
        bot_payment_addr = response.strip()
        logging.info(bot_payment_addr.strip())
        token_data.bot_payment_addr = bot_payment_addr
        session.add(token_data)
        session.commit()
    else:
        logging.info(f"Either Stake Keys, or Payment Keys have not been created")
        logging.info(f"Stake Keys: {stake_keys_created}")
        logging.info(f"Payment Keys: {payment_keys_created}")
        logging.info("FAIL: Something missing, can't move on.")
        return False

    # Get the blockchain protocol parameters
    # Generally we only need this once and it should stay around
    protocol_params = 'tmp/protocol.json'
    protocol_params_exist = os.path.isfile(protocol_params)

    protocol_params_created = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.protocol_params_created).scalar is not None

    if protocol_params_exist and protocol_params_created:
        logging.info("protocol_params_exist, no need to recreate")
    else:
        cmd = f"{config.CARDANO_CLI} query protocol-parameters " \
              f"--testnet-magic {config.TESTNET_ID} " \
              f"--out-file {protocol_params}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        response = str(out[0], 'UTF-8')
        if response == '':
            token_data.protocol_params_created = True
            session.add(token_data)
            session.commit()
            logging.info("Saved protocol.json")
        else:
            logging.info("FAIL: Could not get protocol.json")
            return False

    # Create Policy Script
    policy_vkey = f'tmp/{session_uuid}-policy.vkey'
    policy_skey = f'tmp/{session_uuid}-policy.skey'

    policy_keys_exist = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.policy_keys_created).scalar() is not None

    if policy_keys_exist:
        logging.info("Policy Keys already created for session, skip.")
    else:
        # Create Keys
        cmd = f"{config.CARDANO_CLI} address key-gen " \
              f"--verification-key-file {policy_vkey} " \
              f"--signing-key-file {policy_skey}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        response = str(out[0], 'UTF-8')
        if response == '':
            logging.info("Policy keys created.")
            token_data.policy_keys_created = True
            session.add(token_data)
            session.commit()
        else:
            # Policy keys are needed if we fail here we bail out
            logging.info("FAIL: Something went wrong creating Policy keys.")
            return False
    # At this point we need the bot_payment_addr to have UTXO to burn
    logging.info(f"Please deposit 5 ADA in the following address:")
    logging.info(token_data.bot_payment_addr)
    return True
