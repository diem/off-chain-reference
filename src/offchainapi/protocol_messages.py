# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .utils import JSONSerializable, JSONParsingError, JSONFlag
from .errors import OffChainErrorCode


class OffChainException(Exception):
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
        protocol_error (bool): Whether it is a protocol error.
        code (OffchainErrorCode ): The error code.
        message (str): An error message explaining the problem. Defaults to None.
    """

    def __init__(self, protocol_error, code, message=None):
        self.protocol_error = protocol_error

        assert isinstance(code, OffChainErrorCode)
        self.code = code
        self.message = message
        # If no separate message, then message is code.
        if message is None:
            self.message = f'Unspecified error with code "{code.value}"'

    def __eq__(self, other):
        return isinstance(other, OffChainError) \
            and self.protocol_error == other.protocol_error \
            and self.code == other.code

    def get_json_data_dict(self, flag):
        ''' Override JSONSerializable. '''
        data_dict = {
            "protocol_error": self.protocol_error,
            "code": str(self.code.value)
            }

        if self.message is not None:
            data_dict['message'] = self.message

        if __debug__:
            import json
            assert json.dumps(data_dict)
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Override JSONSerializable. '''
        try:
            protocol_error = bool(data['protocol_error'])
            code = OffChainErrorCode[data['code']]
            message = None
            if 'message' in data:
                message = str(data['message'])

            return OffChainError(
                protocol_error,
                code,
                message)
        except Exception as e:
            raise JSONParsingError(*e.args)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'OffChainError({self.code}, protocol={self.protocol_error})'

def get_request_cid_helper(command):
    """ Extract a cid for a request from a command. """
    try:
        return command.get_request_cid()
    except Exception as e:
        # Allow a debug option for simple commands
        if __debug__ :
            return repr(command)
        raise

@JSONSerializable.register
class CommandRequestObject(JSONSerializable):
    """ Represents a command of the Off chain protocol. """

    def __init__(self, command):
        self.cid = get_request_cid_helper(command)
        self.command = command
        self.command_type = command.json_type()

        # Indicates whether the command was confirmed by the other VASP
        self.response = None

    def __eq__(self, other):
        ''' Define equality as field equality. '''
        return isinstance(other, CommandRequestObject) \
            and self.cid == other.cid \
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
            "cid": self.cid,
            "command": self.command.get_json_data_dict(flag),
            "command_type": self.command_type
        }

        self.add_object_type(data_dict)

        if flag == JSONFlag.STORE and self.response is not None:
            data_dict["response"] = self.response.get_json_data_dict(
                JSONFlag.STORE
            )

        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Override JSONSerializable. '''
        try:
            # Use generic/dynamic parse functionality
            command = JSONSerializable.parse(data['command'], flag)
            self = CommandRequestObject(command)
            self.cid = str(data["cid"])
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
        self.cid = None
        self.status = None
        self.error = None

    def __repr__(self):
        return f"Response <cid:{self.cid} status:{self.status} error:{self.error}>"

    def __eq__(self, other):
        return isinstance(other, CommandResponseObject) \
                and self.cid == other.cid \
                and self.status == other.status \
                and self.error == other.error

    def is_protocol_failure(self):
        """ Returns True if the request has a response that is not a protocol
            failure (and we can recover from it).

        Returns:
            bool: If the request has a response that is not a protocol failure.
        """
        return self.status == 'failure' and self.error.protocol_error

    def is_failure(self):
        """ Returns True if the response represents a failure. """
        return self.status == 'failure'

    # define serialization interface

    def get_json_data_dict(self, flag):
        ''' Override JSONSerializable. '''
        data_dict = {
            "cid": self.cid,
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

            if 'cid' in data and data['cid'] is not None:
                self.cid = str(data['cid'])

            self.status = str(data['status'])

            # Check the status is correct
            if self.status not in {'success', 'failure'}:
                raise JSONParsingError(
                    f'Status must be success or failure not {self.status}')

            # TODO: Do we need this special case?
            if self.status == 'success':
                self.cid = str(data['cid'])


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
    response.cid = request.cid
    response.status = 'success'
    return response


def make_protocol_error(request, code, message=None):
    """ Constructs a CommandResponse signaling a protocol failure.
        We do not sequence or store such responses since we can recover
        from them.

    Args:
        request (CommandRequestObject): The request object.
        code (OffchainErrorCode): The error code.
        message (str, optional): A human-readable message about this error.

    Returns:
        CommandResponseObject: The generated response object.
    """
    response = CommandResponseObject()
    response.cid = request.cid
    response.status = 'failure'
    response.error = OffChainError(protocol_error=True, code=code, message=message)
    return response


def make_parsing_error(message=None, code=OffChainErrorCode.parsing_error):
    """ Constructs a CommandResponse signaling a protocol failure.
        We do not sequence or store such responses since we can recover
        from them.

    Args:
        message (str, optional): A human-readable message about this error.

    Returns:
        CommandResponseObject: The generated response object.

    """
    response = CommandResponseObject()
    response.cid = None
    response.status = 'failure'
    response.error = OffChainError(
        protocol_error=True, code=code, message=message)
    return response


def make_command_error(request, code, message=None):
    """ Constructs a CommandResponse signaling a command failure.
        Those failures lead to a command being sequenced as a failure.

    Args:
        request (CommandRequestObject): The request object.
        code (OffchainErrorCode): The error code.
        message (str, optional): A human-readable message about this error.

    Returns:
        CommandResponseObject: The generated response object.
    """
    response = CommandResponseObject()
    response.cid = request.cid
    response.status = 'failure'
    response.error = OffChainError(protocol_error=False, code=code, message=message)
    return response
