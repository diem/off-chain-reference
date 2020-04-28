""" This modules defines the 'core' Off-chain API interface and objects
    to spin an instance of the Off-chain API client and servers. """

from .protocol import OffChainVASP
from .payment_logic import PaymentProcessor
from .storage import StorableFactory
from .asyncnet import Aionet

import asyncio
import logging
from aiohttp import web


class Vasp:
    def __init__(self, my_addr, host, port, business_context,
                 info_context, database):
        ''' Creates a VASP with the standard networking and storage backend.

        Parameters:
            my_addr : a LibraAddress of this VASP
            host    : a domain name for this VASP
            port    : the port on which the server listens
            business_context : The business contraxt of the VASP implementing
                               the BusinessContext interface.
            info_context     : The information context for the VASP
                               implementing the VASPInfo interface.
            database : A persistent key value store to be used by the storage
                       systems as a backend.

        Returns a VASP object.
        '''
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
        self.pp.set_network(self.net_handler)

        # Later init
        self.site = None
        self.loop = None
        self.runner = None

        # Logger
        self.logger = logging.getLogger(f'VASP.{my_addr.as_str()}')

    def start_services(self, loop):
        ''' Registers services with the even loop provided '''
        asyncio.set_event_loop(loop)

        # Assign a loop  to the processor
        self.pp.loop = loop
        self.loop = loop

        # Start the server
        self.runner = self.net_handler.get_runner()
        loop.run_until_complete(self.runner.setup())

        self.site = web.TCPSite(self.runner, self.host, self.port)
        loop.run_until_complete(self.site.start())

        if __debug__:
            # Run the watchdor task to log statistics
            self.net_handler.schedule_watchdog(loop, period=1.0)

    def new_command(self, addr, cmd):
        ''' A synchronous version of `new_command_async`. It sends a new
            command to the other VASP. Returns a concurrent Future object,
            on which the caller can get a result(). '''
        if self.loop is not None:
            res = asyncio.run_coroutine_threadsafe(
                self.new_command_async(addr, cmd), self.loop)
            return res
        else:
            raise RuntimeError('Event loop is None.')

    async def new_command_async(self, addr, cmd):
        ''' Sends a command to the other VASP and returns a boolean
            indicating success or failure of the command. '''
        return await self.net_handler.send_command(addr, cmd)

    async def close_async(self):
        ''' Await this to cleanly close the network
           and any pending commands being processed. '''

        # Close the network
        self.logger.info('Closing the network ...')
        await self.runner.cleanup()
        await self.net_handler.close()

        # Send the cancel signal to all pending tasks
        other_tasks = []
        for T in asyncio.all_tasks():
            # Ignore our own task
            if T == asyncio.current_task():
                continue
            # Cancel and save the task.
            T.cancel()
            other_tasks += [T]

        self.logger.info('Cancelling all tasks ...')
        await asyncio.gather(*other_tasks, return_exceptions=True)

        self.logger.info('Closing loop ...')
        self.loop.stop()
        if self.loop is not None:
            self.loop = None

    def close(self):
        ''' Syncronous and thread safe version of `close_async`. '''
        assert self.loop is not None
        if self.loop is not None:
            res = asyncio.run_coroutine_threadsafe(
                self.close_async(), self.loop)
            res.result()
        else:
            raise RuntimeError('Event loop is None.')
