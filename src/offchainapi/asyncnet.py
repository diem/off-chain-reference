from .business import BusinessNotAuthorized
from .libra_address import LibraAddress

import aiohttp
from aiohttp import web
import asyncio
import logging
from urllib.parse import urljoin
import json


def make_net_app(vasp):
    return Aionet(vasp)


class Aionet:
    def __init__(self, vasp):
        self.vasp = vasp

        # TODO: This should be a dict holding one session per other vasp.
        self.session = None

        self.app = web.Application()

        # Register routes.
        route = self.get_url('/', '{other_addr}')
        logging.debug(f'Register route {route}')
        self.app.add_routes([web.post(route, self.handle_request)])
        if __debug__:
            self.app.add_routes([
                web.post('/', self.handle_request_debug),
                web.get('/', self.handle_request_debug)
            ])

        self.watchdog_period = 10.0  # seconds

    def __del__(self):
        if self.session:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.session.close())

    async def watchdog_task(self):
        ''' Provides a debug view of pending requests and replies '''
        logging.debug('Start Network Watchdog')
        while True:
            for k in self.vasp.channel_store:
                channel = self.vasp.channel_store[k]
                logging.debug(f'{len(channel.waiting_requests), len(channel.waiting_response)}')
            await asyncio.sleep(self.watchdog_period)


    def get_url(self, base_url, other_addr_str, other_is_server=False):
        if other_is_server:
            server = other_addr_str
            client = self.vasp.get_vasp_address().as_str()
        else:
            server = self.vasp.get_vasp_address().as_str()
            client = other_addr_str
        url = f'{server}/{client}/process/'
        return urljoin(base_url, url)

    if __debug__:
        async def handle_request_debug(self, request):
            return web.Response(text='Hello, world')

    async def handle_request(self, request):
        # TODO: Could there be errors when creating LibraAddress?
        other_addr = LibraAddress(request.match_info['other_addr'])
        logging.debug(f'Request Received from {other_addr.as_str()}')

        # Try to get a channel with the other VASP.
        try:
            channel = self.vasp.get_channel(other_addr)
        except BusinessNotAuthorized as e:
            # Raised if the other VASP is not an authorised business.
            logging.debug(f'Not Authorized {e}')
            raise web.HTTPUnauthorized

        # Verify that the other VASP is authorised to submit the request;
        # ie. that 'other_addr' matches the certificate.
        client_certificate = None  # TODO: Get certificate from ...
        if not self.vasp.info_context.is_authorised_VASP(
            client_certificate, other_addr
        ):
            logging.debug(f'Not Authorized')
            raise web.HTTPForbidden

        # Perform the request, send back the reponse.
        try:
            request_json = await request.json()
            # TODO: Handle the timeout error here
            logging.debug(f'Data Received from {other_addr.as_str()}')
            response = await channel.parse_handle_request_to_future(
                request_json, encoded=False
            )
        except json.decoder.JSONDecodeError as e:
            # Raised if the request does not contain valid JSON.
            logging.debug(f'Type Error {e}')
            import traceback
            traceback.print_exc()
            raise web.HTTPBadRequest

        # Send back the response
        channel.process_waiting_messages()
        logging.debug(f'Sending back response to {other_addr.as_str()}')
        return web.json_response(response.content)

    async def send_request(self, other_addr, json_request):
        logging.debug(f'Connect to {other_addr.as_str()}')

        # Initialize the client.
        if self.session is None:
            self.session = aiohttp.ClientSession()

        # Try to get a channel with the other VASP.
        try:
            channel = self.vasp.get_channel(other_addr)
        except BusinessNotAuthorized as e:
            # Raised if the other VASP is not an authorised business.
            logging.debug(f'Not Authorized {e}')
            return False

        base_url = self.vasp.info_context.get_peer_base_url(other_addr)
        url = self.get_url(base_url, other_addr.as_str(), other_is_server=True)
        logging.debug(f'Sending post request to {url}')
        # TODO: Handle errors with session.post
        async with self.session.post(url, json=json_request) as response:
            try:
                json_response = await response.json()
                logging.debug(f'Json response: {json_response}')

                # TODO: here, what if we receive responses out of order?
                #       I think we should make a future-based parse_handle_response
                #       that returns when there is a genuine success.
                res = channel.parse_handle_response(json_response, encoded=False)
                logging.debug(f'Response parsed with status: {res}')
                channel.process_waiting_messages()
                return res
            except json.decoder.JSONDecodeError as e:
                logging.debug(f'Type Error {e}')
                return False

    async def send_command(self, other_addr, command):
        logging.debug(f'Sending command to {other_addr.as_str()}.')
        try:
            channel = self.vasp.get_channel(other_addr)
        except BusinessNotAuthorized as e:
            # Raised if the other VASP is not an authorised business.
            logging.debug(f'Not Authorized {e}')
            return False

        request = channel.sequence_command_local(command)
        return await self.send_request(other_addr, request.content)

    def sync_new_command(self, other_addr, command, loop):
        ''' Returns a future that can be used to trigger a callback when
        a result is available.
        '''
        return asyncio.run_coroutine_threadsafe(
            self.send_command(other_addr, command), loop
        )

    def get_runner(self):
        return web.AppRunner(self.app)
