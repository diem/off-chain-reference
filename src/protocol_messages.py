from utils import JSONSerializable, JSONParsingError, JSON_NET, JSON_STORE
from executor import SampleCommand

class OffChainError(JSONSerializable):
    def __init__(self, protocol_error=True, code=None):
        self.protocol_error = protocol_error
        self.code = code

    def __eq__(self, other):
        return self.protocol_error == other.protocol_error \
           and self.code == other.code

    def get_json_data_dict(self, flag):
        ''' Get a data dictionary compatible with JSON serilization (json.dumps) '''
        data_dict = {
            "protocol_error" : self.protocol_error,
            "code" : self.code
            }
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        try:
            return OffChainError(bool(data['protocol_error']), str(data['code']))
        except Exception as e:
            raise JSONParsingError(*e.args)


class CommandRequestObject(JSONSerializable):
    """Represents a command of the Off chain protocol"""

    type_map = {
        "SampleCommand": SampleCommand
    }

    def __init__(self, command):
        self.seq = None          # The sequence in the local queue
        self.command_seq = None  # Only server sets this
        self.command = command
        self.command_type = command.json_type()

        # Indicates whether the command was been confirmed by the other VASP
        self.response = None

    def __eq__(self, other):
        ''' Define equality as field equality '''
        return self.seq == other.seq \
           and self.command_seq == other.command_seq \
           and self.command == other.command \
           and self.command_type == other.command_type \
           and self.response == other.response

    def is_same_command(self, other):
        """ Returns true if the other command is the same as this one,
            Used to detect conflicts in case of buggy corresponding VASP."""
        return self.command == other.command

    def has_response(self):
        """ Returns true if request had a response, false otherwise """
        return self.response is not None

    def is_success(self):
        """ Returns true if the response was a success """
        assert self.has_response()
        return self.response.status == 'success'

    # define serialization interface

    def get_json_data_dict(self, flag):
        ''' Get a data dictionary compatible with JSON serilization (json.dumps) '''
        data_dict = {
            "seq" : self.seq,
            "command" : self.command.get_json_data_dict(flag),
            "command_type" : self.command_type
            }

        if self.command_seq is not None:
            data_dict["command_seq"] = self.command_seq

        if flag == JSON_STORE and self.response is not None:
            data_dict["response"] = self.response.get_json_data_dict(JSON_STORE)

        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        try:
            cmd_type = cls.type_map[data["command_type"]]
            command = cmd_type.from_json_data_dict(data['command'], flag)
            self = CommandRequestObject(command)
            self.seq = int(data["seq"])
            if 'command_seq' in data:
                self.command_seq = int(data['command_seq'])
            if flag == JSON_STORE and 'response' in data:
                self.response = CommandResponseObject.from_json_data_dict(data['response'], flag)
            return self
        except Exception as e:
            raise JSONParsingError(*e.args)

class CommandResponseObject(JSONSerializable):
    """Represents a response to a command in the Off chain protocol"""

    def __init__(self):
        # Start with no data
        self.seq = None
        self.command_seq = None
        self.status = None
        self.error = None

    def __eq__(self, other):
        return self.seq == other.seq \
           and self.command_seq == other.command_seq \
           and self.status == other.status \
           and self.error  == other.error


    def not_protocol_failure(self):
        """ Returns True if the request has a response that is not a protocol
            failure (and we can recover from it)
        """
        return self.status == 'success' or (
                self.status == 'failure' and not self.error.protocol_error)

    # define serialization interface

    def get_json_data_dict(self, flag):
        ''' Get a data disctionary compatible with JSON serilization (json.dumps) '''
        data_dict = {
            "seq" : self.seq,
            "command_seq" : self.command_seq,
            "status" : self.status
        }

        if self.error is not None:
            data_dict["error"] = self.error.get_json_data_dict(flag)
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        try:
            self = CommandResponseObject()
            self.seq = int(data['seq'])
            self.command_seq = data['command_seq']
            self.status = str(data['status'])

            # Only None or int allowed
            if self.command_seq is not None:
                self.command_seq = int(self.command_seq)

            # Check the status is correct
            if self.status not in {'success', 'failure'}:
                raise JSONParsingError('Status must be success or failure not %s' % self.status)

            if self.status == 'failure':
                self.error = OffChainError.from_json_data_dict(data['error'], flag)

            return self
        except Exception as e:
            raise JSONParsingError(*e.args)
