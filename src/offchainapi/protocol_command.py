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

from .utils import JSONSerializable, JSONFlag
from .command_processor import CommandProcessor
from .libra_address import LibraAddress
from .protocol_messages import CommandRequestObject

import logging


logger = logging.getLogger(name='libra_off_chain_api.protocol_command')


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

    def get_new_object_versions(self):
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
                self.origin = LibraAddress.from_encoded_str(data["_origin"])
        return self
