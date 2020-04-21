import aiohttp
from aiohttp import web

class Aionet:

    def __init__(self, vasp):
        self.vasp = vasp

    async def handle_request(self, request):
        return web.Response(text="Hello, world")

def make_net_app(vasp):
    app = web.Application()
    net_handler = Aionet(vasp)
    app.add_routes([web.post('/', net_handler.handle_request)])
    return app, net_handler
