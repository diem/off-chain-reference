from networking import *
from protocol import LibraAddress, OffChainVASP
from test_sample_service import simple_request_json
from payment_logic import PaymentCommand
from executor import CommandProcessor
from protocol_messages import CommandRequestObject

from unittest.mock import MagicMock
import pytest
import json


@pytest.fixture
def client():
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    processor = MagicMock(spec=CommandProcessor)
    vasp = OffChainVASP(addr, processor)
    networking = Networking(vasp)
    networking.app.testing = True  # Propagate server errors to the client
    with networking.app.test_client() as c:
        yield c


def test_process(client, simple_request_json):
    CommandRequestObject.register_command_type(PaymentCommand)
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    url = '/'+addr.plain()+'/'+other_addr.plain()+'/process/'
    response = client.post(url, json=simple_request_json)
    assert response.status_code == 200
    assert json.loads(response.data)['status'] == 'success'
