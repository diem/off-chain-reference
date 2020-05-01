from .utils import get_unique_string, JSONSerializable, JSONFlag
from copy import deepcopy
import json


# Generic interface to a shared object
class SharedObject(JSONSerializable):
    """ Subclasses of Shared Objects define instances that are shared between
    VASPs. All shared objects must be JSONSerializable.

    All shared objects have a `version` that is the current version of
    this object, and also link to `previous_versions` that contain a previous
    version of this, or other related objects.

    Once stored an object with a specific version must never change, rather
    a command should be defined and sequenced that takes this object as
    input and generated a new version of this object or other objects.
    """

    def __init__(self):
        ''' All objects have a version number and their commit status. '''
        self.version = get_unique_string()
        self.previous_versions = []  # Stores previous version of the object.

    def new_version(self, new_version=None):
        """ Make a deep copy of an object with a new version number.

        Args:
            new_version (str, optional): a specific new version string
                  to use otherwise a fresh random new version is used.
                  Defaults to None.

        Returns:
            SharedObject: The new shared obeject.
        """
        clone = deepcopy(self)
        clone.previous_versions = [self.get_version()]
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
            '_previous_versions': self.previous_versions,
        })

        self.add_object_type(update_dict)
        return update_dict

    @classmethod
    def from_json_data_dict(cls, data, flag, self=None):
        ''' Override JSONSerializable. '''
        if self is None:
            self = cls.__new__(cls)
        self.version = data['_version']
        self.previous_versions = data['_previous_versions']
        return self

    def pretty(self):
        ''' Returns a string ready for pretty printing.'''
        parsed = self.get_json_data_dict(JSONFlag.STORE)
        s_pretty = json.dumps(parsed, indent=4, sort_keys=True)
        return s_pretty
