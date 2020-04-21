from .executor import ProtocolExecutor, ExecutorException, CommandProcessor
from .protocol_messages import CommandRequestObject, CommandResponseObject, \
    make_success_response, make_protocol_error, make_parsing_error, make_command_error
from .utils import JSONParsingError, JSONFlag
from .libra_address import LibraAddress
from .storage import StorableFactory

import json
from collections import namedtuple
from threading import RLock
import logging

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
        ''' Returns a VASPPairChannel with the other VASP '''
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

    def close_channel(self, other_vasp_addr):
        my_address = self.get_vasp_address()
        store_key = (my_address, other_vasp_addr)
        if store_key in self.channel_store:
            # Close the TLS channel.
            channel = self.channel_store[store_key]
            channel.network_client.close_connection()

            # Delete the channel from our store.
            del self.channel_store[store_key]


class VASPPairChannel:
    """Represents the state of an off-chain bi-directional channel bewteen two VASPs"""

    def __init__(self, myself, other, vasp, storage, processor):
        """ Initialize the channel between two VASPs.

        * Myself is the VASP initializing the local object (VASPInfo)
        * Other is the other VASP (VASPInfo).
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
            raise Exception('Must talk to another VASP:', self.myself.as_str(), self.other.as_str())

        # A reentrant lock to manage access.
        self.rlock = RLock()

        # <STARTS to persist>
        root = self.storage.make_value(self.myself.as_str(), None)
        other_vasp = self.storage.make_value(self.other.as_str(), None, root=root)

        with self.storage.atomic_writes() as tx_no:

            # The list of requests I have initiated
            self.my_requests = self.storage.make_list('my_requests', CommandRequestObject, root=other_vasp)

            # The list of requests the other side has initiated
            self.other_requests = self.storage.make_list('other_requests', CommandRequestObject, root=other_vasp)

            # The index of the next request from my sequence that I should retransmit
            # (ie. for which I have not got a response yet.)
            self.next_retransmit = self.storage.make_value('next_retransmit', int, root=other_vasp, default=0)

            # The final sequence
            self.executor = ProtocolExecutor(self, self.processor)

        # <ENDS to persist>

        # Ephemeral state that can be forgotten upon a crash

        # Response cache
        self.response_cache = {}
        self.pending_requests = []
        # Network handler
        self.net_queue = []

        # The peer base url
        self.peer_base_url = self.vasp.info_context.get_peer_base_url(self.other)

        logging.debug(f'Creating VASP channel {myself.as_str()} -> {other.as_str()}')

    def my_next_seq(self):
        return len(self.my_requests)

    def other_next_seq(self):
        return len(self.other_requests)

    def get_my_address(self):
        return self.myself

    def get_other_address(self):
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
        self.net_queue += [ NetMessage(self.myself, self.other, CommandRequestObject, json_string) ]
        logging.debug(f'Request SENT {self.myself.as_str()}  -> {self.other.as_str()}')
        #self.network_client.send_request(json_string)

    def send_response(self, response):
        """ A hook to send a response to other VASP"""
        json_string = json.dumps(response.get_json_data_dict(JSONFlag.NET))
        net_message = NetMessage(self.myself, self.other, CommandResponseObject, json_string)
        self.net_queue += [ net_message ]
        logging.debug(f'Response SENT {self.myself.as_str()}  -> {self.other.as_str()}')
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


    def process_pending_requests_response(self):
        """ The server re-schedules and executes pending requests, and cached
            responses. """
        if self.num_pending_responses() == 0:
            requests = self.pending_requests
            self.pending_requests = []
            for req in requests:
                self.handle_request(req)

        ## No need to make loop -- it will call again upon success
        if self.next_final_sequence() in self.response_cache:
            response = self.response_cache[self.next_final_sequence()]
            self.handle_response(response)


    def apply_response_to_executor(self, request):
        """Signals to the executor the success or failure of a command."""
        assert request.response is not None
        response = request.response
        if request.is_success():
            self.executor.set_success(response.command_seq)
        else:
            self.executor.set_fail(response.command_seq)

    def sequence_command_local(self, off_chain_command):
        """ The local VASP attempts to sequence a new off-chain command."""

        off_chain_command.set_origin(self.get_my_address())
        request = CommandRequestObject(off_chain_command)

        # Ensure all storage operations are written atomically.
        with self.rlock:
            with self.storage.atomic_writes() as tx_no:
                request.seq = self.my_next_seq()

                if self.is_server():
                    request.command_seq = self.next_final_sequence()
                    # Raises and exits on error -- does not sequence
                    self.executor.sequence_next_command(off_chain_command,
                        do_not_sequence_errors = True)

                self.my_requests += [ request ]

        # Send the requests outside the locks to allow
        # for an asyncronous implementation.
        self.send_request(request)


    def parse_handle_request(self, json_command):
        ''' Handles a request provided as a json_string '''
        assert type(json_command) == str
        logging.debug(f'Request Received {self.other.as_str()}  -> {self.myself.as_str()}')
        with self.rlock:
            try:
                req_dict = json.loads(json_command)
                request = CommandRequestObject.from_json_data_dict(req_dict, JSONFlag.NET)
                # return self.handle_request(request)
                response = self.handle_request(request)
            except JSONParsingError:
                response = make_parsing_error()
                #return self.send_response(response)

        full_response = self.send_response(response)
        return full_response


    def handle_request(self, request):
        with  self.storage.atomic_writes() as tx_no:
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
                return response

        # Clients are not to suggest sequence numbers.
        if self.is_server() and request.command_seq is not None:
            response = make_protocol_error(request, code='malformed')
            return response

        # As a server we first wait for the status of all server
        # requests to sequence any new client requests.
        if self.is_server() and self.num_pending_responses() > 0:
            self.pending_requests += [request]
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

    def parse_handle_response(self, json_response):
        ''' Handles a response provided as a json string. '''
        assert type(json_response) == str
        logging.debug(f'Response Received {self.other.as_str()}  -> {self.myself.as_str()}')
        with self.rlock:
            try:
                resp_dict = json.loads(json_response)
                response = CommandResponseObject.from_json_data_dict(resp_dict, JSONFlag.NET)
                self.handle_response(response)
            except JSONParsingError:
                # Log, but cannot reply: TODO
                raise # To close the channel

    def handle_response(self, response):
        with self.storage.atomic_writes() as tx_no:
            self._handle_response(response)

    def _handle_response(self, response):
        """ Handles a response to a request by this VASP """
        assert isinstance(response, CommandResponseObject)

        request_seq = response.seq
        if type(request_seq) is not int:
            # This denotes a serious error, where the response could not
            # even be parsed. TODO: log the request/reply for debugging.
            assert response.status == 'failure'
            return

        # Check this is the next expected response
        if not request_seq < len(self.my_requests):
            # Caught a bug on the other side
            # TODO: Log warning the other side might be buggy
            return

        if response.not_protocol_failure():

            # Optimization
            next_expected = self.next_retransmit.get_value()
            if next_expected == request_seq:
                self.next_retransmit.set_value(next_expected + 1)

            # Idenpotent: We have already processed the response
            if self.my_requests[request_seq].has_response():
                # TODO: Check the reponse is the same and log warning otherwise.
                return

            request = self.my_requests[request_seq]
            if response.command_seq == self.next_final_sequence():
                # Next command to commit -- do commit it.
                request.response = response

                # Write back the request to storage
                self.my_requests[request_seq] = request

                try:
                    self.executor.sequence_next_command(request.command, \
                        do_not_sequence_errors = False)
                except:
                    # We ignore the outcome since the response is what matters.
                    # TODO: something buggy has happened, if we return an error
                    #       at this point. Log a warning to interop testing.
                    pass

                self.apply_response_to_executor(request)
                self.process_pending_requests_response()

            elif response.command_seq < self.next_final_sequence():
                # Request already in the sequence: happens to the server party.
                #  No chance to register an error, since we do not reply.
                request.response = response

                # Write back the request to storage
                self.my_requests[request_seq] = request

                self.apply_response_to_executor(request)
                self.process_pending_requests_response()

            elif response.command_seq > self.next_final_sequence():
                # This is too high -- wait for more data?
                # Store the response for later use.
                self.response_cache[response.command_seq] = response
            else:
                # Previous conditions are exhaustive
                assert False
        else:
            # Handle protocol failures.
            if response.error.code == 'missing':
                pass  # Will Retransmit
            elif response.error.code == 'wait':
                pass  # Will Retransmit
            elif response.error.code == 'malformed':
                # TODO: log a warning
                pass # Implementation bug was caught.
            elif response.error.code == 'conflict':
                pass
            else:
                # Manage other errors
                # Implementation bug was caught.
                assert False

    def retransmit(self):
        """ Re-sends the earlierst request that has not yet got a response, if any """
        with self.rlock:
            self.would_retransmit(do_retransmit=True)

    def would_retransmit(self, do_retransmit=False):
        """ Returns true if there are any pending re-transmits, namely
            requests for which the response has not yet been received. """

        request_to_send = None

        with self.rlock:
            with self.storage.atomic_writes() as tx_no:
                answer = False
                next_retransmit = self.next_retransmit.get_value()
                while next_retransmit < len(self.my_requests):
                    request = self.my_requests[next_retransmit]
                    if request.has_response():
                        next_retransmit += 1
                    else:
                        answer = True
                        if do_retransmit:
                            request_to_send = request
                        break
                self.next_retransmit.set_value(next_retransmit)

        # Send request outside the lock to allow for asynchronous
        # sending methods.
        if request_to_send is not None:
            self.send_request(request)
        return answer
