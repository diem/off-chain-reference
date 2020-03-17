from executor import ProtocolExecutor, ExecutorException, CommandProcessor
from protocol_messages import CommandRequestObject, CommandResponseObject, \
    make_success_response, make_protocol_error, make_parsing_error, make_command_error
from utils import JSONParsingError, JSONFlag
from libra_address import LibraAddress

import json
from collections import namedtuple

NetMessage = namedtuple('NetMessage', ['src', 'dst', 'type', 'content'])

class OffChainVASP:
    """Manages the off-chain protocol on behalf of one VASP. """

    def __init__(self, vasp_addr, processor):
        if __debug__:
            assert isinstance(processor, CommandProcessor)
            assert isinstance(vasp_addr, LibraAddress)

        self.vasp_addr = vasp_addr
        self.business_context = processor.business_context()
        self.processor = processor
        self.processor.notify = self.notify_new_commands

        # TODO: this should be a persistent store
        self.channel_store = {}

    def my_vasp_addr(self):
        ''' Return our own VASP Libra Address. '''
        return self.vasp_addr

    def get_channel(self, other_vasp_addr):
        ''' Returns a VASPPairChannel with the other VASP '''
        self.business_context.open_channel_to(other_vasp_addr)
        my_address = self.my_vasp_addr()
        other_address = other_vasp_addr
        store_key = (my_address, other_address)
        if store_key not in self.channel_store:
            channel = VASPPairChannel(self.my_vasp_addr(), other_vasp_addr, self, self.processor)
            self.channel_store[store_key] = channel

        return self.channel_store[store_key]

    def notify_new_commands(self):
        ''' The processor calls this method to notify the VASP that new
            commands are available for processing. '''
        self.processor.process_command_backlog(self)


class VASPPairChannel:
    """Represents the state of an off-chain bi-directional channel bewteen two VASPs"""

    def __init__(self, myself, other, vasp, processor):
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

        # Check we are not making a channel with ourselves
        if self.myself.plain() == self.other.plain():
            raise Exception('Must talk to another VASP:', self.myself.plain(), self.other.plain())

        # TODO[issue #7]: persist and recover the command sequences
        # <STARTS to persist>
        self.my_requests = []
        self.my_next_seq = 0
        self.other_requests = []
        self.other_next_seq = 0

        # The final sequence
        self.executor = ProtocolExecutor(self, self.processor)
        # <ENDS to persist>

        # Ephemeral state that can be forgotten upon a crash

        # Response cache
        self.response_cache = {}
        self.pending_requests = []
        # Network handler
        self.net_queue = []

    def get_my_address(self):
        return self.myself

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
        return self.executor.seq

    def persist(self):
        """ A hook to block until state of channel is persisted """
        pass

    def send_request(self, request):
        """ A hook to send a request to other VASP"""
        json_string = request.get_json_data_dict(JSONFlag.NET)
        self.net_queue += [ NetMessage(self.myself, self.other, CommandRequestObject, json_string) ]

    def send_response(self, response):
        """ A hook to send a response to other VASP"""
        json_string = json.dumps(response.get_json_data_dict(JSONFlag.NET))
        net_message = NetMessage(self.myself, self.other, CommandResponseObject,json_string)
        self.net_queue += [ net_message ]
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
        return ['Client','Server'][self.is_server()]

    def is_server(self):
        """ Is the local VASP a server for this pair?"""
        return not self.is_client()

    def pending_responses(self):
        """ Counts the number of responses this VASP is waiting for """
        return len([1 for req in self.my_requests if not req.has_response()])

    def process_pending_requests_response(self):
        """ The server re-schedules and executes pending requests, and cached
            responses. """
        if self.pending_responses() == 0:
            requests = self.pending_requests
            self.pending_requests = []
            for req in requests:
                self.handle_request(req)

        ## No need to make loop -- it will call again upon success
        if self.next_final_sequence() in self.response_cache:
            response = self.response_cache[self.next_final_sequence()]
            self.handle_response(response)

    def apply_response_to_executor(self, request):
        """Signals to the executor the success of failure of a command."""
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
        request.seq = self.my_next_seq

        if self.is_server():
            request.command_seq = self.next_final_sequence()
            # Raises and exits on error -- does not sequence
            self.executor.sequence_next_command(off_chain_command,
                do_not_sequence_errors = True)

        self.my_next_seq += 1
        self.my_requests += [ request ]
        self.send_request(request)
        self.persist()


    def parse_handle_request(self, json_command):
        ''' Handles a request provided as a json_string '''
        try:
            req_dict = json.loads(json_command)
            request = CommandRequestObject.from_json_data_dict(req_dict, JSONFlag.NET)
            return self.handle_request(request)
        except JSONParsingError:
            response = make_parsing_error()
            return self.send_response(response)


    def handle_request(self, request):
        """ Handles a request received by this VASP.

            Returns a network record of the response if one can be constructed,
            or None in case they are scheduled for later processing. If none is
            returned then this function must be called again once the condition

                self.pending_responses() == 0

            becomes true.
        """
        request.command.set_origin(self.other)

        # Always answer old requests
        if request.seq < self.other_next_seq:
            previous_request = self.other_requests[request.seq]
            if previous_request.is_same_command(request):
                # Re-send the response
                response = previous_request.response
                return self.send_response(response)

            else:
                # There is a conflict, and it will have to be resolved
                #  TODO[issue 8]: How are conflicts meant to be resolved? With only
                #        two participants we cannot tolerate errors.
                response = make_protocol_error(request, code='conflict')
                response.previous_command = previous_request.command
                return self.send_response(response)

        # Clients are not to suggest sequence numbers.
        if self.is_server() and request.command_seq is not None:
            response = make_protocol_error(request, code='malformed')
            return self.send_response(response)

        # As a server we first wait for the status of all server
        # requests to sequence any new client requests.
        if self.is_server() and self.pending_responses() > 0:
            self.pending_requests += [request]
            return None

        # Sequence newer requests
        if request.seq == self.other_next_seq:

            if self.is_client() and request.command_seq > self.next_final_sequence():
                # We must wait, since we cannot give an answer before sequencing
                # previous commands.
                response = make_protocol_error(request, code='wait')
                return self.send_response(response)

            self.other_next_seq += 1
            self.other_requests += [request]

            seq = self.next_final_sequence()
            old_len = len(self.executor.seq)
            try:
                self.executor.sequence_next_command(request.command,
                                                    do_not_sequence_errors = False)
                response = make_success_response(request)
            except ExecutorException as e:
                response = make_command_error(request, str(e))
            new_len = len(self.executor.seq)
            assert new_len == old_len + 1

            request.response = response
            request.response.command_seq = seq
            self.apply_response_to_executor(request)

            self.persist()
            return self.send_response(request.response)

        elif request.seq > self.other_next_seq:
            # We have received the other side's request without receiving the
            # previous one
            response = make_protocol_error(request, code='missing')
            return self.send_response(response)

            # NOTE: the protocol is still correct without persisiting the cache
            self.persist()
        else:
            # OK: Previous cases are exhaustive
            assert False

    def parse_handle_response(self, json_response):
        ''' Handles a response provided as a json string. '''
        try:
            resp_dict = json.loads(json_response)
            response = CommandResponseObject.from_json_data_dict(resp_dict, JSONFlag.NET)
            self.handle_response(response)
        except JSONParsingError:
            # Log, but cannot reply: TODO
            raise # To close the channel

    def handle_response(self, response):
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

            # Idenpotent: We have already processed the response
            if self.my_requests[request_seq].has_response():
                # TODO: Check the reponse is the same and log warning otherwise.
                return

            request = self.my_requests[request_seq]
            if response.command_seq == self.next_final_sequence():
                # Next command to commit -- do commit it.
                request.response = response

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
                self.persist()

            elif response.command_seq < self.next_final_sequence():
                # Request already in the sequence: happens to the leader.
                #  No chance to register an error, since we do not reply.
                request.response = response
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
        self.would_retransmit(do_retransmit=True)

    def would_retransmit(self, do_retransmit=False):
        """ Returns true if there are any pending re-transmits, namely
            requests for which the response has not yet been received. """
        for request in self.my_requests:
            assert isinstance(request, CommandRequestObject)
            if not request.has_response():
                if do_retransmit:
                    self.send_request(request)
                return True
        return False
