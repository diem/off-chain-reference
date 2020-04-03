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
def tester_addr():
    return LibraAddress.encode_to_Libra_address(b'A'*16)


@pytest.fixture
def testee_addr():
    return LibraAddress.encode_to_Libra_address(b'B'*16)


# --- Test client ---

@pytest.fixture
def network_client(tester_addr, testee_addr):
    return NetworkClient(testee_addr, tester_addr)

def test_get_url(network_client, tester_addr, testee_addr):
    url = network_client.get_url('/')
    assert url == f'/{tester_addr.plain()}/{testee_addr.plain()}/process/'


# the 'httpserver' fixture comes from the pytest-httpserver package
def test_send_request(network_client, httpserver, simple_request_json,
                      simple_response_json):
    url = '/process'
    httpserver.expect_request(url).respond_with_json(simple_response_json)
    network_client.send_request(httpserver.url_for(url), simple_request_json)


def test_send_request_unknown_receiver(network_client, simple_request_json):
    url = 'http://bad_url'
    network_client.send_request(url, simple_request_json)


# --- Test server ---


@pytest.fixture
def server(testee_addr):
    processor = MagicMock(spec=CommandProcessor)
    info_context = MagicMock(spec=VASPInfo)
    network_factory = MagicMock()
    vasp = OffChainVASP(testee_addr, processor, info_context, network_factory)
    server = NetworkServer(vasp)
    return server


@pytest.fixture
def flask_client(server):
    server.app.testing = True  # Propagate server errors to the client
    with server.app.test_client() as c:
        yield c


@pytest.fixture
def url(tester_addr, testee_addr):
    return f'/{testee_addr.plain()}/{tester_addr.plain()}/process/'


@pytest.fixture
def bad_request_json():
    # This requests triggers an exception inside 'json.load' of VASPPairChannel.
    return {"random": "random"}


@pytest.fixture
def simple_response_json():
    return {"seq": 0, "command_seq": 0, "status": "success"}


def test_process_request(server, flask_client, url, simple_request_json):
    CommandRequestObject.register_command_type(PaymentCommand)
    server.vasp.info_context.is_authorised_VASP.return_value = True
    response = flask_client.post(url, json=simple_request_json)
    assert response.status_code == 200
    assert json.loads(response.data)['status'] == 'success'


def test_process_request_bad_vasp(server, flask_client, url, simple_request_json):
    server.vasp.info_context.is_authorised_VASP.return_value = False
    response = flask_client.post(url, json=simple_request_json)
    assert response.status_code == 403


def test_process_request_bad_request(server, flask_client, url, bad_request_json):
    server.vasp.info_context.is_authorised_VASP.return_value = True
    response = flask_client.post(url, json=bad_request_json)
    assert response.status_code == 400
