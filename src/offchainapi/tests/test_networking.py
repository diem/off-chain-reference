from ..networking import NetworkClient, NetworkServer
from ..payment import PaymentActor, PaymentObject
from ..payment_logic import PaymentCommand
from ..protocol_messages import CommandRequestObject
from ..utils import JSONFlag
from ..payment_logic import Status

from json import dumps, loads
from unittest.mock import MagicMock
import pytest



@pytest.fixture
def tester_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0


@pytest.fixture
def testee_addr(three_addresses):
    _, _, b0 = three_addresses
    return b0


@pytest.fixture
def request_json(three_addresses, payment_action):
    a0, _, b0 = three_addresses
    sender = PaymentActor(a0.as_str(), 'C', Status.none, [])
    receiver = PaymentActor(b0.as_str(), '1', Status.none, [])
    payment = PaymentObject(
        sender, receiver, 'ref', 'orig_ref', 'desc', payment_action
    )
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.seq = 0
    return request.get_json_data_dict(JSONFlag.NET)


# --- Test client ---

@pytest.fixture
def network_client(tester_addr, testee_addr):
    return NetworkClient(testee_addr, tester_addr)


@pytest.fixture
def response_json():
    return {"seq": 0, "command_seq": 0, "status": "success"}


def test_get_url(network_client, tester_addr, testee_addr):
    url = network_client.get_url('/')
    assert url == f'/{tester_addr.as_str()}/{testee_addr.as_str()}/process/'


# the 'httpserver' fixture comes from the pytest-httpserver package
def test_send_request(network_client, httpserver, request_json, response_json):
    url = '/process'
    httpserver.expect_request(url).respond_with_json(dumps(response_json))
    response = network_client.send_request(httpserver.url_for(url), request_json)
    assert response.status_code == 200


def test_send_request_unknown_receiver(network_client, request_json):
    url = 'http://bad_url'
    response = network_client.send_request(url, request_json)
    assert response is None


# --- Test server ---


@pytest.fixture
def server(vasp, testee_addr):
    vasp.vasp_addr = testee_addr
    return NetworkServer(vasp)


@pytest.fixture
def flask_client(server):
    server.app.testing = True  # Propagate server errors to the client
    with server.app.test_client() as c:
        yield c


@pytest.fixture
def url(tester_addr, testee_addr):
    return f'/{testee_addr.as_str()}/{tester_addr.as_str()}/process/'


@pytest.fixture
def bad_request_json():
    # This requests triggers an exception inside 'json.load' of VASPPairChannel.
    return {"random": "random"}


def test_process_request(server, flask_client, url, request_json):
    server.vasp.info_context.is_authorised_VASP.return_value = True
    response = flask_client.post(url, json=request_json)
    assert response.status_code == 200
    assert loads(response.data)['status'] == 'success'


def test_process_request_bad_vasp(server, flask_client, url, request_json):
    server.vasp.info_context.is_authorised_VASP.return_value = False
    response = flask_client.post(url, json=request_json)
    assert response.status_code == 403


def test_process_request_bad_request(server, flask_client, url, bad_request_json):
    server.vasp.info_context.is_authorised_VASP.return_value = True
    response = flask_client.post(url, json=bad_request_json)
    # TODO: here we should be returning 400
    assert response.status_code == 200
