from .executor import ProtocolExecutor, ExecutorException, CommandProcessor
from .protocol_messages import CommandRequestObject, CommandResponseObject, \
    OffChainProtocolError, OffChainOutOfOrder, OffChainException, \
    make_success_response, make_protocol_error, \
    make_parsing_error, make_command_error
from .utils import JSONParsingError, JSONFlag
from .libra_address import LibraAddress

import json
from collections import namedtuple, defaultdict
from threading import RLock
import logging
import asyncio
import time

""" A Class to store messages meant to be sent on a network. """
NetMessage = namedtuple('NetMessage', ['src', 'dst', 'type', 'content'])


class OffChainVASP:
    """Manages the off-chain protocol on behalf of one VASP. """
    def __init__(self, vasp_addr, processor, storage_factory, info_context):
        logging.debug(f'Creating VASP {vasp_addr.as_str()}')

        assert isinstance(processor, CommandProcessor)
        assert isinstance(vasp_addr, LibraAddress)

        # The LibraAddress of the VASP
        self.vasp_addr = vasp_addr
        # The business context provided by the processor
        self.business_context = processor.business_context()

        # The command processor that checks and processes commands
        # We attach the notify member to this class to trigger
        # processing of resumed commands.
        self.processor = processor

        # The VASPInfo context that contains various network information
        # such as TLS certificates and keys.
        self.info_context = info_context

        # The dict of channels we already have.
        self.channel_store = {}

        # Manage storage
        self.storage_factory = storage_factory

    def get_vasp_address(self):
        ''' Return our own VASP Libra Address. '''
        return self.vasp_addr

    def get_channel(self, other_vasp_addr):
        ''' Returns a VASPPairChannel with the other VASP.

        Parameters:
            other_vasp_addr : is a LibraAddress.

        Returns:
            A VASPPairChannel.

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
        ''' Returns a storage factory for this system. '''
        return self.storage_factory


class VASPPairChannel:
    """ Represents the state of an off-chain bi-directional
        channel bewteen two VASPs"""

    def __init__(self, myself, other, vasp, storage, processor):
        """ Initialize the channel between two VASPs.

        * Myself is own LibraAddress.
        * Other is the other VASP LibraAddress.
        * Vasp is the OffChainVASP object this channel belongs to.
        * Storage is a StorableFactory instance.
        * Processor is a command processor for this channel.

        """

        if __debug__:
            assert isinstance(myself, LibraAddress)
            assert isinstance(other, LibraAddress)
            assert isinstance(processor, CommandProcessor)
            assert isinstance(vasp, OffChainVASP)

        # State that is given by constructor
        self.myself = myself
        self.other = other
        self.processor = processor
        self.vasp = vasp
        self.storage = storage

        # Check we are not making a channel with ourselves
        if self.myself.as_str() == self.other.as_str():
            raise OffChainException(
                'Must talk to another VASP:',
                self.myself.as_str(),
                self.other.as_str())

        # A reentrant lock to manage access.
        self.rlock = RLock()
        self.logger = logging.getLogger(name=f'channel.{self.other.as_str()}')

        # State that is persisted

        root = self.storage.make_value(self.myself.as_str(), None)
        other_vasp = self.storage.make_value(
            self.other.as_str(), None, root=root)

        with self.storage.atomic_writes() as _:

            # The list of requests I have initiated
            self.my_requests = self.storage.make_list(
                'my_requests', CommandRequestObject, root=other_vasp)

            # The list of requests the other side has initiated
            self.other_requests = self.storage.make_list(
                'other_requests', CommandRequestObject, root=other_vasp)

            # The index of the next request from my sequence that I should
            # retransmit (ie. for which I have not got a response yet.)
            self.next_retransmit = self.storage.make_value(
                'next_retransmit', int, root=other_vasp, default=0)

            # The final sequence
            self.executor = ProtocolExecutor(self, self.processor)

        # Ephemeral state that can be forgotten upon a crash

        # Request / response cache to allow reordering
        self.waiting_requests = defaultdict(list)
        self.request_window = 1000
        self.waiting_response = defaultdict(list)
        self.response_window = 1000

        # Network handler
        self.net_queue = []

        oth_addr = other.as_str()
        self.logger.debug(f'Created VASP channel to {oth_addr}')

    def my_next_seq(self):
        ''' Returns the next request sequence number for this VASP. '''
        return len(self.my_requests)

    def other_next_seq(self):
        ''' Returns the next request sequence number for the other VASP. '''
        return len(self.other_requests)

    def get_my_address(self):
        ''' Returns own VASP LibraAddress. '''
        return self.myself

    def get_other_address(self):
        ''' Returns other VASP LibraAddress. '''
        return self.other

    def get_vasp(self):
        ''' Get the OffChainVASP to which this channel is attached. '''
        return self.vasp

    # Define a stub here to make the linter happy
    if __debug__:
        def tap(self):
            return []

    def next_final_sequence(self):
        """ Returns the next sequence number in the common sequence."""
        return self.executor.next_seq()

    def get_final_sequence(self):
        """ Returns a list of commands in the common sequence. """
        return self.executor.command_sequence

    def send_request(self, request):
        """ A hook to send a request to other VASP"""
        json_string = request.get_json_data_dict(JSONFlag.NET)
        net_message = NetMessage(
            self.myself,
            self.other,
            CommandRequestObject,
            json_string)

        # Only used in unit tests
        if __debug__:
            self.net_queue += [net_message]

        self.logger.debug(f'Request SENT -> {self.other.as_str()}')
        return net_message

    def send_response(self, response, encoded=True):
        """ A hook to send a response to other VASP"""
        struct = response.get_json_data_dict(JSONFlag.NET)
        if encoded:
            struct = json.dumps(struct)
        net_message = NetMessage(
            self.myself, self.other, CommandResponseObject, struct)
        if __debug__:
            self.net_queue += [net_message]
        self.logger.debug(f'Response SENT -> {self.other.as_str()}')
        return net_message

    def is_client(self):
        """ Is the local VASP a client for this pair?"""
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
        """ The role of the VASP as a string. For debug output."""
        return ['Server', 'Client'][self.is_client()]

    def is_server(self):
        """ Is the local VASP a server for this pair?"""
        return not self.is_client()

    def num_pending_responses(self):
        """ Counts the number of responses this VASP is waiting for """
        return len([1 for req in self.my_requests if not req.has_response()])

    def has_pending_responses(self):
        return self.would_retransmit()

    def apply_response_to_executor(self, request):
        """Signals to the executor the success or failure of a command."""
        assert request.response is not None
        response = request.response
        if request.is_success():
            self.executor.set_success(response.command_seq)
        else:
            self.executor.set_fail(response.command_seq, response.error)

    def sequence_command_local(self, off_chain_command):
        """ The local VASP attempts to sequence a new off-chain command."""

        off_chain_command.set_origin(self.get_my_address())
        request = CommandRequestObject(off_chain_command)

        # Ensure all storage operations are written atomically.
        with self.rlock:
            with self.storage.atomic_writes() as _:
                request.seq = self.my_next_seq()

                if self.is_server():
                    request.command_seq = self.next_final_sequence()
                    # Raises and exits on error -- does not sequence
                    self.executor.sequence_next_command(
                        off_chain_command,
                        do_not_sequence_errors=True)

                self.my_requests += [request]

        # Send the requests outside the locks to allow
        # for an asyncronous implementation.
        return self.send_request(request)

    def parse_handle_request(self, json_command, encoded=False):
        ''' Handles a request provided as a json_string '''
        loop = asyncio.new_event_loop()
        fut = self.parse_handle_request_to_future(
            json_command,
            encoded,
            nowait=True,
            loop=loop)
        return fut.result()

    def process_waiting_messages(self):
        ''' Executes any requets that are now capable of executing, and were
            not before due to being received out of order. '''

        while self.next_final_sequence() in self.waiting_response:
            next_cmd_seq = self.executor.last_confirmed
            list_of_responses = self.waiting_response[next_cmd_seq]
            for resp_record in list_of_responses:
                (json_command, encoded, fut) = resp_record
                self.parse_handle_response_to_future(json_command, encoded, fut)
            del self.waiting_response[next_cmd_seq]

        while self.other_next_seq() in self.waiting_requests:
            next_seq = self.other_next_seq()
            list_of_requests = self.waiting_requests[next_seq]
            for req_record in list_of_requests:
                (json_command, encoded, fut, old_time) = req_record

                # Call, and this will update the future and unblocks
                # any processes waiting on it.
                self.parse_handle_request_to_future(json_command, encoded, fut)

            del self.waiting_requests[next_seq]


    def parse_handle_request_to_future(self, json_command, encoded=False, fut=None, nowait=False, loop=None):
        ''' Handles a request provided as a json_string and returns
            a future that triggers when the command is processed.

            Parameters:
                * json_command : the json CommandRequest serialized object
                * encoded : True if json_command is a string or False if it is
                  a dict.
                * loop : the event loop to use
                * nowait : feed requests commands even out of order without
                  waiting.

            Returns:
                * A (NetMessage) instance containing the response to the request.

            '''

        if fut is None:
            fut = asyncio.Future(loop=loop)

        self.logger.debug(f'Request Received -> {self.myself.as_str()}')
        try:
            # Parse the request whoever necessary
            req_dict = json.loads(json_command) if encoded else json_command
            request = CommandRequestObject.from_json_data_dict(req_dict, JSONFlag.NET)

            # Here test if it is the next one in order
            # (1) It is not in the next window
            # (3) The server is not waiting for replies
            if not (self.other_next_seq() < request.seq  < request.seq + self.request_window) and \
                    not (self.is_server() and self.num_pending_responses() > 0) or \
                    nowait:
                with self.rlock:
                    response = self.handle_request(request)
            else:
                self.waiting_requests[request.seq] += [(json_command, encoded, fut, time.time())]
                return fut
        except JSONParsingError:
            response = make_parsing_error()
            full_response = self.send_response(response, encoded=False)
        except Exception as e:
            fut.set_exception(e)
            return fut

        # Prepare the response.
        full_response = self.send_response(response, encoded=False)
        fut.set_result(full_response)
        return fut


    def handle_request(self, request):
        with self.storage.atomic_writes() as tx_no:
            return self._handle_request(request)

    def _handle_request(self, request):
        """ Handles a request received by this VASP.

            Returns a network record of the response to the request.
        """
        request.command.set_origin(self.other)

        # Always answer old requests
        if request.seq < self.other_next_seq():
            previous_request = self.other_requests[request.seq]
            if previous_request.is_same_command(request):
                # Re-send the response
                response = previous_request.response
                return response

            else:
                # There is a conflict, and it will have to be resolved
                #  TODO[issue 8]: How are conflicts meant to be resolved? With only
                #        two participants we cannot tolerate errors.
                response = make_protocol_error(request, code='conflict')
                response.previous_command = previous_request.command
                self.logger.error('Conflicting requests for seq {request.seq}')
                return response

        # Clients are not to suggest sequence numbers.
        if self.is_server() and request.command_seq is not None:
            response = make_protocol_error(request, code='malformed')
            return response

        # As a server we first wait for the status of all server
        # requests to sequence any new client requests.
        if self.is_server() and self.num_pending_responses() > 0:
            # TODO [issue #38]: Ideally, the channel should return None,
            # and the server network should wait until a response is available
            # before answering the client.
            response = make_protocol_error(request, code='wait')
            return response

        # Sequence newer requests
        if request.seq == self.other_next_seq():
            if self.is_client() and request.command_seq > self.next_final_sequence():
                # We must wait, since we cannot give an answer before sequencing
                # previous commands.
                response = make_protocol_error(request, code='wait')
                return response

            seq = self.next_final_sequence()
            try:
                self.executor.sequence_next_command(request.command,
                                    do_not_sequence_errors = False)
                response = make_success_response(request)
            except ExecutorException as e:
                response = make_command_error(request, str(e))

            # Write back to storage
            request.response = response
            request.response.command_seq = seq
            self.other_requests += [request]
            self.apply_response_to_executor(request)
            return request.response

        elif request.seq > self.other_next_seq():
            # We have received the other side's request without receiving the
            # previous one
            response = make_protocol_error(request, code='missing')
            return response
        else:
            # OK: Previous cases are exhaustive
            assert False

    def parse_handle_response(self, json_response, encoded=False):
        ''' Calls `parse_handle_response_to_future` but respoves the future and returns the result. '''
        loop = asyncio.new_event_loop()
        fut = self.parse_handle_response_to_future(json_response, encoded, nowait=True, loop=loop)
        return fut.result()

    def parse_handle_response_to_future(self, json_response, encoded=False, fut=None, nowait=False, loop=None):
        ''' Handles a response provided as a json string. Returns a future
            that fires when the response is processed. You may `await` this future
            from an asyncio coroutine.

            Parameters:
                * json_response : the response received
                * encoded : True if the json_response is a json string, or False if it is a dictionary.
                * nowait : do not wait for the reponse to be in order, and feed it directly to the protocol state machine.
                * loop : the event loop in which this should be executed.

            Response:
                * Returns True if the command was a success or False if it was not a success (Command error).

            Raises:
                * On protocol error it throws an exception (OffChainProtocolError).
                * On an unrecoverabe error it throws an (OffChainException).
                * In case the response is out of order (due to nowait=True) then an (OffChainOutOfOrder) is raised.

            '''
        self.logger.debug(f'Response Received -> {self.myself.as_str()}')

        if fut is None:
            fut = asyncio.Future(loop=loop)

        try:
            resp_dict = json.loads(json_response) if encoded else json_response
            response = CommandResponseObject.from_json_data_dict(resp_dict, JSONFlag.NET)

            # Check if this has to wait
            next_response_seq = self.next_final_sequence()
            command_seq = response.command_seq
            if command_seq is None \
                or not (next_response_seq < command_seq < next_response_seq + self.response_window) \
                or nowait:
                with self.rlock:
                    result = self.handle_response(response)
                fut.set_result(result)

            else:
                self.waiting_response[command_seq] += [(json_response, encoded, fut)]

        except JSONParsingError as e:
            # Log, but cannot reply: TODO
            # Close the channel?
            import traceback
            traceback.print_exc()
            fut.set_exception(e)

        return fut

    def handle_response(self, response):
        with self.storage.atomic_writes() as tx_no:
            return self._handle_response(response)

    def _handle_response(self, response):
        """ Handles a response to a request by this VASP.

        If protocol error occurs raises a OffChainProtocolError.
        Otherwise returns True if the command is successfully sequenced,
        and False if it is sequenced but not successful.

        On serious unrecoverable errors it also raises OffChainException.

        It raises
        """
        assert isinstance(response, CommandResponseObject)

        # Is there was a protocol error return the error.
        if response.is_protocol_failure():
            raise OffChainProtocolError.make(response.error)

        if type(response.seq) is not int:
            raise OffChainException(f'''Response seq must be int not {response.seq} ({type(response.seq)})''')

        request_seq = response.seq

        # Check this is the next expected response
        if not request_seq < len(self.my_requests):
            raise OffChainException(f'''Response for seq {request_seq} received, but has requests only up to seq < {len(self.my_requests)}''')

        # Optimization -- no need to retransmit since we got a response.
        next_expected = self.next_retransmit.get_value()
        if next_expected == request_seq:
            self.next_retransmit.set_value(next_expected + 1)

        # Idenpotent: We have already processed the response
        if self.my_requests[request_seq].has_response():

            # Check the reponse is the same and log warning otherwise.
            if self.my_requests[request_seq].response != response:
                excp =  OffChainException('Got duplicate but different responses.')
                excp.reponse1 = self.my_requests[request_seq].response
                excp.response2 = response
                raise excp
            return self.my_requests[request_seq].is_success()

        # This is too high -- wait for more data.
        if response.command_seq > self.next_final_sequence():
            raise OffChainOutOfOrder(f'Expect command seq {self.next_final_sequence()} but got higher {response.command_seq}')

        # Read and write back response into request
        request = self.my_requests[request_seq]
        request.response = response
        self.my_requests[request_seq] = request

        # Add the next command to the common sequence.
        if response.command_seq == self.next_final_sequence():
            try:
                self.executor.sequence_next_command(
                     request.command,
                     do_not_sequence_errors=False)
            except ExecutorException as e:
                # If a error is raised, but the response is a success, then
                # raise a serious error and stop the channel. If not all is
                # good -- we expected an error and this is why the command
                # failed possibly.
                if request.is_success():
                    self.logger.exception(e)
                    raise e

        # KEY INVARIANT: Can we prove this always holds?
        assert response.command_seq == self.executor.last_confirmed

        self.apply_response_to_executor(request)
        return request.is_success()


    def retransmit(self):
        """ Re-sends the earlierst request that has not yet got a response, if any """
        self.would_retransmit(do_retransmit=True)

    def would_retransmit(self, do_retransmit=False):
        """ Returns true if there are any pending re-transmits, namely
            requests for which the response has not yet been received. """

        request_to_send = None

        with self.rlock:
            with self.storage.atomic_writes() as tx_no:
                next_retransmit = self.next_retransmit.get_value()
                while next_retransmit < len(self.my_requests):
                    request = self.my_requests[next_retransmit]
                    if request.has_response():
                        next_retransmit += 1
                    else:
                        if do_retransmit:
                            request_to_send = request
                        break
                self.next_retransmit.set_value(next_retransmit)

        # Send request outside the lock to allow for asynchronous
        # sending methods.
        return self.send_request(request) if request_to_send != None else None
