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

from .utils import get_unique_string, JSONSerializable, JSONFlag
from copy import deepcopy
import json


# Generic interface to a shared object
class SharedObject(JSONSerializable):
    """ Subclasses of Shared Objects define instances that are shared between
    VASPs. All shared objects must be JSONSerializable.

    All shared objects have a `version` that is the current version of
    this object, and also link to a `previous_version` that contain a previous
    version of this, or other related objects.

    Once stored an object with a specific version must never change, rather
    a command should be defined and sequenced that takes this object as
    input and generated a new version of this object or other objects.
    """

    def __init__(self):
        ''' All objects have a version number and their commit status. '''
        self.version = get_unique_string()
        self.previous_version = None  # Stores previous version of the object.

    def new_version(self, new_version=None, store=None):
        """ Make a deep copy of an object with a new version number.

        Args:
            new_version (str, optional): a specific new version string
                  to use otherwise a fresh random new version is used.
                  Defaults to None.
            store (dict-like, optional): a persistant store that given
                  a version number key, returns a *fresh* instance of
                  the object.

        Returns:
            SharedObject: The new shared obeject.
        """
        if store:
            clone = store[self.version]
        else:
            clone = deepcopy(self)

        clone.previous_version = self.get_version()
        clone.version = new_version
        if clone.version is None:
            clone.version = get_unique_string()

        return clone

    def get_version(self):
        """Return a unique version number to this object and version.

        Returns:
            int: The version number.
        """
        return self.version

    def set_version(self, version):
        """ Sets the version of the objects. Useful for contructors.

        Args:
            version (int): The version of the object.
        """
        self.version = version

    def get_json_data_dict(self, flag, update_dict=None):
        ''' Override JSONSerializable. '''
        if update_dict is None:
            update_dict = {}

        update_dict.update({
            '_version': self.version,
            '_previous_version': self.previous_version,
        })

        self.add_object_type(update_dict)
        return update_dict

    @classmethod
    def from_json_data_dict(cls, data, flag, self=None):
        ''' Override JSONSerializable. '''
        if self is None:
            self = cls.__new__(cls)
        self.version = data['_version']
        self.previous_version = data['_previous_version']
        return self
