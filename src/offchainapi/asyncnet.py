from .business import BusinessNotAuthorized
from .libra_address import LibraAddress


import aiohttp
from aiohttp import web
from aiohttp.client_exceptions import ClientError
import asyncio
import logging
from urllib.parse import urljoin
import json


class NetworkException(Exception):
    pass


class Aionet:
    def __init__(self, vasp):
        ''' Initializes the network system with a OffChainVASP instance. '''
        self.logger = logging.getLogger(name='aionet')

        self.vasp = vasp

        # For the moment hold one session per VASP.
        self.session = None
        self.app = web.Application()

        # Register routes.
        route = self.get_url('/', '{other_addr}')
        self.app.add_routes([web.post(route, self.handle_request)])
        self.logger.debug(f'Register route {route}')

        if __debug__:
            self.app.add_routes([
                web.post('/', self.handle_request_debug),
                web.get('/', self.handle_request_debug)
            ])

        # The watchdog process variables
        self.watchdog_period = 10.0  # seconds
        self.watchdog_task_obj = None  # Store the task here to cancel

    async def close(self):
        ''' Close the open Http client session and the network object. '''
        if self.session is not None:
            session = self.session
            self.session = None
            await session.close()

        if self.watchdog_task_obj is not None:
            self.watchdog_task_obj.cancel()

    def schedule_watchdog(self, loop, period=10.0):
        self.watchdog_period = period
        self.watchdog_task_obj = loop.create_task(self.watchdog_task())

    async def watchdog_task(self):
        ''' Provides a priodic debug view of pending requests and replies '''
        self.logger.info('Start Network Watchdog')
        try:
            while True:
                for k in self.vasp.channel_store:
                    channel = self.vasp.channel_store[k]
                    len_req = len(channel.waiting_requests)
                    len_resp = len(channel.waiting_response)

                    role = ['Client', 'Server'][channel.is_server()]
                    waiting = channel.is_server() \
                        and channel.would_retransmit()
                    me = channel.get_my_address().as_str()
                    other = channel.get_other_address().as_str()

                    len_my = len(channel.my_requests)
                    len_oth = len(channel.other_requests)

                    self.logger.info(
                        f'''
Channel: {me} [{role}] <-> {other}
Queues: my: {len_my} (Wait: {waiting}) other: {len_oth}
Retransmit: {channel.would_retransmit()}
Wait-Req: {len_req} Wait-Resp: {len_resp}''')
                await asyncio.sleep(self.watchdog_period)
        except Exception as e:
            self.logger.error('XXXXXXX')
            self.logger.error(e)
        finally:
            self.logger.info('Stop Network Watchdog')

    def get_url(self, base_url, other_addr_str, other_is_server=False):
        ''' Composes the URL for the Off-chain API VASP end point.'''
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
        ''' Main Http server handler for incomming OffChainAPI requests. '''
        # TODO: Could there be errors when creating LibraAddress?
        other_addr = LibraAddress(request.match_info['other_addr'])
        self.logger.debug(f'Request Received from {other_addr.as_str()}')

        # Try to get a channel with the other VASP.
        try:
            channel = self.vasp.get_channel(other_addr)
        except BusinessNotAuthorized as e:
            # Raised if the other VASP is not an authorised business.
            self.logger.debug(f'Not Authorized {e}')
            raise web.HTTPUnauthorized

        # Verify that the other VASP is authorised to submit the request;
        # ie. that 'other_addr' matches the certificate.
        client_certificate = None  # TODO: Get certificate from ...
        if not self.vasp.info_context.is_authorised_VASP(
            client_certificate, other_addr
        ):
            self.logger.debug(f'Not Authorized')
            raise web.HTTPForbidden

        # Perform the request, send back the reponse.
        try:
            request_json = await request.json()
            # TODO: Handle the timeout error here
            self.logger.debug(f'Data Received from {other_addr.as_str()}')
            response = await channel.parse_handle_request_to_future(
                request_json, encoded=False)

        except json.decoder.JSONDecodeError as e:
            # Raised if the request does not contain valid JSON.
            self.logger.debug(f'Type Error {str(e)}')
            import traceback
            traceback.print_exc()
            raise web.HTTPBadRequest
        except aiohttp.client_exceptions.ContentTypeError as e:
            # Raied when the server replies with wrong content type.
            self.logger.debug(f'ContentTypeError Error {e}')
            import traceback
            traceback.print_exc()
            raise web.HTTPBadRequest

        # Send back the response
        self.logger.debug(f'Process Waiting messages')
        channel.process_waiting_messages()

        self.logger.debug(f'Sending back response to {other_addr.as_str()}')
        return web.json_response(response.content)

    async def send_request(self, other_addr, json_request):
        ''' Uses an HTTP client to send an OffChainAPI request
            to another VASP.

            Parameters:
                * other_addr : The LibraAddress of the other VASP.
                * json_request : a Dict that is a serialized request,
                  ready to be sent across the network.

            Can raise a NetworkException.
            '''
        self.logger.debug(f'Connect to {other_addr.as_str()}')

        # Initialize the client.
        if self.session is None:
            self.session = aiohttp.ClientSession()

        # Try to get a channel with the other VASP.
        channel = self.vasp.get_channel(other_addr)

        base_url = self.vasp.info_context.get_peer_base_url(other_addr)
        url = self.get_url(base_url, other_addr.as_str(), other_is_server=True)
        self.logger.debug(f'Sending post request to {url}')

        try:
            async with self.session.post(url, json=json_request) as response:
                try:
                    json_response = await response.json()
                    self.logger.debug(f'Json response: {json_response}')

                    # Wait in case the requests are sent out of order.
                    res = await channel.parse_handle_response_to_future(
                        json_response, encoded=False)
                    self.logger.debug(f'Response parsed with status: {res}')

                    self.logger.debug(f'Process Waiting messages')
                    channel.process_waiting_messages()
                    return res
                except json.decoder.JSONDecodeError as e:
                    self.logger.debug(f'JSONDecodeError {str(e)}')
                    raise e
                except asyncio.CancelledError as e:
                    raise e
                except Exception as e:
                    self.logger.debug(f'Exception {type(e)}: {str(e)}')
                    raise e
        except ClientError as e:
            raise NetworkException(e)

    def sequence_command(self, other_addr, command):
        ''' Sequences a new command to the local queue, ready to be
            sent to the other VASP.

            Parameters:
                * other_addr : the LibraAddress of the other VASP.
                * command : A ProtocolCommand instance.

            Returns:
                * An instance of a CommandRequestObject
                  representing the command.

            Upon successful completing the sender should call
            `send_request` to actually send the request to the other
            side. However, even if that fails subsequent retrasmissions
            will automatically re-send the request.
         '''

        channel = self.vasp.get_channel(other_addr)
        request = channel.sequence_command_local(command)
        request = request[3]
        return request

    def get_runner(self):
        ''' Gets an object to that needs to be run in an
            event loop to register the server. '''
        return web.AppRunner(self.app)
