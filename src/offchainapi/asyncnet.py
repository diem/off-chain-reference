import aiohttp
import asyncio
from aiohttp import web

class Aionet:

    def __init__(self, vasp):
        self.vasp = vasp
        self.session = None

        # TODO: must eventually call
        # await self.session.close()


    async def handle_request(self, request):
        return web.Response(text="Hello, world")
    
    async def handle_offchain_request(self, request):
        myself_name = request.match_info['recvvasp']
        other_name = request.match_info['sendvasp']
        channel = self.vasp.get_channel(other_name)

        # Perform the request, send back the reponse
        # TODO: here we may place the reqyest in a queue and have it
        #       handled by a central task per channel to ensure we
        #       handle requests, and send responses strictly in 
        #       sequence.
        body = await request.text()
        response = channel.parse_handle_request(body)

        # Send back the response
        return web.Response(text=response)
    
    async def send_request(self, other_vasp, off_chain_request):
        # Init the client
        if self.session is None:
            self.session = aiohttp.ClientSession()

        my_name = self.vasp.my_name
        channel = self.vasp.get_channel(other_vasp)

        addr = 'http://otherhost' + f'/{other_vasp}/{my_name}/process'
        async with self.session.post(addr, data=off_chain_request) as resp:
            channel.parse_handle_response(resp.text())
        
        # TODO: here we can return whether it worked or not.
        return
    
    async def new_command(self, other_vasp, command):
        channel = self.vasp.get_channel(other_vasp)
        request = channel.sequence_command_local(command)

        result = await self.send_request(other_vasp, request)
        return result
    
    def sync_new_command(self, other_vasp, command, loop):
        fut = asyncio.run_coroutine_threadsafe(self.new_command(other_vasp, command), loop)
        # Returns a future that can be used to trigger 
        # a callback when a result is available.
        return fut


def make_net_app(vasp):
    app = web.Application()
    net_handler = Aionet(vasp)
    app.add_routes([web.post('/', net_handler.handle_request)])
    app.add_routes([web.post('/{recvvasp}/{sendvasp}/process', net_handler.handle_request)])
    return app, net_handler

def sync_new_command(net_handler, loop, ):
    fut = asyncio.run_coroutine_threadsafe(net_handler.new_command(), loop)
