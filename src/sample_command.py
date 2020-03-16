from executor import ProtocolCommand
from utils import JSONFlag
from shared_object import SharedObject

class SampleObject(SharedObject):
    def __init__(self, item):
        SharedObject.__init__(self)
        self.item = item

class SampleCommand(ProtocolCommand):
    def __init__(self, command, deps=None):
        ProtocolCommand.__init__(self)
        command = SampleObject(command)
        if deps is None:
            self.dependencies = []
        else:
            self.dependencies = deps
        self.creates   = [ command.item ]
        self.command   = command
        self.always_happy = True

    def get_object(self, version_number, dependencies):
        return self.command

    def item(self):
        return self.command.item

    def __eq__(self, other):
        return self.dependencies == other.dependencies \
            and self.creates == other.creates \
            and self.command.item == other.command.item

    def __str__(self):
        return 'CMD(%s)' % self.item()

    def get_json_data_dict(self, flag):
        data_dict = ProtocolCommand.get_json_data_dict(self, flag)
        data_dict["command"] = self.command.item
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        self = SampleCommand(data['command'], data['dependencies'])
        if flag == JSONFlag.STORE:
            self.commit_status = data["commit_status"]
        return self

    @classmethod
    def json_type(self):
        return "SampleCommand"
