# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

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

    def __eq__(self, other):
        val = (self.dependencies == other.dependencies and
               self.creates_versions == other.creates_versions and
               self.origin == other.origin)
        return val


    def get_request_cid(self):
        """ Suggests the cid that the request with this command should contain.

        Each cid should ideally be unique, and the same command should create a
        request with the same cid. """
        raise NotImplementedError()  # pragma: no cover


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
        return set(v for _,v in self.dependencies)

    def get_new_object_versions(self):
        ''' Get the list of version numbers created by this command.

            Returns:
                list: A list of version numbers.
        '''
        return set(v for _, v in self.creates_versions)

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

        for pair in zip(self.dependencies, self.creates_versions):
            k, v = pair

        data_dict = {
            "_reads":     dict(self.dependencies),
            "_writes": dict(self.creates_versions),
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
        self.dependencies = list((k,v) for k,v in data['_reads'].items())
        self.creates_versions = list((k,v) for k,v in data['_writes'].items())
        if flag == JSONFlag.STORE:
            if "_origin" in data:
                self.origin = LibraAddress.from_encoded_str(data["_origin"])
        return self
