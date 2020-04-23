""" This modules defines the 'core' Off-chain API interface and objects
    to spin an instancee of the Off-chain API client and servers. """

from .business import BusinessContext, BusinessForceAbort, \
BusinessValidationFailure, VASPInfo
from .protocol import OffChainVASP
from .libra_address import LibraAddress
from .protocol_messages import CommandRequestObject
from .payment_logic import PaymentCommand, PaymentProcessor
from .status_logic import Status
from .storage import StorableFactory
from .payment import PaymentAction, PaymentActor, PaymentObject
from .asyncnet import Aionet

import logging
logging.basicConfig(level=logging.ERROR)

import json
from unittest.mock import MagicMock
from threading import Thread
import time
import asyncio
from aiohttp import web

class Vasp:
    def __init__(self, my_addr, host, port, business_context, info_context, database):
        self.my_addr = my_addr
        self.host = host
        self.port = port
        self.bc = business_context
        self.store = StorableFactory({})
        self.info_context = info_context
        self.pp = PaymentProcessor(self.bc, self.store)
        self.vasp = OffChainVASP(
            self.my_addr, self.pp, self.store, self.info_context
        )
        self.net_handler = Aionet(self.vasp)

        # Later init
        self.site = None

    def start_services(self, loop):
        # Start the processor
        self.pp.loop = loop

        # Start the server
        runner = self.net_handler.get_runner()
        #
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())

        self.site = web.TCPSite(runner, self.host, self.port)
        loop.run_until_complete(self.site.start())

    def new_command(self, addr, cmd):
        pass

    async def new_command_async(self, addr, cmd):
        return await self.net_handler.send_command(addr, cmd)

    async def close_async(self):
        pass

    def close(self):
        pass
