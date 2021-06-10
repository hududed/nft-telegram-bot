# ipfs_util.py

import config
import requests
import logging
logger = logging.getLogger(__name__)


def create_ipfs(image):
    """ Uploads image to Blockfrost """
    with open(image, "rb") as file_upload:
        ipfs_create_url = "https://ipfs.blockfrost.io/api/v0/ipfs/add"
        files = {'file': file_upload}
        headers = {"project_id": f"{config.BLOCKFROST_IPFS}"}
        res = requests.post(ipfs_create_url,  files=files, headers=headers)
        res.raise_for_status()
        if res.status_code == 200:
            logging.info("Uploaded image to Blockfrost")
            logging.info(res.json())
            return res.json()
        else:
            logger.error("Something failed here? Upload to blockfrost failed")
            return False

def check_ipfs(ipfs_hash):
    """ Check to see if the ipfs hash is accessible via
    ipfs.io and cloudflare """
    ipfs_gateways = [
        f"https://gateway.ipfs.io/ipfs/{ipfs_hash}",
        f"https://cloudflare-ipfs.com/ipfs/{ipfs_hash}"
    ]

    ipfs_status = []
    for gateway in ipfs_gateways:
        res = requests.get(gateway)
        logging.info(res.status_code)
        if res.status_code == 200:
            ipfs_status.append(True)
        else:
            ipfs_status.append(False)
    logging.info(f"Availability:  {ipfs_status}")
    return True
