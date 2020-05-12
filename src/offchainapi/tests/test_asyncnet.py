from ..asyncnet import Aionet
from ..protocol_messages import OffChainException
from ..business import BusinessNotAuthorized

import pytest
import aiohttp
from ..crypto import ComplianceKey

@pytest.fixture
def tester_addr(three_addresses):
    _, _, a0 = three_addresses
    return a0


@pytest.fixture
def testee_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0

@pytest.fixture
def key():
    return ComplianceKey.generate()

@pytest.fixture
def net_handler(vasp, key):
    vasp.info_context.get_base_url.return_value = '/'
    vasp.info_context.get_peer_compliance_signature_key.return_value = key
    vasp.info_context.get_peer_compliance_verification_key.return_value = key
    return Aionet(vasp)


@pytest.fixture
def url(net_handler, tester_addr):
    return net_handler.get_url('/', tester_addr.as_str())


@pytest.fixture
async def client(net_handler, aiohttp_client):
    return await aiohttp_client(net_handler.app)


@pytest.fixture
async def server(net_handler, tester_addr, aiohttp_server, json_response):
    async def handler(request):
        return aiohttp.web.json_response(json_response)

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


async def test_handle_request(url, net_handler, key, aiohttp_client, json_request):
    from json import dumps
    new_request = {'_signed': key.sign_message(dumps(json_request))}

    client = await aiohttp_client(net_handler.app)

    response = await client.post(url, json=new_request)
    assert response.status == 200
    content = await response.json()
    assert content['status'] == 'success'


async def test_handle_request_business_not_authorised(vasp, url, json_request,
                                                      aiohttp_client):
    vasp.business_context.open_channel_to.side_effect = BusinessNotAuthorized
    net_handler = Aionet(vasp)
    client = await aiohttp_client(net_handler.app)
    response = await client.post(url, json=json_request)
    assert response.status == 401


async def test_handle_request_bad_payload(client, url):
    response = await client.post(url)
    assert response.status == 400


async def test_send_request(net_handler, tester_addr, server, json_request):
    from ..crypto import ComplianceKey
    key = ComplianceKey.generate()
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url
    net_handler.vasp.info_context.get_peer_compliance_signature_key.return_value = key
    net_handler.vasp.info_context.get_peer_compliance_verification_key.return_value = key

    with pytest.raises(OffChainException):
        _ = await net_handler.send_request(tester_addr, json_request)
    # Raises since the vasp did not emit the command; so it does
    # not expect a response.


async def test_send_command(net_handler, tester_addr, server, command):
    from ..crypto import ComplianceKey
    key = ComplianceKey.generate()
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url
    net_handler.vasp.info_context.get_peer_compliance_signature_key.return_value = key
    net_handler.vasp.info_context.get_peer_compliance_verification_key.return_value = key
    req = net_handler.sequence_command(tester_addr, command)
    ret = await net_handler.send_request(tester_addr, req)
    assert ret
