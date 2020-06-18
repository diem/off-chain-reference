# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .executor import ProtocolExecutor, ExecutorException, CommandProcessor
from .protocol_messages import CommandRequestObject, CommandResponseObject, \
    OffChainProtocolError, OffChainOutOfOrder, OffChainException, \
    make_success_response, make_protocol_error, \
    make_parsing_error, make_command_error
from .utils import JSONParsingError, JSONFlag
from .libra_address import LibraAddress
from .crypto import OffChainInvalidSignature

import json
from collections import namedtuple, defaultdict
from threading import RLock
import logging
import asyncio
import time

""" A Class to store messages meant to be sent on a network. """
NetMessage = namedtuple('NetMessage', ['src', 'dst', 'type', 'content'])

logger = logging.getLogger(name='libra_off_chain_api.protocol')


class OffChainVASP:
    """ Manages the off-chain protocol on behalf of one VASP.

    Args:
        vasp_addr (LibraAddress): The address of the VASP.
        processor (CommandProcessor): The command processor.
        storage_factory (StorableFactory): The storage factory.
        info_context (VASPInfo): The information context for the VASP
                                 implementing the VASPInfo interface.
    """

    def __init__(self, vasp_addr, processor, storage_factory, info_context):
        logger.debug(f'Creating VASP {vasp_addr.as_str()}')

        assert isinstance(processor, CommandProcessor)
        assert isinstance(vasp_addr, LibraAddress)

        # The LibraAddress of the VASP.
        self.vasp_addr = vasp_addr
        # The business context provided by the processor.
        self.business_context = processor.business_context()

        # The command processor that checks and processes commands.
        # We attach the notify member to this class to trigger
        # processing of resumed commands.
        self.processor = processor

        # The VASPInfo context that contains various network information
        # such as TLS certificates and keys.
        self.info_context = info_context

        # The dict of channels we already have.
        self.channel_store = {}

        # Manage storage.
        self.storage_factory = storage_factory

    def get_vasp_address(self):
        """Return our own VASP Libra Address.

        Returns:
            LibraAddress: The VASP's address.
        """
        return self.vasp_addr

    def get_channel(self, other_vasp_addr):
        ''' Returns a VASPPairChannel with the other VASP.

        Parameters:
            other_vasp_addr (LibraAddress): The address of the other VASP.

        Returns:
            VASPPairChannel: A channel with the other VASP.

        '''
        self.business_context.open_channel_to(other_vasp_addr)
        my_address = self.get_vasp_address()
        store_key = (my_address, other_vasp_addr)

        if store_key not in self.channel_store:
            channel = VASPPairChannel(
                my_address,
                other_vasp_addr,
                self,
                self.storage_factory,
                self.processor
            )
            self.channel_store[store_key] = channel

        return self.channel_store[store_key]

    def get_storage_factory(self):
        """Returns a storage factory for this system.

        Returns:
            StorableFactory: The storage factory of the VASP.
        """
        return self.storage_factory


class VASPPairChannel:
    """ Represents the state of an off-chain bi-directional
        channel bewteen two VASPs.

    Args:
        myself (LibraAddress): The address of the current VASP.
        other (LibraAddress): The address of the other VASP.
        vasp (OffChainVASP): The OffChainVASP to which this channel is attached.
        storage (StorageFactory): The storage factory.
        processor (CommandProcessor): A command processor.

    Raises:
        OffChainException: If the channel is not talking to another VASP.
    """

    def __init__(self, myself, other, vasp, storage, processor):

        assert isinstance(myself, LibraAddress)
        assert isinstance(other, LibraAddress)
        assert isinstance(processor, CommandProcessor)
        assert isinstance(vasp, OffChainVASP)

        # State that is given by constructor.
        self.myself = myself
        self.other = other
        self.other_address_str = self.other.as_str()
        self.processor = processor
        self.vasp = vasp
        self.storage = storage

        # Check we are not making a channel with ourselves.
        if self.myself.as_str() == self.other_address_str:
            raise OffChainException(
                'Must talk to another VASP:',
                self.myself.as_str(),
                self.other_address_str
            )

        # A reentrant lock to manage access.
        self.rlock = RLock()

        # State that is persisted.

        root = self.storage.make_value(self.myself.as_str(), None)
        other_vasp = self.storage.make_value(
            self.other_address_str, None, root=root
        )

        with self.storage.atomic_writes() as _:

            # The list of requests I have initiated.
            self.my_requests = self.storage.make_list(
                'my_requests', CommandRequestObject, root=other_vasp
            )

            # The list of requests the other side has initiated.
            self.other_requests = self.storage.make_list(
                'other_requests', CommandRequestObject, root=other_vasp
            )

            # The index of the next request from my sequence that I should
            # retransmit (ie. for which I have not got a response yet.).
            self.next_retransmit = self.storage.make_value(
                'next_retransmit', int, root=other_vasp, default=0
            )

            # The final sequence
            self.executor = ProtocolExecutor(self, self.processor)

        # Ephemeral state that can be forgotten upon a crash.

        # Keep track of object locks
        self.object_locks = {}

        # Request / response cache to allow reordering.
        self.waiting_requests = defaultdict(list)
        self.request_window = 1000
        self.waiting_response = defaultdict(list)
        self.response_window = 1000

        # Network handler
        self.net_queue = []

        logger.debug(f'(other:{self.other_address_str}) Created VASP channel')

    def my_next_seq(self):
        """
        Returns:
            int: The next request sequence number for this VASP.
        """
        return len(self.my_requests)

    def other_next_seq(self):
        """
        Returns:
            int: The next request sequence number for the other VASP.
        """
        return len(self.other_requests)

    def get_my_address(self):
        """
        Returns:
            LibraAddress: The address of this VASP.
        """
        return self.myself

    def get_other_address(self):
        """
        Returns:
            LibraAddress: The address of the other VASP.
        """
        return self.other

    def get_vasp(self):
        """
        Returns:
            OffChainVASP: The OffChainVASP to which this channel is attached.
        """
        return self.vasp

    # Define a stub here to make the linter happy
    if __debug__:
        def tap(self):
            return []

    def next_final_sequence(self):
        """
        Returns:
            int: The next sequence number in the common sequence.
        """
        return self.executor.next_seq()

    def get_final_sequence(self):
        """
        Returns:
            list: The list of commands in the common sequence.
        """
        return self.executor.command_sequence

    def send_request(self, request):
        """ A hook to send a request to other VASP.

        Args:
            request (CommandRequestObject): The request object.

        Returns:
            NetMessage: The message to be sent on a network.
        """
        json_dict = request.get_json_data_dict(JSONFlag.NET)

        # Make signature.
        vasp = self.get_vasp()
        my_key = vasp.info_context.get_peer_compliance_signature_key(
            self.get_my_address().as_str()
        )
        json_string = my_key.sign_message(json.dumps(json_dict))

        net_message = NetMessage(
            self.myself,
            self.other,
            CommandRequestObject,
            json_string
        )

        # Only used in unit tests.
        if __debug__:
            self.net_queue += [net_message]

        return net_message

    def send_response(self, response):
        """ A hook to send a response to other VASP.

        Args:
            response (CommandResponseObject): The request object.

        Returns:
            NetMessage: The message to be sent on a network.
        """
        struct = response.get_json_data_dict(JSONFlag.NET)

        # Sign response
        my_key = self.get_vasp().info_context.get_peer_compliance_signature_key(
            self.get_my_address().as_str()
        )
        signed_response = my_key.sign_message(json.dumps(struct))

        net_message = NetMessage(
            self.myself, self.other, CommandResponseObject, signed_response
        )
        if __debug__:
            self.net_queue += [net_message]
        return net_message

    def is_client(self):
        """
        Returns:
            bool: Whether the local VASP the client for this pair.
        """
        myself_address = self.myself
        other_address = self.other

        # Write out the logic, for clarity
        bit = myself_address.last_bit() ^ other_address.last_bit()
        if bit == 0:
            return myself_address.greater_than_or_equal(other_address)
        if bit == 1:
            return not myself_address.greater_than_or_equal(other_address)
        assert False  # Never reach this code

    def role(self):
        """ The role of the VASP as a string. For debug output.

        Returns:
            str: The role of the VASP.
        """
        return ['Server', 'Client'][self.is_client()]

    def is_server(self):
        """
         Returns:
             bool: Whether the local VASP the server for this pair.
         """
        return not self.is_client()

    def num_pending_responses(self):
        """
        Returns:
            int: The number of responses this VASP is waiting for.
        """
        return len([1 for req in self.my_requests if not req.has_response()])

    def has_pending_responses(self):
        """
        Returns:
            bool: Whether this VASP has pending responses to retransmit.
        """
        return self.would_retransmit()

    def apply_response_to_executor(self, request):
        """Signals to the executor the success or failure of a command.

        Args:
            request (CommandRequestObject): The request object.
        """
        assert request.response is not None
        response = request.response
        if request.is_success():
            self.executor.set_success(response.command_seq)
        else:
            self.executor.set_fail(response.command_seq, response.error)

    def sequence_command_local(self, off_chain_command):
        """The local VASP attempts to sequence a new off-chain command.

        Args:
            off_chain_command (PaymentCommand): The command to sequence.

        Returns:
            NetMessage: The message to be sent on a network.
        """

        off_chain_command.set_origin(self.get_my_address())
        request = CommandRequestObject(off_chain_command)

        # Ensure all storage operations are written atomically.
        with self.rlock:
            with self.storage.atomic_writes() as _:
                request.seq = self.my_next_seq()

                if self.is_server():
                    request.command_seq = self.next_final_sequence()
                    # Raises and exits on error -- does not sequence.
                    self.executor.sequence_next_command(
                        off_chain_command,
                        do_not_sequence_errors=True
                    )

                self.my_requests += [request]

        # Send the requests outside the locks to allow
        # for an asyncronous implementation.
        return self.send_request(request)

    def parse_handle_request(self, json_command):
        """ Handles a request provided as a json string or dict.

        Args:
            json_command (str or dict): The json request.

        Returns:
            NetMessage: The message to be sent on a network.
        """
        loop = asyncio.new_event_loop()
        fut = self.parse_handle_request_to_future(
            json_command, nowait=True, loop=loop
        )
        return fut.result()

    def process_waiting_messages(self):
        ''' Executes any requets that are now capable of executing, and were
            not before due to being received out of order. '''

        logger.debug(
            f'(other:{self.other_address_str}) '
            f'Processing waiting messages: '
            f'remote Seq {self.other_next_seq()}, '
            f'command Seq #{self.next_final_sequence()}, '
            f'last Confirmed: {self.executor.last_confirmed}, ',
        )

        while self.executor.last_confirmed in self.waiting_response:
            next_cmd_seq = self.executor.last_confirmed

            logger.debug(
                f'(other:{self.other_address_str}) '
                f'Activate response to #{next_cmd_seq}',
            )

            # Take a copy of the pending responses.
            list_of_responses = self.waiting_response[next_cmd_seq]
            del self.waiting_response[next_cmd_seq]

            for resp_record in list_of_responses:
                (json_command, fut) = resp_record
                _ = self.parse_handle_response_to_future(json_command, fut)

            # Break if we made no progress.
            if next_cmd_seq == self.executor.last_confirmed:
                break

        while self.other_next_seq() in self.waiting_requests:
            next_seq = self.other_next_seq()
            logger.debug(
                f'(other:{self.other_address_str}) '
                f'Activate request to other next seq: #{next_seq}',
            )

            # Take a copy of the pending requests.
            list_of_requests = self.waiting_requests[next_seq]
            del self.waiting_requests[next_seq]

            for req_record in list_of_requests:
                (json_command, fut, old_time) = req_record

                # Call, and this will update the future and unblocks
                # any processes waiting on it.
                _ = self.parse_handle_request_to_future(json_command, fut)

            # Break if no progress is made.
            if next_seq == self.other_next_seq():
                break

    def parse_handle_request_to_future(
        self, json_command, fut=None, nowait=False, loop=None
    ):
        """ Handles a request provided as a json string or dict and returns
            a future that triggers when the command is processed.

        Args:
            json_command (str or dict): The json request.
            fut (asyncio.Future, optional): The future. Defaults to None.
            nowait (bool, optional): Whether to feed requests commands even
                  out of order without waiting. Defaults to False.
            loop (asyncio.AbstractEventLoopPolicy, optional): The event loop
                  to use. Defaults to None.

        Returns:
            asyncio.Future: A future to A NetMessage instance containing the
                  response to the request.
        """

        if fut is None:
            fut = asyncio.Future(loop=loop)
        else:
            # If we are passed a future that is done, we just return it
            # since there is nothing more to do.
            if fut.done():
                return fut

        try:
            # Check signature
            vasp = self.get_vasp()
            other_key = vasp.info_context.get_peer_compliance_verification_key(
                self.get_other_address().as_str()
            )
            request = json.loads(other_key.verify_message(json_command))

            # Parse the request whoever necessary.
            request = CommandRequestObject.from_json_data_dict(
                request, JSONFlag.NET
            )

            with self.rlock:
                # Going ahead to process the request.
                logger.debug(
                    f'(other:{self.other_address_str}) '
                    f'Processing request seq #{request.seq}',
                )
                response = self.handle_request(request, raise_on_wait=True)

        except OffChainInvalidSignature as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'Signature verification failed. OffChainInvalidSignature: {e}',
            )
            # TODO: Package proper exception
            fut.set_result('Signature verification failed.')
            return fut

        except OffChainOutOfOrder as e:
            if nowait:
                # No waiting -- so bubble up the potocol error response.
                logger.info(
                    f'(other:{self.other_address_str}) '
                    f'Request OutOfOrder and no wait',
                )
                response = e.args[0]
            else:
                # We were told to wait for this requests turn.
                logger.info(
                    f'(other:{self.other_address_str}) '
                    f'Request OutOfOrder, add to waiting requests',
                )
                self.waiting_requests[request.seq] += [(
                    json_command, fut, time.time()
                )]
                return fut
        except JSONParsingError as e:
            logger.error(
                f'(other:{self.other_address_str}) JSONParsingError: {e}',
                exc_info=True,
            )
            response = make_parsing_error()
        except Exception as e:
            logger.error(
                f'(other:{self.other_address_str}) exception: {e}',
                exc_info=True,
            )
            fut.set_exception(e)
            return fut

        # Prepare the response.
        full_response = self.send_response(response)
        fut.set_result(full_response)
        return fut

    def handle_request(self, request, raise_on_wait=False):
        """ Handles a request provided as a dictionary. (see `_handle_request`)
        """
        with self.storage.atomic_writes() as _:
            return self._handle_request(request, raise_on_wait)

    def _handle_request(self, request, raise_on_wait):
        """ Handles a request provided as a dictionary.

        Args:
            request (CommandRequestObject): The request.
            raise_on_wait (bool, optional): Whether to raise OffChainOutOfOrder
                when we cannot generate a response before sequencing previous
                commands. Defaults to False.

        Raises:
            OffChainOutOfOrder: In case the response is out of order
                (due to nowait=True).

        Returns:
            CommandResponseObject: The response to the VASP's request.
        """
        request.command.set_origin(self.other)


        # Keep track of object locks here.

        #create_versions = request.command.new_object_versions()
        #depends_on_version = request.command.get_dependencies()

        #if all(v in self.object_locks for v in create_versions):
        #    # Command already processed.
        #    print('Processed')
        #
        # if any(v not in self.object_locks for v in depends_on_version):
        #     print('Missing dependencies')
        #     print(depends_on_version, self.object_locks)
        # else:
        #     print('Go ahead wrt dependencies')

        # Always answer old requests.
        other_next_seq = self.other_next_seq()
        if request.seq < other_next_seq:
            previous_request = self.other_requests[request.seq]
            if previous_request.is_same_command(request):
                # Re-send the response.
                logger.debug(
                    f'(other:{self.other_address_str}) '
                    f'Handle request that alerady has a response: '
                    f'seq #{request.seq}, other next #{other_next_seq}',
                )
                return previous_request.response
            else:
                # There is a conflict, and it will have to be resolved
                # TODO[issue 8]: How are conflicts meant to be resolved?
                # With only two participants we cannot tolerate errors.
                response = make_protocol_error(request, code='conflict')
                response.previous_command = previous_request.command
                logger.error(
                    f'(other:{self.other_address_str}) '
                    f'Conflicting requests for seq {request.seq}',
                )
                return response

        # Clients are not to suggest sequence numbers.
        if self.is_server() and request.command_seq is not None:
            response = make_protocol_error(request, code='malformed')
            return response

        # As a server we first wait for the status of all server
        # requests to sequence any new client requests.
        # We also wait to acknowledge previous requests before
        # acknowledging the next ones.
        if self.is_server() and self.has_pending_responses() \
                or request.seq > self.other_next_seq():
            logger.info(
                f'(other:{self.other_address_str}) '
                f'Request OutOfOrder! I am server, has pending responses: '
                f'{self.has_pending_responses()}, req.seq: #{request.seq} '
                f'other next seq: #{self.other_next_seq()}',
            )
            response = make_protocol_error(request, code='wait')
            if raise_on_wait:
                raise OffChainOutOfOrder(response)
            return response

        # Sequence newer requests.
        assert request.seq == self.other_next_seq()
        assert (self.is_server() and request.command_seq is None) \
            or (self.is_client() and request.command_seq is not None)

        if self.is_client() \
                and request.command_seq != self.next_final_sequence():
            # We must wait, since we cannot give an answer
            # before sequencing previous commands.
            logger.info(
                f'(other:{self.other_address_str}) '
                f'Request OutOfOrder! I am client: req.com_seq: '
                f'{request.command_seq}, next final seq: '
                f'{self.next_final_sequence()}',
            )
            response = make_protocol_error(request, code='wait')
            if raise_on_wait:
                raise OffChainOutOfOrder(response)
            return response

        # What is the sequence of this request.
        # Either given by the server to the client, or made by the server.
        # Due to the guard conditions above this will always
        # be self.next_final_sequence().
        seq = self.next_final_sequence()

        try:
            self.executor.sequence_next_command(
                request.command,
                do_not_sequence_errors=False
            )
            response = make_success_response(request)
        except ExecutorException as e:
            response = make_command_error(request, str(e))

        # Write back to storage
        request.response = response
        request.response.command_seq = seq
        self.other_requests += [request]
        self.apply_response_to_executor(request)
        self.register_deps(request)

        return request.response

    def register_deps(self, request):
        # Keep track of object locks here.
        create_versions = request.command.new_object_versions()
        depends_on_version = request.command.get_dependencies()

        if request.response.status == 'success':
            # print(f'Deps: {depends_on_version}')
            assert all(v in self.object_locks for v in depends_on_version)

            for dv in depends_on_version:
                self.object_locks[dv] = False
                # print(f'Set: {dv} <- False')

            for cv in create_versions:
                self.object_locks[cv] = True
                # print(f'Set: {cv} <- True')

            # print(f'final locks: {self.object_locks}')


    def parse_handle_response(self, json_response):
        """ Handles a response as json string or dict.

        Args:
            json_response (str or dict): The json response.

        Returns:
            bool: Whether the command was a success or not
        """
        loop = asyncio.new_event_loop()
        fut = self.parse_handle_response_to_future(
            json_response, nowait=True, loop=loop
        )
        return fut.result()

    def parse_handle_response_to_future(
        self, json_response, fut=None, nowait=False, loop=None
    ):
        """ Handles a response provided as a json string. Returns a future
            that fires when the response is processed. You may `await` this
            future from an asyncio coroutine.

        Args:
            json_response (dict or str): The json response.
            fut (asyncio.Future, optional): The future. Defaults to None.
            nowait (bool, optional): Whether to wait for the reponse to be in
                order to feed it directly to the protocol state machine.
                Defaults to False.
            loop (asyncio.AbstractEventLoopPolicy, optional): the event loop
                in which this is executed. Defaults to None.

        Returns:
            bool: Whether the command was a success or not (Command error).
        """
        if fut is None:
            fut = asyncio.Future(loop=loop)

        try:
            vasp = self.get_vasp()
            other_key = vasp.info_context.get_peer_compliance_verification_key(
                self.get_other_address().as_str()
            )
            response = json.loads(other_key.verify_message(json_response))
            response = CommandResponseObject.from_json_data_dict(
                response, JSONFlag.NET
            )
            command_seq = response.command_seq

            with self.rlock:
                result = self.handle_response(response)
            fut.set_result(result)

        except OffChainInvalidSignature as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'Signature verification failed. OffChainInvalidSignature: {e}',
            )
            # TODO: Package proper exception
            fut.set_result('Signature verification failed.')
        except JSONParsingError as e:
            logger.warning(
                f'(other:{self.other_address_str}) JSONParsingError: {e}'
            )
            fut.set_exception(e)
        except OffChainOutOfOrder as e:
            # If we were told to not wait, raise this.
            if nowait:
                logger.info(
                    f'(other:{self.other_address_str}) '
                    f'response OutofOrder and no wait. OffChainOutOfOrder: {e}',
                )
                fut.set_exception(e)
            else:
                logger.info(
                    f'(other:{self.other_address_str}) '
                    f'response OutOfOrder, adding a waiting response. Exception: {e}',
                )
                # Otherwise wait for longer.
                self.waiting_response[command_seq] += [(json_response, fut)]
        except OffChainException or OffChainProtocolError as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'OffChainException/OffChainProtocolError: {e}',
            )
            fut.set_exception(e)
        except ExecutorException as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'ExecutorException: {e}',
            )
            fut.set_exception(e)

        return fut

    def handle_response(self, response):
        """ Handles a response provided as a dictionary. See `_handle_response`
        """
        with self.storage.atomic_writes() as _:
            return self._handle_response(response)

    def _handle_response(self, response):
        """ Handles a response provided as a dictionary.

        Args:
            response (CommandResponseObject): The response.

        Raises:
            OffChainProtocolError: On protocol error.
            OffChainException: On an unrecoverabe error.
            ExecutorException: Can happy if the other VASP is buggy.

        Returns:
            bool: Whether the response is successfully sequenced.
        """
        assert isinstance(response, CommandResponseObject)

        # Is there was a protocol error return the error.
        if response.is_protocol_failure():
            raise OffChainProtocolError.make(response.error)

        if type(response.seq) is not int:
            raise OffChainException(
                f'Response seq must be int not '
                f'{response.seq} ({type(response.seq)})'
            )

        request_seq = response.seq

        # Check this is the next expected response.
        my_next_seq = self.my_next_seq()
        if request_seq >= my_next_seq:
            raise OffChainException(
                f'Response for seq {request_seq} received, '
                f'but has requests only up to seq < {my_next_seq}'
            )

        # Idenpotent: We have already processed the response.
        request = self.my_requests[request_seq]
        if request.has_response():
            # Check the reponse is the same and log warning otherwise.
            if request.response != response:
                excp = OffChainException(
                    'Got duplicate but different responses.'
                )
                excp.response1 = request.response
                excp.response2 = response
                raise excp
            # this request may have concurrent modification
            # read db to get latest status
            return self.my_requests[request_seq].is_success()

        # This is too high -- wait for more data.
        next_final_sequence = self.next_final_sequence()
        last_confirmed = self.executor.last_confirmed
        if response.command_seq > next_final_sequence \
                or (response.command_seq != last_confirmed):
            raise OffChainOutOfOrder(
                f'Expect command seq {next_final_sequence} but got {response.command_seq}, '
                f'last confirmed: {last_confirmed}'
            )

        # Read and write back response into request.
        request.response = response
        self.my_requests[request_seq] = request

        # Optimization -- update the retransmit index.
        self.would_retransmit()

        # Add the next command to the common sequence.
        if response.command_seq == self.next_final_sequence():
            try:
                self.executor.sequence_next_command(
                    request.command,
                    do_not_sequence_errors=False
                )
            except ExecutorException as e:
                # If an error is raised, but the response is a success, then
                # raise a serious error and stop the channel. If not, all is
                # good -- we expected an error and this is why the command
                # possibly failed.
                if request.is_success():
                    logger.error(f'(other:{self.other_address_str}) {e}', exc_info=True)
                    raise e

        # KEY INVARIANT: Can we prove this always holds?
        assert response.command_seq == self.executor.last_confirmed

        self.apply_response_to_executor(request)
        self.register_deps(request)
        return request.is_success()

    def retransmit(self):
        """ Re-sends the earlierst request that has not yet got a response,
        if any """
        self.would_retransmit(do_retransmit=True)

    def would_retransmit(self, do_retransmit=False):
        """ Returns true if there are any pending re-transmits, namely
            requests for which the response has not yet been received.
            Note that this function re-transmits at most one request
            at a time.
        """

        request_to_send = None

        with self.rlock:
            with self.storage.atomic_writes():
                next_retransmit = self.next_retransmit.get_value()
                while next_retransmit < self.my_next_seq():
                    request = self.my_requests[next_retransmit]
                    if request.has_response():
                        next_retransmit += 1
                    else:
                        request_to_send = request
                        break

                if next_retransmit != self.next_retransmit.get_value():
                    self.next_retransmit.set_value(next_retransmit)

        # Send request outside the lock to allow for asynchronous
        # sending methods.
        if not do_retransmit:
            return request_to_send is not None
        else:
            return self.send_request(request) if request_to_send is not None \
                else None

    def pending_retransmit_number(self):
        '''
        Returns:
            the number of requests that are waiting to be
            retransmitted on this channel.
        '''
        if not self.would_retransmit():
            return 0

        return self.my_next_seq() - self.next_retransmit.get_value()
