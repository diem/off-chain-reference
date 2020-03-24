from networking import *
from protocol import LibraAddress, OffChainVASP, VASPPairChannel
from test_sample_service import simple_request_json
from payment_logic import PaymentCommand
from executor import CommandProcessor
from protocol_messages import CommandRequestObject
from business import VASPInfo

from unittest.mock import MagicMock
import pytest
import json


@pytest.fixture
def tester_addr():
    return LibraAddress.encode_to_Libra_address(b'A'*16)


@pytest.fixture
def testee_addr():
    return LibraAddress.encode_to_Libra_address(b'B'*16)


@pytest.fixture
def network(testee_addr):
    processor = MagicMock(spec=CommandProcessor)
    info_context = MagicMock(spec=VASPInfo)
    vasp = OffChainVASP(testee_addr, processor, info_context)
    network = Networking(vasp)
    return network


@pytest.fixture
def client(network):
    network.app.testing = True  # Propagate server errors to the client
    with network.app.test_client() as c:
        yield c


@pytest.fixture
def url(tester_addr, testee_addr):
    return f'/{testee_addr.plain()}/{tester_addr.plain()}/process/'


@pytest.fixture
def bad_request_json():
    # This requests triggers an exception inside 'json.load' of VASPPairChannel
    return {"random": "random"}


@pytest.fixture
def simple_response_json():
    return {"seq": 0, "command_seq": 0, "status": "success"}


# --- Test server ---


def test_process_request(network, client, url, simple_request_json):
    CommandRequestObject.register_command_type(PaymentCommand)
    network.vasp.info_context.is_authorised_VASP.return_value = True
    response = client.post(url, json=simple_request_json)
    assert response.status_code == 200
    assert json.loads(response.data)['status'] == 'success'


def test_process_request_bad_vasp(network, client, url, simple_request_json):
    network.vasp.info_context.is_authorised_VASP.return_value = False
    response = client.post(url, json=simple_request_json)
    assert response.status_code == 401


def test_process_request_bad_request(network, client, url, bad_request_json):
    network.vasp.info_context.is_authorised_VASP.return_value = True
    response = client.post(url, json=bad_request_json)
    assert response.status_code == 400


# --- Test client ---


def test_get_url(tester_addr, testee_addr):
    base_url = '/'
    url = Networking.get_url(base_url, testee_addr, tester_addr)
    assert url == f'/{tester_addr.plain()}/{testee_addr.plain()}/process/'


# the 'httpserver' fixture comes from the pytest-httpserver package
def test_send_request(httpserver, simple_request_json, simple_response_json):
    url = '/process'
    httpserver.expect_request(url).respond_with_json(simple_response_json)
    Networking.send_request(httpserver.url_for(url), simple_request_json)


def test_send_request_unknown_receiver(network, simple_request_json):
    url = 'http://bad_url'
    Networking.send_request(url, simple_request_json)
