from ..asyncnet import *

from unittest.mock import MagicMock

def test_init():
    vasp = MagicMock()
    make_net_app(vasp)


async def test_request(aiohttp_client, loop):
    vasp = MagicMock()
    app, net_handler = make_net_app(vasp)

    client = await aiohttp_client(app)
    resp = await client.post('/')
    assert resp.status == 200
    text = await resp.text()
    assert 'Hello, world' in text
