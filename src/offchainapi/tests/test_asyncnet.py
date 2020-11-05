# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..asyncnet import Aionet
from ..protocol_messages import OffChainException
from ..business import BusinessNotAuthorized
from ..utils import get_unique_string

import pytest
import aiohttp
import json
import asyncio


@pytest.fixture
def tester_addr(three_addresses):
    _, _, a0 = three_addresses
    return a0


@pytest.fixture
def testee_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0


@pytest.fixture
def net_handler(vasp, key):
    vasp.info_context.get_my_compliance_signature_key.return_value = key
    vasp.info_context.get_peer_compliance_verification_key.return_value = key
    return Aionet(vasp)


@pytest.fixture
def url(net_handler, tester_addr):
    return net_handler.get_url('/', tester_addr.as_str())


@pytest.fixture
async def client(net_handler, aiohttp_client):
    return await aiohttp_client(net_handler.app)


@pytest.fixture
async def server(net_handler, tester_addr, testee_addr, aiohttp_server, key):
    obj = {}
    async def handler(request):
        if 'cid' not in obj:
            print('DEBUG: ATTACH A CID!!!!!!')
        headers = {'X-Request-ID': request.headers['X-Request-ID']}
        resp = {"cid": obj.get("cid",'SET A VALUE'), "status": "success"}
        signed_json_response = await key.sign_message(json.dumps(resp))
        return aiohttp.web.Response(text=signed_json_response, headers=headers)

    app = aiohttp.web.Application()
    url = net_handler.get_url('/', tester_addr.as_str(), other_is_server=True)
    app.add_routes([aiohttp.web.post(url, handler)])
    server = await aiohttp_server(app)
    server.side = obj
    return server


def test_init(vasp):
    Aionet(vasp)


async def test_handle_request(url, net_handler, key, client, signed_json_request):
    headers = {'X-Request-ID': 'abc'}
    response = await client.post(
        url, data=signed_json_request,
        headers=headers)
    assert response.status == 200
    content = await response.text()
    content = await key.verify_message(content)
    content = json.loads(content)
    assert content['status'] == 'success'


async def test_handle_request_not_authorised(vasp, url, json_request, client):
    vasp.business_context.open_channel_to.side_effect = BusinessNotAuthorized
    headers = {'X-Request-ID': 'abc'}
    response = await client.post(url, json=json_request, headers=headers)
    assert response.status == 401

async def test_handle_request_bad_payload(client, url):
    headers = {'X-Request-ID': 'abc'}
    response = await client.post(url, headers=headers)
    assert response.status == 400


async def test_send_request(net_handler, tester_addr, server, signed_json_request):
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url

    with pytest.raises(OffChainException):
        _ = await net_handler.send_request(tester_addr, signed_json_request)
    # Raises since the vasp did not emit the command; so it does
    # not expect a response.
    await net_handler.close()


async def test_send_command(net_handler, tester_addr, server, command):
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url
    req = await net_handler.sequence_command(tester_addr, command)
    server.side['cid'] = command.get_request_cid()

    ret = await net_handler.send_request(tester_addr, req)
    await net_handler.close()
    assert ret


async def test_watchdog_task(net_handler, tester_addr, server, command):
    # Ensure there is a request to re-transmit.
    req = await net_handler.sequence_command(tester_addr, command)
    server.side['cid'] = command.get_request_cid()
    base_url = f'http://{server.host}:{server.port}'
    net_handler.vasp.info_context.get_peer_base_url.return_value = base_url
    assert len(net_handler.vasp.channel_store.values()) == 1
    channel = list(net_handler.vasp.channel_store.values())[0]
    assert channel.would_retransmit()
    waiting_packages = await channel.package_retransmit(number=100)
    assert len(waiting_packages) == 1
    assert waiting_packages[0].content == req
    assert len(channel.committed_commands) == 0


    # Run the watchdog for a while.
    loop = asyncio.get_event_loop()
    net_handler.schedule_watchdog(loop, period=0.1)
    await asyncio.sleep(0.3)

    # Ensure the watchdog successfully sent the command.
    assert len(channel.committed_commands) == 1

    # Ensure there is nothing else to re-transmit.
    assert not channel.would_retransmit()
    waiting_packages = await channel.package_retransmit(number=100)
    assert not waiting_packages
    await net_handler.close()


def test_get_url(net_handler, tester_addr, testee_addr):
    base_url = "http://offchain.test.com/offchain"
    expected = f"{base_url}/v1/{tester_addr.as_str()}/{testee_addr.as_str()}/command/"
    url = net_handler.get_url(base_url, tester_addr.as_str(), other_is_server=True)
    assert url == expected

    base_url = "http://offchain.test.com/offchain/"
    expected = f"{base_url}v1/{tester_addr.as_str()}/{testee_addr.as_str()}/command/"
    url = net_handler.get_url(base_url, tester_addr.as_str(), other_is_server=True)
    assert url == expected

    base_url = "http://offchain.test.com"
    expected = f"{base_url}/v1/{tester_addr.as_str()}/{testee_addr.as_str()}/command/"
    url = net_handler.get_url(base_url, tester_addr.as_str(), other_is_server=True)
    assert url == expected

    base_url = "http://offchain.test.com/"
    expected = f"{base_url}v1/{tester_addr.as_str()}/{testee_addr.as_str()}/command/"
    url = net_handler.get_url(base_url, tester_addr.as_str(), other_is_server=True)
    assert url == expected
