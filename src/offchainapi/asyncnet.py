# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .business import BusinessNotAuthorized
from .libra_address import LibraAddress
from .utils import get_unique_string

import aiohttp
from aiohttp import web
from aiohttp.client_exceptions import ClientError
import asyncio
import logging
from urllib.parse import urljoin
import json


logger = logging.getLogger(name='libra_off_chain_api.asyncnet')


class NetworkException(Exception):
    pass


class Aionet:
    """A network client and server using aiohttp. Initialize
    the network system with a OffChainVASP instance.

    Args:
        vasp (OffChainVASP): The  OffChainVASP instance.
    """

    def __init__(self, vasp):
        self.vasp = vasp

        # For the moment hold one session per VASP.
        self.session = None
        self.app = web.Application()

        # Register routes.
        route = self.get_url('/', '{other_addr}')
        self.app.add_routes([web.post(route, self.handle_request)])
        logger.debug(f'Register route {route}')

        if __debug__:
            self.app.add_routes([
                web.post('/', self.handle_request_debug),
                web.get('/', self.handle_request_debug)
            ])

        # The watchdog process variables.
        self.watchdog_period = 10.0  # seconds
        self.watchdog_task_obj = None  # Store the task here to cancel.

    async def close(self):
        ''' Close the open Http client session and the network object. '''
        if self.session is not None:
            session = self.session
            self.session = None
            await session.close()

        if self.watchdog_task_obj is not None:
            self.watchdog_task_obj.cancel()

    def schedule_watchdog(self, loop, period=10.0):
        """ Creates and schedues the watchdog periodic process.
        It logs basic statistics for all channels and retransmits.

        Args:
            loop (asyncio.AbstractEventLoopPolicy): The event loop.
            period (float, optional): The refresh period in seconds.
                Defaults to 10.0.
        """
        self.watchdog_period = period
        self.watchdog_task_obj = loop.create_task(self.watchdog_task())

    async def watchdog_task(self):
        ''' Provides a priodic debug view of pending requests and replies. '''
        logger.info('Start Network Watchdog.')
        try:
            while True:
                for k in self.vasp.channel_store:
                    channel = self.vasp.channel_store[k]

                    role = ['Client', 'Server'][channel.is_server()]
                    waiting = channel.is_server() \
                        and channel.would_retransmit()
                    me = channel.get_my_address().as_str()
                    other = channel.get_other_address().as_str()
                    # TODO: Retransmit a few of the requests here.

                    len_my = len(channel.my_request_index)

                    logger.info(
                        f'''
                        Channel: {me} [{role}] <-> {other}
                        Queues: my: {len_my} (Wait: {waiting})
                        Retransmit: {channel.would_retransmit()}'''
                    )
                await asyncio.sleep(self.watchdog_period)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error('Watchdog exception', exc_info=True)
        finally:
            logger.info('Stop Network Watchdog')

    def get_url(self, base_url, other_addr_str, other_is_server=False):
        """Composes the URL for the Off-chain API VASP end point.

        Args:
            base_url (str): The base url.
            other_addr_str (str): The address of the other VASP as a string.
            other_is_server (bool, optional): Whether the other VASP is the
                server. Defaults to False.

        Returns:
            str: The complete URL for the Off-chain API VASP end point
        """
        if other_is_server:
            server = other_addr_str
            client = self.vasp.get_vasp_address().as_str()
        else:
            server = self.vasp.get_vasp_address().as_str()
            client = other_addr_str
        url = f'v1/{server}/{client}/command/'
        full_url = urljoin(base_url, url)
        return full_url

    if __debug__:
        async def handle_request_debug(self, request):
            return web.Response(text='Hello, world')

    async def handle_request(self, request):
        """ Main Http server handler for incomming OffChainAPI requests.

        Args:
            request (aiohttp.web.Request): The request from the other VASP.

        Raises:
            aiohttp.web.HTTPUnauthorized: An exception for 401 Unauthorized.
            aiohttp.web.HTTPForbidden: An exception for 403 Forbidden.
            aiohttp.web.HTTPBadRequest: An exception for 400 Bad Request.

        Returns:
            aiohttp.web.Response: A json response with predefined
            'application/json' content type and data encoded by json.dumps.
        """

        other_addr = LibraAddress.from_encoded_str(request.match_info['other_addr'])
        logger.debug(f'Request Received from {other_addr.as_str()}')

        # Check and extract '
        if 'X-Request-ID' not in request.headers:
            raise web.HTTPBadRequest(headers={'X-Request-ID': 'None'})
        x_request_id = request.headers['X-Request-ID']
        headers = {'X-Request-ID': x_request_id}

        # Try to get a channel with the other VASP.
        try:
            channel = self.vasp.get_channel(other_addr)
        except BusinessNotAuthorized as e:
            # Raised if the other VASP is not an authorised business.
            logger.debug(f'Not Authorized', exc_info=True)
            raise web.HTTPUnauthorized(headers=headers)

        # Perform the request, send back the reponse.
        try:
            request_json = await request.json()

            # TODO: Handle timeout errors here.
            logger.debug(f'Data Received from {other_addr.as_str()}.')
            response = channel.parse_handle_request(request_json)

        except json.decoder.JSONDecodeError as e:
            # Raised if the request does not contain valid json.
            logger.debug(f'JSONDecodeError', exc_info=True)
            raise web.HTTPBadRequest(headers=headers)

        except aiohttp.client_exceptions.ContentTypeError as e:
            # Raised when the server replies with wrong content type;
            # eg. text/html instead of json.
            logger.debug(f'ContentTypeError', exc_info=True)
            raise web.HTTPBadRequest(headers=headers)

        # Send back the response.
        logger.debug(f'Process Waiting messages.')
        logger.debug(f'Sending back response to {other_addr.as_str()}.')
        return web.json_response(response.content, headers=headers)

    async def send_request(self, other_addr, json_request):
        """ Uses an Http client to send an OffChainAPI request to another VASP.

        Args:
            other_addr (LibraAddress): The LibraAddress of the other VASP.
            json_request (dict): a Dict that is a serialized request,
                ready to be sent across the network.

        Raises:
            NetworkException: [description]
        """

        logger.debug(f'Connect to {other_addr.as_str()}')

        # Initialize the client.
        if self.session is None:
            self.session = aiohttp.ClientSession()

        # Try to get a channel with the other VASP.
        channel = self.vasp.get_channel(other_addr)

        # Get the URLs
        base_url = self.vasp.info_context.get_peer_base_url(other_addr)
        url = self.get_url(base_url, other_addr.as_str(), other_is_server=True)
        logger.debug(f'Sending post request to {url}')

        # Add a custom request header
        headers = {'X-Request-ID': get_unique_string()}

        try:
            async with self.session.post(
                    url,
                    json=json_request,
                    headers=headers
            ) as response:
                try:
                    # Check the header is correct
                    if 'X-Request-ID' not in response.headers or \
                            response.headers['X-Request-ID'] != headers['X-Request-ID']:
                        raise Exception(
                            'Incorrect X-Request-ID header:', response.headers
                        )

                    json_response = await response.json()
                    logger.debug(f'Json response: {json_response}')

                    # Wait in case the requests are sent out of order.
                    res = channel.parse_handle_response(json_response)
                    logger.debug(f'Response parsed with status: {res}')

                    logger.debug(f'Process Waiting messages')
                    return res
                except json.decoder.JSONDecodeError as e:
                    logger.debug(f'JSONDecodeError', exc_info=True)
                    raise e
                except asyncio.CancelledError as e:
                    raise e
                except Exception as e:
                    logger.debug(f'Exception: {type(e)}', exc_info=True)
                    raise e
        except ClientError as e:
            logger.debug(f'ClientError {type(e)}: {e}')
            raise NetworkException(e)

    def sequence_command(self, other_addr, command):
        ''' Sequences a new command to the local queue, ready to be
            sent to the other VASP.

            other_addr (LibraAddress) : the LibraAddress of the other VASP.
            command (ProtocolCommand) : A ProtocolCommand instance.

            Returns:
                str: json str of the net message
        '''

        channel = self.vasp.get_channel(other_addr)
        request = channel.sequence_command_local(command)
        request = channel.package_request(request)
        request = request.content
        return request

    def get_runner(self):
        ''' Gets an object to that needs to be run in an
            event loop to register the server.

            Returns:
                aiohttp.web.AppRunner: A runner for Application.

        '''
        return web.AppRunner(self.app)
