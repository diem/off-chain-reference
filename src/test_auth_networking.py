from auth_networking import *
from protocol import LibraAddress, OffChainVASP
from executor import CommandProcessor
from business import VASPInfo
from protocol_messages import CommandRequestObject
from payment_logic import PaymentCommand

from unittest.mock import MagicMock
import sys
import requests
import json

'''
Run the following command to create the server's key and certificate:
    $ openssl req -x509 -newkey rsa:4096 -keyout server_key.pem \
        -out server_cert.pem -nodes -days 365 -subj "/CN=127.0.0.1"

Run the following commands to create the client's key and certificate:
    $ openssl req -newkey rsa:4096 -keyout client_key.pem -out client_csr.pem \
        -nodes -days 365
    $ openssl x509 -req -in client_csr.pem -signkey client_key.pem \
        -out client_cert.pem -days 365

For testing the client from a web browser, generate a p12 file and add it to the
browser (or to the OS Keychain if using Safari):
    $ openssl pkcs12 -export -in client_cert.pem -inkey client_key.pem \
        -out client.p12
'''


test_vector_request = """{
        "seq": 0,
        "command": {
            "dependencies": [],
            "creates_versions": ["TJZb1EwYY/gloKCIfiASHw=="],
            "diff": {
                "reference_id": "ref_payment_1",
                "original_payment_reference_id": "orig_ref...",
                "description": "description ...",
                "sender": {
                    "address": "QUFBQUFBQUFBQUFBQUFBQQ==",
                    "subaddress": "C",
                    "status": "none",
                    "metadata": []
                },
                "receiver": {
                    "address": "QkJCQkJCQkJCQkJCQkJCQg==",
                    "subaddress": "1",
                    "status": "none",
                    "metadata": []
                },
                "action": {
                    "amount": 5,
                    "currency": "TIK",
                    "action": "charge",
                    "timestamp": "2020-01-02 18:00:00 UTC"
                }
            }
        },
        "command_type": "<class 'payment_logic.PaymentCommand'>"
    }"""


if __name__ == "__main__":

    # Test keys and certificates.
    assets_path = '../test_vectors/'
    server_key = f'{assets_path}server_key.pem'
    server_cert = f'{assets_path}server_cert.pem'
    client_key = f'{assets_path}client_key.pem'
    client_cert = f'{assets_path}client_cert.pem'

    # Server address
    base_url = 'https://127.0.0.1:5000/'

    # Create the networking.
    CommandRequestObject.register_command_type(PaymentCommand)
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    processor = MagicMock(spec=CommandProcessor)
    info_context = MagicMock(spec=VASPInfo)
    info_context.get_peer_base_url.return_value = base_url
    network_factory = NetworkFactory()
    vasp = OffChainVASP(addr, processor, info_context, network_factory)
    network_server = AuthNetworkServer(
        vasp, server_key, server_cert, client_cert
    )

    # Run either as client or as server
    mode = sys.argv[1]
    if mode == 'client-ping':
        response = requests.get(
            base_url, verify=server_cert, cert=(client_cert, client_key)
        )
        print('\nRESPONSE: ', response.json())
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    elif mode == 'client-process':
        other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
        url = f'{base_url}{addr.plain()}/{other_addr.plain()}/process/'
        network_client = AuthNetworkClient(
            addr, other_addr, server_cert, client_cert, client_key
        )
        response = network_client.send_request(url, test_vector_request)
        response = response.json() if response != None else None
        print('\nRESPONSE: ', response)

    elif mode == 'server':
        network_server.run()
    else:
        assert False
