from ..asyncnet import Aionet
from ..payment import PaymentActor, PaymentObject
from ..payment_logic import PaymentCommand
from ..protocol_messages import CommandRequestObject, OffChainException
from ..utils import JSONFlag
from ..payment_logic import Status
from ..business import BusinessNotAuthorized

import pytest
import aiohttp


@pytest.fixture
def tester_addr(three_addresses):
    _, _, a0 = three_addresses
    return a0


@pytest.fixture
def testee_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0


@pytest.fixture
def command(three_addresses, payment_action):
    a0, _, b0 = three_addresses
    sender = PaymentActor(b0.as_str(), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    payment = PaymentObject(
        sender, receiver, 'ref', 'orig_ref', 'desc', payment_action
    )
    return PaymentCommand(payment)


@pytest.fixture
def json_request(command):
    request = CommandRequestObject(command)
    request.seq = 0
    request.command_seq = 0
    return request.get_json_data_dict(JSONFlag.NET)


@pytest.fixture
def response_json():
    return {"seq": 0, "command_seq": 0, "status": "success"}


@pytest.fixture
def net_handler(vasp):
    vasp.info_context.is_authorised_VASP.return_value = True
    vasp.info_context.get_base_url.return_value = '/'
    return Aionet(vasp)


@pytest.fixture
def url(net_handler, tester_addr):
    return net_handler.get_url('/', tester_addr.as_str())


@pytest.fixture
async def client(net_handler, aiohttp_client):
    return await aiohttp_client(net_handler.app)


@pytest.fixture
async def server(net_handler, tester_addr, aiohttp_server, response_json):
    async def handler(request):
        return aiohttp.web.json_response(response_json)

    app = aiohttp.web.Application()
    url = net_handler.get_url('/', tester_addr.as_str(), other_is_server=True)
    app.add_routes([aiohttp.web.post(url, handler)])
    server = await aiohttp_server(app)
    return server


def test_init(vasp):
    vasp.info_context.get_base_url.return_value = '/'
    Aionet(vasp)


async def test_handle_request_debug(client):
    response = await client.post('/')
    assert response.status == 200
    text = await response.text()
    assert 'Hello, world' in text


async def test_handle_request(url, client, json_request):
    response = await client.post(url, json=json_request)
    assert response.status == 200
    content = await response.json()
    assert content['status'] == 'success'


async def test_handle_request_business_not_authorised(vasp, url, json_request,
                                                      aiohttp_client):
    vasp.info_context.is_authorised_VASP.return_value = True
    vasp.business_context.open_channel_to.side_effect = BusinessNotAuthorized
    net_handler = Aionet(vasp)
    client = await aiohttp_client(net_handler.app)
    response = await client.post(url, json=json_request)
    assert response.status == 401


async def test_handle_request_forbidden(vasp, url, json_request, aiohttp_client):
    vasp.info_context.is_authorised_VASP.return_value = False
    net_handler = Aionet(vasp)
    client = await aiohttp_client(net_handler.app)
    response = await client.post(url, json=json_request)
    assert response.status == 403


async def test_handle_request_bad_payload(client, url):
    response = await client.post(url)
    assert response.status == 400


async def test_send_request(net_handler, tester_addr, server, json_request):
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url
    with pytest.raises(OffChainException):
        _ = await net_handler.send_request(tester_addr, json_request)
    # Raises since the vasp did not emit the command; so it does
    # not expect a response.


async def test_send_command(net_handler, tester_addr, server, command):
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url
    req = net_handler.sequence_command(tester_addr, command)
    ret = await net_handler.send_request(tester_addr, req)
    assert ret
