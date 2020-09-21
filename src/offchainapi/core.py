# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

""" This modules defines the 'core' Off-chain API interface and objects
    to spin an instance of the Off-chain API client and servers. """

from .protocol import OffChainVASP
from .payment_logic import PaymentProcessor
from .storage import StorableFactory
from .asyncnet import Aionet, NetworkException

import asyncio
import logging
from aiohttp import web

logger = logging.getLogger(name='libra_off_chain_api.core')

class VASPPaymentTimeout(Exception):
    pass


class Vasp:
    ''' Creates a VASP with the standard networking and storage backend.

    Parameters:
        my_addr (LibraAddress) : A LibraAddress of this VASP.
        host (str) : A domain name for this VASP.
        port (int) : The port on which the server listens.
        business_context (BusinessContext) : The business context of the VASP
            implementing the BusinessContext interface.
        info_context (VASPInfo) : The information context for the VASP
            implementing the VASPInfo interface.
        database (*) : A persistent key value store to be used
            by the storage systems as a backend.

    Returns a VASP object.
    '''

    def __init__(self, my_addr, host, port, business_context,
                 info_context, database):

        # Initiaize all VASP related objects.
        self.my_addr = my_addr              # Our Address.
        self.host = host                    # Our Host name.
        self.port = port                    # Our server listening port.
        self.bc = business_context          # Our Business Context.
        self.database = database            # A key-value store.
        self.info_context = info_context    # Our info context.

        # Make default storage.
        self.store = StorableFactory(database)
        # Make default PaymentProcessor.
        self.pp = PaymentProcessor(self.bc, self.store)

        # Make root OffChainVasp Object.
        self.vasp = OffChainVASP(
            self.my_addr, self.pp, self.store, self.info_context
        )
        # Make default aiohttp based network.
        self.net_handler = Aionet(self.vasp)
        self.pp.set_network(self.net_handler) # Set handler for processor.

        # Initialize later those ...
        # (When calling `start_services`)
        self.site = None
        self.loop = None
        self.runner = None
        self.all_started_future = None


    def set_loop(self, loop):
        ''' Set the asyncio event loop associated with this VASP.'''
        if self.loop is None:
            self.loop = loop
            self.all_started_future = self.loop.create_future()

    async def _set_start_notifier(self):
        self.all_started_future.set_result(True)

    async def _await_start_notifier(self):
        return await self.all_started_future

    def start_services(self, *, watch_period=10.0):
        ''' Registers services with the even loop provided.

        Parameters:
            loop (asyncio.AbstractEventLoopPolicy): an asyncio event loop on
                which to register services.
            watch_period (float, optional): the time (seconds) beween
                activating the network watchdog to trigger debug info and
                retransmits. Defaults to 10.0.

        '''
        if self.loop is None:
            raise Exception('Missing event loop: set with "set_loop".')

        asyncio.set_event_loop(self.loop)

        # Assign a loop  to the processor.
        self.pp.loop = self.loop

        # Start the http server.
        self.runner = self.net_handler.get_runner()
        self.loop.run_until_complete(self.runner.setup())
        self.site = web.TCPSite(self.runner, self.host, self.port)
        self.loop.run_until_complete(self.site.start())

        # Run the watchdor task to log statistics.
        self.net_handler.schedule_watchdog(self.loop, period=watch_period)

        # Reschedule commands to be processed, when the loop starts.
        self.loop.create_task(self.pp.retry_process_commands())

        # Mechanism to notify the running of loop
        self.loop.create_task(self._set_start_notifier())

    def wait_for_start(self):
        ''' A syncronous function that blocks until the asyncio loop serving the VASP
        is running. It is thread safe, and can therefore be called from another thread
        than the one where the asyncio loop is running.'''
        result = asyncio.run_coroutine_threadsafe(
            self._await_start_notifier(), self.loop)
        return result.result()

    async def wait_for_payment_outcome_async(self, payment_reference_id, timeout=None):
        ''' Awaits until the payment with the given reference_id is
        ready_for_settlement or aborted and returns the payment object
        at that version.

        Parameters:
            payment_reference_id (str): the reference_id of the payment
                of interest.
            timeout (float, or None by default): second until timeout.

        Returns a PaymentObject with the given reference_id that is ether
        ready_for_settlement or aborted by one of the parties.

        '''
        try:
            payment = await asyncio.wait_for(
                self.pp.wait_for_payment_outcome(payment_reference_id),
                timeout)
        except asyncio.TimeoutError:
            print(f'Timeout for payment {payment_reference_id}')
            latest_version = self.get_payment_by_ref(payment_reference_id)
            print('Pay:', latest_version)
            raise VASPPaymentTimeout(latest_version)

        return payment

    def wait_for_payment_outcome(self, payment_reference_id, timeout):
        ''' A non-async variant of wait_for_payment_outcome_async that returns
        a concurrent.futures Future with the result. You may call `.result()`
        on it to block or register a call-back. '''
        if self.loop is not None:
            res = asyncio.run_coroutine_threadsafe(
                self.wait_for_payment_outcome_async(payment_reference_id, timeout), self.loop)
            return res
        else:
            raise RuntimeError('Event loop is None.')

    async def new_command_async(self, addr, cmd):
        ''' Sends a new command to the other VASP and returns a
            boolean indicating success or failure of the command,
            or a request in case of a network falure.

            Parameters:
                addr (LibraAddress) : The address of the VASP to which to
                    send the command.
                cmd (PaymentCommand) : A payment command instance.

            Returns:
                In case of no failure it returns
                a Bool indicating whether the sequenced command was
                successful or not. OR In case of a network failure
                returns an instance of a CommandRequestObject represented
                as a json dict that can be retransmitted.

            Note that the automatic retransmission will eventually re-sent
            the request until progress is made.
            '''
        req = await self.net_handler.sequence_command(addr, cmd)
        try:
            return await self.net_handler.send_request(addr, req)
        except NetworkException:
            return req

    def new_command(self, addr, cmd):
        """ A synchronous version of `new_command_async`. It sends a new
            command to the other VASP. Returns a concurrent Future object,
            on which the caller can get a result().

            Args:
                addr (LibraAddress): The address of the VASP to which to
                                    send the command.
                cmd (PaymentCommand): A payment command instance.

            Raises:
                RuntimeError: If the Event loop is None.

            Returns:
                bool or CommandRequestObject: In case of no failure it returns
                a Bool indicating whether
                the sequenced command was successful or not.
                OR In case of a network failure returns an instance of
                a CommandRequestObject represented as a json dict that
                can be retransmitted.
        """
        if self.loop is not None:
            res = asyncio.run_coroutine_threadsafe(
                self.new_command_async(addr, cmd), self.loop)
            return res
        else:
            raise RuntimeError('Event loop is None.')

    def get_payment_by_ref(self, reference_id):
        """ Returns the latest version of the PaymentObject
            with the given reference ID.

            Parameters:
                reference_id (str): The reference ID of a payment.

            Returns:
                PaymentObject: A PaymentObject with the reference ID given.

            Raises:
                KeyError: In case a payment with the given reference
                    does not exist.
        """
        payment = self.pp.get_latest_payment_by_ref_id(reference_id)
        return payment

    def get_payment_history_by_ref(self, reference_id):
        """ Returns a list of versions of the PaymentObjects
            with the given reference ID.

            Parameters:
                reference_id (str): The reference ID of a payment.

            Returns:
                List of PaymentObject: A list of PaymentObject versions
                in reverse causal order (newest first) with the same
                reference ID given.

            Raises:
                KeyError: In case a payment with the given reference
                    does not exist.
        """
        payment = list(self.pp.get_payment_history_by_ref_id(reference_id))
        return payment

    async def close_async(self):
        ''' Await this to cleanly close the network
           and any pending commands being processed. '''

        # Close the network
        logger.info('Closing the network ...')
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

        logger.info('Cancelling all tasks ...')
        await asyncio.gather(*other_tasks, return_exceptions=True)

        logger.info('Closing loop ...')
        self.loop.stop()
        if self.loop is not None:
            self.loop = None

    def close(self):
        ''' Syncronous and thread safe version of `close_async`.

            Raises:
                RuntimeError: If the Event loop is None.
        '''
        assert self.loop is not None
        if self.loop is not None:
            res = asyncio.run_coroutine_threadsafe(
                self.close_async(), self.loop)
            res.result()
        else:
            raise RuntimeError('Event loop is None.')
