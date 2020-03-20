from networking import *
from protocol import LibraAddress, OffChainVASP
from test_sample_service import simple_request_json
from payment_logic import PaymentCommand
from executor import CommandProcessor
from protocol_messages import CommandRequestObject
from business import VASPInfo

from unittest.mock import MagicMock
import pytest
import json


@pytest.fixture
def network():
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    processor = MagicMock(spec=CommandProcessor)
    vasp = OffChainVASP(addr, processor)
    context = MagicMock(spec=VASPInfo)
    network = Networking(vasp, context)
    return network


@pytest.fixture
def client(network):
    network.app.testing = True  # Propagate server errors to the client
    with network.app.test_client() as c:
        yield c


@pytest.fixture
def simple_response_json():
    return {"seq": 0, "command_seq": 0, "status": "success"}


def test_process_request(network, client, simple_request_json):
    CommandRequestObject.register_command_type(PaymentCommand)
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    url = f'/{addr.plain()}/{other_addr.plain()}/process/'
    network.context.is_authorised_VASP.return_value = True
    response = client.post(url, json=simple_request_json)
    assert response.status_code == 200
    assert json.loads(response.data)['status'] == 'success'


# the 'httpserver' fixture comes from the pytest-httpserver package
def test_send_request(network, httpserver, simple_request_json, simple_response_json):
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    url = '/process'
    httpserver.expect_request(url).respond_with_json(simple_response_json)
    network.send_request(httpserver.url_for(url), other_addr, simple_request_json)


def test_get_url(network):
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    network.context.get_peer_base_url.return_value = '/'
    url = network.get_url(other_addr)
    assert url == f'/{other_addr.plain()}/{addr.plain()}/process/'
