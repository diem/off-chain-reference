from .utils import JSONSerializable, JSONParsingError, JSONFlag


class OffChainException(Exception):
    pass


class OffChainOutOfOrder(Exception):
    pass


class OffChainProtocolError(Exception):
    ''' This class denotes protocol errors, namely errors at the
        OffChain protocols level rather than the command sequencing level. '''

    @staticmethod
    def make(protocol_error):
        """Make an OffChainProtocolError with a given error.

        Args:
            protocol_error (str): The protocol error representation.

        Returns:
            OffChainProtocolError: The error object.
        """
        self = OffChainProtocolError()
        self.protocol_error = protocol_error
        return self

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'OffChainProtocolError: {str(self.protocol_error)}'


class OffChainError(JSONSerializable):
    """Represents an OffChainError.

    Args:
        protocol_error (bool, optional): Whether it is a protocol error.
                                         Defaults to True.
        code (int or None, optional): The error code. Defaults to None.
    """

    def __init__(self, protocol_error=True, code=None):
        self.protocol_error = protocol_error
        self.code = code

    def __eq__(self, other):
        return isinstance(other, OffChainError) \
            and self.protocol_error == other.protocol_error \
            and self.code == other.code

    def get_json_data_dict(self, flag):
        ''' Override JSONSerializable. '''
        data_dict = {
            "protocol_error": self.protocol_error,
            "code": self.code
            }
        if __debug__:
            import json
            assert json.dumps(data_dict)
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Override JSONSerializable. '''
        try:
            return OffChainError(
                bool(data['protocol_error']),
                str(data['code']))
        except Exception as e:
            raise JSONParsingError(*e.args)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'OffChainError({self.code}, protocol={self.protocol_error})'


@JSONSerializable.register
class CommandRequestObject(JSONSerializable):
    """ Represents a command of the Off chain protocol. """

    def __init__(self, command):
        self.seq = None          # The sequence in the local queue
        self.command_seq = None  # Only server sets this
        self.signature = None
        self.command = command
        self.command_type = command.json_type()

        # Indicates whether the command was confirmed by the other VASP
        self.response = None

    def __eq__(self, other):
        ''' Define equality as field equality. '''
        return isinstance(other, CommandRequestObject) \
            and self.seq == other.seq \
            and self.command_seq == other.command_seq \
            and self.command == other.command \
            and self.command_type == other.command_type \
            and self.response == other.response

    def is_same_command(self, other):
        """Returns true if the other command is the same as this one,
            Used to detect conflicts in case of buggy corresponding VASP.

        Args:
            other (CommandRequestObject): Another command.

        Returns:
            bool: If the other command is the same as this one.
        """
        return self.command == other.command

    def has_response(self):
        """Returns true if request had a response, false otherwise.

        Returns:
            bool: If request had a response.
        """
        return self.response is not None

    def is_success(self):
        """Returns true if the response was a success.

        Returns:
            bool: If the response was a success.
        """
        assert self.has_response()
        return self.response.status == 'success'

    # define serialization interface
    def get_json_data_dict(self, flag):
        ''' Override JSONSerializable. '''
        data_dict = {
            "seq": self.seq,
            "command": self.command.get_json_data_dict(flag),
            "command_type": self.command_type
        }

        self.add_object_type(data_dict)

        if self.command_seq is not None:
            data_dict["command_seq"] = self.command_seq

        if self.signature is not None:
            data_dict["signature"] = self.signature

        if flag == JSONFlag.STORE and self.response is not None:
            data_dict["response"] = self.response.get_json_data_dict(
                JSONFlag.STORE
            )

        if __debug__:
            import json
            assert json.dumps(data_dict)

        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Override JSONSerializable. '''
        try:
            # Use generic/dynamic parse functionality
            command = JSONSerializable.parse(data['command'], flag)
            self = CommandRequestObject(command)
            self.seq = int(data["seq"])
            if 'command_seq' in data:
                self.command_seq = int(data['command_seq'])
            if 'signature' in data:
                self.signature = data["signature"]
            if flag == JSONFlag.STORE and 'response' in data:
                self.response = CommandResponseObject.from_json_data_dict(
                    data['response'], flag
                )
            return self
        except Exception as e:
            raise JSONParsingError(*e.args)


class CommandResponseObject(JSONSerializable):
    """Represents a response to a command in the Off chain protocol."""

    def __init__(self):
        # Start with no data
        self.seq = None
        self.command_seq = None
        self.status = None
        self.error = None

    def __eq__(self, other):
        return isinstance(other, CommandResponseObject) \
                and self.seq == other.seq \
                and self.command_seq == other.command_seq \
                and self.status == other.status \
                and self.error == other.error

    def is_protocol_failure(self):
        """ Returns True if the request has a response that is not a protocol
            failure (and we can recover from it).

        Returns:
            bool: If the request has a response that is not a protocol failure.
        """
        return self.status == 'failure' and self.error.protocol_error

    # define serialization interface

    def get_json_data_dict(self, flag):
        ''' Override JSONSerializable. '''
        data_dict = {
            "seq": self.seq,
            "command_seq": self.command_seq,
            "status": self.status
        }

        if self.error is not None:
            data_dict["error"] = self.error.get_json_data_dict(flag)

        self.add_object_type(data_dict)
        if __debug__:
            import json
            assert json.dumps(data_dict)

        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Override JSONSerializable. '''
        try:
            self = CommandResponseObject()

            if 'seq' in data and data['seq'] is not None:
                self.seq = int(data['seq'])

            if 'command_seq' in data and data['command_seq'] is not None:
                self.command_seq = data['command_seq']

            self.status = str(data['status'])

            # Only None or int allowed
            if self.command_seq is not None:
                self.command_seq = int(self.command_seq)

            # Check the status is correct
            if self.status not in {'success', 'failure'}:
                raise JSONParsingError(
                    f'Status must be success or failure not {self.status}')

            if self.status == 'success':
                self.seq = int(data['seq'])

            if self.status == 'failure':
                self.error = OffChainError.from_json_data_dict(
                    data['error'], flag)

            return self
        except Exception as e:
            raise JSONParsingError(*e.args)


def make_success_response(request):
    """Constructs a CommandResponse signaling success.

    Args:
        request (CommandRequestObject): The request object.

    Returns:
        CommandResponseObject: The generated response object.
    """
    response = CommandResponseObject()
    response.seq = request.seq
    response.status = 'success'
    return response


def make_protocol_error(request, code=None):
    """ Constructs a CommandResponse signaling a protocol failure.
        We do not sequence or store such responses since we can recover
        from them.

    Args:
        request (CommandRequestObject): The request object.
        code (int or None, optional): The error code. Defaults to None.

    Returns:
        CommandResponseObject: The generated response object.
    """
    response = CommandResponseObject()
    response.seq = request.seq
    response.status = 'failure'
    response.error = OffChainError(protocol_error=True, code=code)
    return response


def make_parsing_error():
    """ Constructs a CommandResponse signaling a protocol failure.
        We do not sequence or store such responses since we can recover
        from them.

    Returns:
        CommandResponseObject: The generated response object.
    """
    response = CommandResponseObject()
    response.seq = None
    response.status = 'failure'
    response.error = OffChainError(protocol_error=True, code='parsing')
    return response


def make_command_error(request, code=None):
    """ Constructs a CommandResponse signaling a command failure.
        Those failures lead to a command being sequenced as a failure.

    Args:
        request (CommandRequestObject): The request object.
        code (int or None, optional): The error code. Defaults to None.

    Returns:
        CommandResponseObject: The generated response object.
    """
    response = CommandResponseObject()
    response.seq = request.seq
    response.status = 'failure'
    response.error = OffChainError(protocol_error=False, code=code)
    return response
