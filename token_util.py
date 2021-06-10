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

def mint(**kwargs):
    """ Minting of the actual token """
    # Get session:
    session_uuid = kwargs.get('session_uuid')
    # Start DB Session
    session = Session()
    logging.info(f'Minting started for {session_uuid}')

    sesh_exists = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).scalar() is not None
    if sesh_exists:
        logging.info(f'Session Found: {session_uuid}')
    else:
        logging.info(f"No Session found: {session_uuid}")
        return False

    # We have data
    token_data = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).one()

    # Temporary arbitrary logic to fail tries to re-mint tokens
    if token_data.tx_submitted:
        logging.info(f"Session already Minted: {session_uuid}")
        return False

    # Get current slot
    current_slot = get_current_slot()

    slot_cushion = config.SLOT_CUSHION
    invalid_after_slot = current_slot + slot_cushion
    # Add to DB
    token_data.current_slot = current_slot
    token_data.slot_cushion = slot_cushion
    token_data.invalid_after_slot = invalid_after_slot
    session.add(token_data)
    session.commit()

    # Check to see if we have UTXO
    utxo = check_wallet_utxo(token_data.bot_payment_addr)
    tx_hash = utxo[0]
    tx_ix = int(utxo[1])
    available_lovelace = int(utxo[2])
        if utxo:
        # Add UTXO data to DB
        token_data.utxo_tx_hash = utxo[0]
        token_data.utxo_tx_ix = utxo[1]
        token_data.utxo_lovelace = utxo[2]
        session.add(token_data)
        session.commit()

    if available_lovelace >= 5000000:
        # Check BlockFrost for tx details to get the return addr
        tx_details = get_tx_details(utxo[0])
        creator_pay_addr = tx_details['inputs'][0]['address']
        token_data.creator_pay_addr = creator_pay_addr
        session.add(token_data)
        session.commit()
        logging.info(f"Added creator_pay_addr to DB, "
              f"we will send the token back to this address")
        logging.info(creator_pay_addr)
    else:
        # FAIL
        logging.info("Creator failed to send proper funds!")
        return False

    # Use policy keys to make policy file
    # TODO Verify policy keys were made previously
    policy_vkey = f'tmp/{session_uuid}-policy.vkey'
    policy_script = f'tmp/{session_uuid}-policy.script'
    policy_id = ''

    policy_script_exists = session.query(Tokens).filter(
        Tokens.session_uuid == session_uuid).filter(
        Tokens.policy_script_created).scalar() is not None

    logging.info(policy_script_exists)
    if policy_script_exists:
        logging.info("Policy Script already created for session, skip.")
    else:
        # Building a token locking policy for NFT
        policy_dict = {
            "type": "all",
            "scripts": [
                {
                    "keyHash": "",
                    "type": "sig"
                },
                {
                    "type": "before",
                    "slot": 0
                }
            ]
        }
        # Generate policy key-hash
        cmd = f"{config.CARDANO_CLI} address key-hash " \
              f"--payment-verification-key-file {policy_vkey}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        response = str(out[0], 'UTF-8')
        policy_keyhash = response.strip()
        if policy_keyhash:
            logging.info(f"Policy keyHash created: {policy_keyhash}")
            token_data.policy_keyhash = policy_keyhash
            session.add(token_data)
            session.commit()
        else:
            logging.info("Policy keyHash failed to create")
            return False

        # Add keyHash and slot to dict
        policy_dict["scripts"][0]["keyHash"] = policy_keyhash
        policy_dict["scripts"][1]["slot"] = current_slot + slot_cushion

        logging.info(f"Policy Dictionary for token: {policy_dict}")
        # Write out the policy script to a file for later
        policy_script_out = open(policy_script, "w+")
        json.dump(policy_dict, policy_script_out)
        policy_script_out.close()
        token_data.policy_keys_created = True
        session.add(token_data)
        session.commit()

        # Generate policy ID

        cmd = f"{config.CARDANO_CLI} transaction policyid --script-file {policy_script}"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out = proc.communicate()
        policy_id = str(out[0], 'UTF-8')
        logging.info(f"Policy ID: {policy_id}")
        token_data.policy_id = policy_id
        session.add(token_data)
        session.commit()

    # Create Metadata

    metadata_file = f'tmp/{session_uuid}-metadata.json'
    meta_dict = {
        "721": {
            token_data.policy_id.strip(): {
                f"{token_data.token_number}": {
                    "image": f"ipfs://{token_data.token_ipfs_hash}",
                    "ticker": token_data.token_ticker,
                    "name": token_data.token_name,
                    "description": token_data.token_desc,
                }
            }
        }
    }
    # Write out the policy
    metadata_out = open(metadata_file, "w+")
    json.dump(meta_dict, metadata_out)
    metadata_out.close()
    logging.info("Created metadata.json")
    token_data.metadata_created = True
    session.add(token_data)
    session.commit()

    matx_raw = f'tmp/{session_uuid}-matx.raw'
    # Build Raw TX
    tx_fee = 0
    cmd = f'{config.CARDANO_CLI} transaction build-raw ' \
          f'--fee {tx_fee} ' \
          f'--tx-in {tx_hash}#{tx_ix} ' \
          f'--tx-out {token_data.creator_pay_addr}+{available_lovelace}+"{token_data.token_amount} {token_data.policy_id.strip()}.{token_data.token_ticker}" ' \
          f'--mint="{token_data.token_amount} {token_data.policy_id.strip()}.{token_data.token_ticker}" ' \
          f'--metadata-json-file {metadata_file} ' \
          f'--invalid-hereafter={invalid_after_slot} ' \
          f'--out-file {matx_raw}'

    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    # Command does not return anything
    out = proc.communicate()
    if out[1] is None:
        logging.info(out)
        logging.info("Raw transaction created")
        token_data.raw_tx_created = True
        session.add(token_data)
        session.commit()
    else:
        logging.info(out)
        logging.info('Something failed on building the transaction')
        return False

    # Calculate Fee [or hard set to 3 ADA]
    protocol_params = 'tmp/protocol.json'
    cmd = f"{config.CARDANO_CLI} transaction calculate-min-fee " \
          f"--tx-body-file {matx_raw} " \
          f"--tx-in-count 1 " \
          f"--tx-out-count 1 " \
          f"--witness-count 1 " \
          f"--testnet-magic {config.TESTNET_ID} " \
          f"--protocol-params-file {protocol_params}"

    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.communicate()
    response = str(out[0], 'UTF-8').split()
    # calculate-fee always seems low in testnet
    # Add 100 Lovelace for reasons ???
    tx_fee = int(response[0]) + 100

    logging.info(f'The TX fee today: {tx_fee}')
    # Build TX with Fees

    matx_raw = f'tmp/{session_uuid}-real-matx.raw'
    # Build Raw TX
    ada_return = available_lovelace - tx_fee
    logging.info(f"Return this much plus token back to the "
          f"original funder: {ada_return} lovelace")
    cmd = f'{config.CARDANO_CLI} transaction build-raw ' \
          f'--fee {tx_fee} ' \
          f'--tx-in {tx_hash}#{tx_ix} ' \
          f'--tx-out {token_data.creator_pay_addr}+{ada_return}+"{token_data.token_amount} {token_data.policy_id.strip()}.{token_data.token_ticker}" ' \
          f'--mint="{token_data.token_amount} {token_data.policy_id.strip()}.{token_data.token_ticker}" ' \
          f'--metadata-json-file {metadata_file} ' \
          f'--invalid-hereafter={invalid_after_slot} ' \
          f'--out-file {matx_raw}'

    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    # Command does not return anything
    out = proc.communicate()

    if out[1] is None:
        logging.info(out)
        logging.info("Real Raw transaction created")
    else:
        logging.info(out)
        logging.info('Something failed on building the real transaction')
        return False

    # Sign TX
    payment_skey_file = f'tmp/{session_uuid}-payment.skey'
    policy_skey = f'tmp/{session_uuid}-policy.skey'

    matx_signed = f'tmp/{session_uuid}-matx.signed'
    cmd = f"{config.CARDANO_CLI} transaction sign " \
          f"--signing-key-file {payment_skey_file} " \
          f"--signing-key-file {policy_skey} " \
          f"--script-file {policy_script} " \
          f"--testnet-magic {config.TESTNET_ID} " \
          f"--tx-body-file {matx_raw} " \
          f"--out-file {matx_signed}"


    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    # Command does not return anything
    out = proc.communicate()
    if out[1] is None:
        logging.info(out)
        logging.info("Transaction signed")
        token_data.signed_tx_created = True
        session.add(token_data)
        session.commit()
    else:
        logging.info(out)
        logging.info('Something failed on Transaction signing')
        return False

    # Send to Blockchain
    cmd = f"{config.CARDANO_CLI} transaction submit " \
          f"--tx-file  {matx_signed} " \
          f"--testnet-magic {config.TESTNET_ID}"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    # Command does not return anything
    out = proc.communicate()
    if out[1] is None:
        logging.info(out)
        logging.info("Transaction Submitted")
        token_data.tx_submitted = True
        session.add(token_data)
        session.commit()
    else:
        logging.info(out)
        logging.info('Something failed on Transaction Submitted')
        return False

    # Verify Sent
    confirmed = False
    while confirmed is False:
        creator_utxo = check_wallet_utxo(token_data.creator_pay_addr)
        if creator_utxo:
            # Sleep while wait for BlockFrost to pick up TX
            time.sleep(5)
            nft_tx_details = get_tx_details(creator_utxo[0])
            logging.info(nft_tx_details)
            # Done with minting
            token_data.token_tx_hash = creator_utxo[0]
            session.add(token_data)
            session.commit()
            return True
        confirmed = False
        # Sleep for 5 sec, blocks are 20 seconds
        # so we should get a confirmation in 4 tries
        time.sleep(5)
