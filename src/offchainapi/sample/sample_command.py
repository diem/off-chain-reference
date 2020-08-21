# Copyright (c) Facebook, Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ..protocol_command import ProtocolCommand
from ..utils import JSONSerializable
from ..shared_object import SharedObject

@JSONSerializable.register
class SampleObject(SharedObject):
    def __init__(self, item):
        SharedObject.__init__(self)
        self.item = item

@JSONSerializable.register
class SampleCommand(ProtocolCommand):
    def __init__(self, command, deps=None):
        ProtocolCommand.__init__(self)
        command = SampleObject(command)
        if deps is None:
            self.dependencies = []
        else:
            self.dependencies = deps
        self.creates_versions   = [ command.item ]
        self.command   = command
        self.always_happy = True

    def get_object(self, version_number, dependencies):
        return self.command

    def item(self):
        return self.command.item

    def __eq__(self, other):
        return self.dependencies == other.dependencies \
            and self.creates_versions == other.creates_versions \
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
        self = super().from_json_data_dict(data, flag)
        self.command = SampleObject(data['command'])
        self.dependencies = data['_dependencies']
        assert type(self) == cls
        return self

    @classmethod
    def json_type(self):
        return "SampleCommand"
