# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0


from .command_processor import CommandProcessor
from .protocol_messages import CommandRequestObject, CommandResponseObject, \
    OffChainProtocolError, OffChainOutOfOrder, OffChainException, \
    make_success_response, make_protocol_error, \
    make_parsing_error, make_command_error
from .utils import JSONParsingError, JSONFlag
from .libra_address import LibraAddress
from .crypto import OffChainInvalidSignature

import json
from collections import namedtuple
from threading import RLock
import logging

""" A Class to store messages meant to be sent on a network. """
NetMessage = namedtuple('NetMessage', ['src', 'dst', 'type', 'content'])

logger = logging.getLogger(name='libra_off_chain_api.protocol')


class DependencyException(Exception):
    pass


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

            # The common sequence of commands & and their
            # status for those committed.
            self.command_sequence = self.storage.make_list(
                'command_sequence', CommandRequestObject, root=other_vasp
            )

            self.commands_no_store = self.storage.make_value(
                                'command_no_store', int,
                                root=other_vasp, default=0)

            # Keep track of object locks
            self.object_locks = self.storage.make_dict('object_locks', str, root=other_vasp)
            self.my_request_index = self.storage.make_dict('my_request_index', CommandRequestObject, root=other_vasp)
            self.other_request_index = self.storage.make_dict('other_request_index', CommandRequestObject, root=other_vasp)
            self.pending_response = self.storage.make_dict('pending_response', bool, root=other_vasp)

        # Ephemeral state that can be forgotten upon a crash.

        # Network handler
        self.net_queue = []

        logger.debug(f'(other:{self.other_address_str}) Created VASP channel')

    @property
    def commands_no(self):
        return self.commands_no_store.get_value()

    def my_next_seq(self):
        """
        Returns:
            int: The next request sequence number for this VASP.
        """
        return 'SEQ_' + str(len(self.my_request_index))

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

    def next_final_sequence(self):
        """
        Returns:
            int: The next sequence number in the common sequence.
        """
        return len(self.command_sequence)

    def get_final_sequence(self):
        """
        Returns:
            list: The list of commands in the common sequence.
        """
        return self.command_sequence

    def package_request(self, request):
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

    def package_response(self, response):
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

    def apply_response_to_executor(self, request):
        """Signals to the executor the success or failure of a command.

        Args:
            request (CommandRequestObject): The request object.
        """
        assert request.response is not None
        response = request.response

        self.commands_no_store.set_value(self.commands_no + 1)
        other_addr = self.get_other_address()

        self.processor.process_command(
            other_addr=other_addr,
            command=request.command,
            seq=self.commands_no,
            status_success=request.is_success(),
            error=response.error if response.error else None
        )

    def sequence_command_local(self, off_chain_command):
        """The local VASP attempts to sequence a new off-chain command.

        Args:
            off_chain_command (PaymentCommand): The command to sequence.

        Returns:
            NetMessage: The message to be sent on a network.
        """

        off_chain_command.set_origin(self.get_my_address())
        request = CommandRequestObject(off_chain_command)

        # Before adding locally, check the dependencies
        create_versions = request.command.new_object_versions()
        depends_on_version = request.command.get_dependencies()

        if any(dv not in self.object_locks for dv in depends_on_version):
            raise DependencyException('Depends not present.')

        if any(self.object_locks[dv] == 'False' for dv in depends_on_version):
            raise DependencyException('Depends used.')

        if any(cv in self.object_locks for cv in create_versions):
            raise DependencyException('Object version already exists.')

        is_locked = any(self.object_locks[dv] != 'True'
                        for dv in depends_on_version)
        if is_locked:
            raise DependencyException('Depends locked.')

        # Ensure all storage operations are written atomically.
        with self.rlock:
            with self.storage.atomic_writes() as _:
                request.cid = self.my_next_seq()

                my_address = self.get_my_address()
                other_address = self.get_other_address()
                self.processor.check_command(my_address, other_address, off_chain_command)

                self.my_request_index[request.cid] = request

                # Add the request to those requiring a response.
                self.pending_response[request.cid] = True

                for dv in depends_on_version:
                    self.object_locks[dv] = request.cid
                    # By definition nothing was waiting here, since
                    # we checked it was all True.

        # Send the requests outside the locks to allow
        # for an asyncronous implementation.
        return self.package_request(request)

    def parse_handle_request(self, json_command):
        """ Handles a request provided as a json string or dict.

        Args:
            json_command (str or dict): The json request.

        Returns:
            NetMessage: The message to be sent on a network.
        """
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
                    f'Processing request seq #{request.cid}',
                )
                response = self.handle_request(request)

        except OffChainInvalidSignature as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'Signature verification failed. OffChainInvalidSignature: {e}',
            )
            raise e

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
            raise e

        # Prepare the response.
        full_response = self.package_response(response)
        return full_response

    def handle_request(self, request):
        """ Handles a request provided as a dictionary. (see `_handle_request`)
        """
        with self.storage.atomic_writes() as _:
            return self._handle_request(request)

    def _handle_request(self, request):
        """ Handles a request provided as a dictionary.

        Args:
            request (CommandRequestObject): The request.

        Raises:
            OffChainOutOfOrder: In case the response is out of order
                (due to nowait=True).

        Returns:
            CommandResponseObject: The response to the VASP's request.
        """
        request.command.set_origin(self.other)

        # Keep track of object locks here.
        create_versions = request.command.new_object_versions()
        depends_on_version = request.command.get_dependencies()

        has_all_deps = all(dv in self.object_locks
                           for dv in depends_on_version)

        # Always answer old requests.
        if request.cid in self.other_request_index:
            previous_request = self.other_request_index[request.cid]
            if previous_request.has_response():
                if previous_request.is_same_command(request):

                    # Invariant
                    assert all(cv in self.object_locks for cv in create_versions)

                    # Re-send the response.
                    logger.debug(
                        f'(other:{self.other_address_str}) '
                        f'Handle request that alerady has a response: '
                        f'seq #{request.cid}, other next #XXX',
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
                        f'Conflicting requests for seq {request.cid}',
                    )
                    return response


        # If one of the dependency is locked then wait.
        if has_all_deps:
            is_locked = any(self.object_locks[dv] != 'True'
                for dv in depends_on_version)
            if is_locked:
                if self.is_server():
                    # The server requests take precedence, so make this wait.
                    response = make_protocol_error(request, code='wait')
                    return response
                else:
                    # A client yields the locks to the server.
                    pass

        try:
            if not has_all_deps:
                raise Exception('Missing dependencies')

            command = request.command
            my_address = self.get_my_address()
            other_address = self.get_other_address()
            self.processor.check_command(
                my_address, other_address, command)

            response = make_success_response(request)
        except Exception as e:
            response = make_command_error(request, str(e))

        # Write back to storage
        request.response = response

        # Update the index of others' requests
        self.command_sequence += [request]
        self.other_request_index[request.cid] = request
        self.register_dependencies(request)
        self.apply_response_to_executor(request)

        return request.response

    def register_dependencies(self, request):
        ''' A helper function to register dependencies of a successful request. '''

        # Keep track of object locks here.
        create_versions = request.command.new_object_versions()
        depends_on_version = request.command.get_dependencies()

        if any(cv in self.object_locks for cv in create_versions):
            # The objects already exist? Do not change them!
            return

        if request.is_success():
            assert all(v in self.object_locks for v in depends_on_version)

            for dv in depends_on_version:
                self.object_locks[dv] = 'False'

            for cv in create_versions:
                self.object_locks[cv] = 'True'

        else:
            assert all(v in self.object_locks for v in depends_on_version)

            for dv in depends_on_version:
                if depends_on_version[dv] == request.cid:
                    self.object_locks[dv] = 'True'


    def parse_handle_response(self, json_response):
        """ Handles a response as json string or dict.

        Args:
            json_response (str or dict): The json response.

        Returns:
            bool: Whether the command was a success or not
        """
        try:
            vasp = self.get_vasp()
            other_key = vasp.info_context.get_peer_compliance_verification_key(
                self.get_other_address().as_str()
            )
            response = json.loads(other_key.verify_message(json_response))
            response = CommandResponseObject.from_json_data_dict(
                response, JSONFlag.NET
            )

            with self.rlock:
                result = self.handle_response(response)
            return result

        except OffChainInvalidSignature as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'Signature verification failed. OffChainInvalidSignature: {e}',
            )
            raise e
        except JSONParsingError as e:
            logger.warning(
                f'(other:{self.other_address_str}) JSONParsingError: {e}'
            )
            raise e
        # except OffChainOutOfOrder as e:
        # TODO: What if two consecutive  server responses on the same object
        # arrive out of order?
        except OffChainOutOfOrder or OffChainException or OffChainProtocolError as e:
            logger.warning(
                f'(other:{self.other_address_str}) '
                f'OffChainException/OffChainProtocolError: {e}',
            )
            raise e


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

        Returns:
            bool: Whether the response is successfully sequenced.
        """
        assert isinstance(response, CommandResponseObject)

        # Is there was a protocol error return the error.
        if response.is_protocol_failure():
            raise OffChainProtocolError.make(response.error)

        request_seq = response.cid

        if request_seq not in self.my_request_index:
            raise OffChainException(
                f'Response for seq {request_seq} received, '
                f'but has requests only up to seq < xxx'
            )

        # Idenpotent: We have already processed the response.
        request = self.my_request_index[request_seq]
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
            return self.my_request_index[request_seq].is_success()

        # Read and write back response into request.
        request.response = response
        del self.pending_response[request.cid]

        # Add the next command to the common sequence.
        self.command_sequence += [request]
        self.my_request_index[request_seq] = request
        self.register_dependencies(request)
        self.apply_response_to_executor(request)

        return request.is_success()

    def package_retransmit(self, number=1):
        """ Re-sends the earlierst request that has not yet got a response,
        if any """

        net_messages = []
        for num, next_retransmit in enumerate(self.pending_response.keys()):
            request_to_send = self.my_request_index[next_retransmit]
            net_messages += [ self.package_request(request_to_send)]
            if num == number:
                break

        return net_messages

    def would_retransmit(self):
        """ Returns true if there are any pending re-transmits, namely
            requests for which the response has not yet been received.
            Note that this function re-transmits at most one request
            at a time.
        """
        return len(self.pending_response) > 0

    def pending_retransmit_number(self):
        '''
        Returns:
            the number of requests that are waiting to be
            retransmitted on this channel.
        '''
        return len(self.pending_response)
