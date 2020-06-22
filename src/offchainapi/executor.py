# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .utils import JSONSerializable, JSONFlag
from .command_processor import CommandProcessor
from .libra_address import LibraAddress

import logging


logger = logging.getLogger(name='libra_off_chain_api.executor')


# Interface we need to do commands:
class ProtocolCommand(JSONSerializable):
    def __init__(self):
        self.dependencies = []
        self.creates_versions = []
        self.origin = None  # Takes a LibraAddress.

    def set_origin(self, origin):
        """ Sets the Libra address that proposed this command.

        Args:
            origin (LibraAddress): the Libra address that proposed the command.
        """
        assert self.origin is None or origin == self.origin
        self.origin = origin

    def get_origin(self):
        """ Gets the Libra address that proposed this command.

        Returns:
            LibraAddress: the Libra address that proposed this command.

        """
        return self.origin

    def get_dependencies(self):
        ''' Get the list of dependencies.

            Returns:
                list: A list of version numbers.
        '''
        return set(self.dependencies)

    def new_object_versions(self):
        ''' Get the list of version numbers created by this command.

            Returns:
                list: A list of version numbers.
        '''
        return set(self.creates_versions)

    def get_object(self, version_number, dependencies):
        """ Returns the actual shared object with this version number.

        Args:
            version_number (int): The version number of the object.
            dependencies (list): The list of dependencies.

        Raises:
            SharedObject: The actual shared object with this version number.
        """
        raise NotImplementedError()  # pragma: no cover

    def get_json_data_dict(self, flag):
        """ Get a data dictionary compatible with
            JSON serilization (json.dumps).

        Args:
            flag (utils.JSONFlag): whether the JSON is intended
                for network transmission (NET) to another party or local storage
                (STORE).

        Returns:
            dict: A data dictionary compatible with JSON serilization.
        """
        data_dict = {
            "_dependencies":     self.dependencies,
            "_creates_versions": self.creates_versions,
        }

        if flag == JSONFlag.STORE:
            if self.origin is not None:
                data_dict.update({
                    "_origin": self.origin.as_str()
                })

        self.add_object_type(data_dict)
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        """ Construct the object from a serlialized
            JSON data dictionary (from json.loads).

        Args:
            data (dict): A JSON data dictionary.
            flag (utils.JSONFlag): whether the JSON is intended
                for network transmission (NET) to another party or local storage
                (STORE).

        Returns:
            ProtocolCommand: A ProtocolCommand from the input data.
        """
        self = cls.__new__(cls)
        ProtocolCommand.__init__(self)
        self.dependencies = list(data['_dependencies'])
        self.creates_versions = list(data['_creates_versions'])
        if flag == JSONFlag.STORE:
            if "_origin" in data:
                self.origin = LibraAddress(data["_origin"])
        return self


class ExecutorException(Exception):
    """ Indicates an exception in the executor. """
    pass


class ProtocolExecutor:
    """ An instance of this class managed the common sequence of commands
        between two VASPs, and whether they are a success or failure. It
        uses a CommandProcessor to determine if the command itself is
        valid by itslef, and also to then 'execute' the command, and
        possibly generate more commands as a result.

        A command in the sequence is a success if:
            * All the shared objects it depends on are active.
            * Both sides consider it a valid, according to the command
              processor checks).

        All successful commands see the objects they create become valid,
        and are passed on to the CommandProcessor, to drive the higher
        level protocol forward.
    """

    def __init__(self, channel, processor):
        """ Initialize the ProtocolExecutor with a Command Processor
            that checks the commands, and then executes the protocol for
            successful commands.

            The channel provides the context (vasp, channel) to pass on to
            the executor, as well as the storage context to persist
            the command sequence.

        Args:
            channel (VASPPairChannel): A VASP channel.
            processor (CommandProcessor): The command processor.
        """

        if __debug__:
            # No need for this import unless we are debugging.
            from .protocol import VASPPairChannel
            assert isinstance(processor, CommandProcessor)
            assert isinstance(channel, VASPPairChannel)

        self.processor = processor
        self.channel = channel
        self.other_name = self.channel.get_other_address().as_str()

        # <STARTS to persist>

        # Configure storage hierarchy.
        storage_factory = channel.storage
        root = storage_factory.make_value(
            channel.get_my_address().as_str(), None
        )
        other_vasp = storage_factory.make_value(
            channel.get_other_address().as_str(), None, root=root
        )

        # The common sequence of commands & and their
        # status for those committed.
        self.command_sequence = storage_factory.make_list(
            'command_sequence', ProtocolCommand, root=other_vasp
        )
        self.command_status_sequence = storage_factory.make_list(
            'command_status_sequence', bool, root=other_vasp
        )

    @property
    def last_confirmed(self):
        """ The index of the last confirmed (success or fail)
            command in the sequence.

            Returns:
                int: The index of the last confirmed command in the sequence.
        """
        return len(self.command_status_sequence)

    def set_outcome(self, command, is_success, seq, error=None):
        """ Execute successful commands, and notify of failed commands.

        Args:
            command (PaymentCommand): The current payment command.
            is_success (bool): Whether the command is a success or failure.
            seq (int): The sequence number of the payment command.
            error (Exception, optional): The exception, if the command is a
                                         failure. Defaults to None.
        """
        _, channel, _ = self.get_context()
        other_addr = channel.get_other_address()

        self.processor.process_command(
            other_addr=other_addr,
            command=command,
            seq=seq,
            status_success=is_success,
            error=error
        )

    def next_seq(self):
        ''' Returns the next sequence number in the common sequence.'''
        return len(self.command_sequence)

    def get_context(self):
        """ Returns a (vasp, channel, executor) context.

            Returns:
                (OffChainVASP, VASPPairChannel, ProtocolExecutor): The context.
        """
        return (self.channel.get_vasp(), self.channel, self)

    # def sequence_next_command(self, command, do_not_sequence_errors=False):
    #     """ Sequence the next command in the shared sequence.

    #     Args:
    #         command (PaymentCommand): The next command to sequence.
    #         do_not_sequence_errors (bool, optional): Whether to sequence errors.
    #                                                  Defaults to False.

    #     Raises:
    #         ExecutorException: If an error occured when sequencing the command.

    #     Returns:
    #         int: The position of the command in the sequence.
    #     """

    #     try:
    #         all_good = True
    #         _, channel, _ = self.get_context()
    #         my_address = channel.get_my_address()
    #         other_address = channel.get_other_address()
    #         self.processor.check_command(my_address, other_address, command)

    #         self.command_sequence += [command]

    #     except Exception as e:
    #         all_good = False
    #         type_str = f'{str(type(e))}: {e}'
    #         logger.error(f'(other:{self.other_name}) {type_str}', exc_info=True)

    #         raise ExecutorException(type_str)

    #     finally:
    #         # Sequence if all is good, or if we were asked to. Note that
    #         # we do sequence command failure, if the failure is due to a
    #         # high level protocol failure (for audit).
    #         if all_good:
    #             pass

    def extend_sequence(self, command):
        self.command_sequence += [command]

    def set_success(self, command):
        ''' Sets the command at a specific sequence number to be a success.

            Turn all objects created to be actually live, and call the
            CommandProcessor to drive the protocol forward.

            Args:
                seq_no (int): A specific sequence number.
        '''

        self.command_status_sequence += [True]
        seq_no = len(self.command_status_sequence)

        # Call the command processor.
        logger.info(
            f'(other:{self.other_name}) '
            f'Confirm success of command #{seq_no}'
        )

        self.set_outcome(command, is_success=True, seq=seq_no)

    def set_fail(self, command, error=None):
        ''' Sets the command at a specific sequence number to be a failure.

            Remove all potentially live objects from the database, to trigger
            failure of subsequent commands that depend on them.

            Args:
                seq_no (int): A specific sequence number.
        '''
        #assert seq_no == self.last_confirmed
        self.command_status_sequence += [False]
        seq_no = len(self.command_status_sequence)

        # Call the command processor.
        logger.info(
            f'(other:{self.other_name}) '
            f'Confirm failure of command #{seq_no}'
        )
        # command = self.command_sequence[seq_no]
        self.set_outcome(command, is_success=False, seq=seq_no, error=error)
