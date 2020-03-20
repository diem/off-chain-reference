from auth_networking import *
from protocol import LibraAddress, OffChainVASP
from executor import CommandProcessor
from business import VASPInfo
from payment_logic import PaymentCommand
from protocol_messages import CommandRequestObject

from payment import PaymentActor, PaymentAction, PaymentObject
from status_logic import Status
from utils import JSONFlag

from unittest.mock import MagicMock
import sys
import requests

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

def simple_request_json():
    sender_addr = LibraAddress.encode_to_Libra_address(b'A'*16).encoded_address
    receiver_addr   = LibraAddress.encode_to_Libra_address(b'B'*16).encoded_address
    assert type(sender_addr) == str
    assert type(receiver_addr) == str

    sender = PaymentActor(sender_addr, 'C', Status.none, [])
    receiver = PaymentActor(receiver_addr, '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref_payment_1', 'orig_ref...', 'description ...', action)
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.seq = 0
    request_json = json.dumps(request.get_json_data_dict(JSONFlag.NET))
    return request_json


if __name__ == "__main__":

    # Test keys and certificates.
    assets_path = '../assets/'
    server_key = f'{assets_path}server_key.pem'
    server_key_password = None
    server_cert = f'{assets_path}server_cert.pem'
    client_key = f'{assets_path}client_key.pem'
    client_cert = f'{assets_path}client_cert.pem'

    # Server address
    base_url = 'https://127.0.0.1:5000/'

    # Create the networking.
    CommandRequestObject.register_command_type(PaymentCommand)
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    processor = MagicMock(spec=CommandProcessor)
    vasp = OffChainVASP(addr, processor)
    context = MagicMock(spec=VASPInfo)
    context.is_authorised_VASP.return_value = True
    network = AuthenticatedNetworking(
        vasp,
        context,
        server_key,
        server_key_password,
        server_cert,
        client_key,
        client_cert
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
        network.send_request(url, other_addr, simple_request_json())

    elif mode == 'server':
        network.run()
    else:
        assert False
