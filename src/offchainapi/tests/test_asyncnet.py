from ..asyncnet import Aionet, make_net_app
from ..payment import PaymentActor, PaymentObject
from ..payment_logic import PaymentCommand
from ..protocol_messages import CommandRequestObject
from ..utils import JSONFlag
from ..payment_logic import Status
from ..business import BusinessNotAuthorized

from unittest.mock import MagicMock
import pytest
from json import loads


@pytest.fixture
def tester_addr(three_addresses):
    _, _, a0 = three_addresses
    return a0


@pytest.fixture
def testee_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0


@pytest.fixture
def json_request(three_addresses, payment_action):
    a0, _, b0 = three_addresses
    sender = PaymentActor(b0.as_str(), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    payment = PaymentObject(
        sender, receiver, 'ref', 'orig_ref', 'desc', payment_action
    )
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.seq = 0
    request.command_seq = 0
    return request.get_json_data_dict(JSONFlag.NET)


@pytest.fixture
def net_handler(vasp):
    vasp.info_context.is_authorised_VASP.return_value = True
    return make_net_app(vasp)


@pytest.fixture
def url(net_handler, tester_addr):
    return net_handler.get_url('/', tester_addr.as_str())


@pytest.fixture
async def client(net_handler, aiohttp_client):
    return await aiohttp_client(net_handler.app)


def test_init(vasp):
    make_net_app(vasp)


async def test_handle_request_debug(client):
    response = await client.post('/')
    assert response.status == 200
    text = await response.text()
    assert 'Hello, world' in text


async def test_handle_request(url, client, json_request):
    response = await client.post(url, json=json_request)
    assert response.status == 200
    content = await response.json()
    assert loads(content)['status'] == 'success'


async def test_handle_request_business_not_authorised(vasp, url, json_request,
                                                      aiohttp_client):
    vasp.info_context.is_authorised_VASP.return_value = True
    vasp.business_context.open_channel_to.side_effect = BusinessNotAuthorized
    net_handler = make_net_app(vasp)
    client = await aiohttp_client(net_handler.app)
    response = await client.post(url, json=json_request)
    assert response.status == 401


async def test_handle_request_forbidden(vasp, url, json_request, aiohttp_client):
    vasp.info_context.is_authorised_VASP.return_value = False
    net_handler = make_net_app(vasp)
    client = await aiohttp_client(net_handler.app)
    response = await client.post(url, json=json_request)
    assert response.status == 403


async def test_handle_request_bad_payload(client, url):
    response = await client.post(url)
    assert response.status == 400

async def test_send_request():
    pass
