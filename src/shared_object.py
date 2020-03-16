from copy import deepcopy
from utils import get_unique_string,JSONSerializable

# Generic interface to a shared object

class SharedObject(JSONSerializable):
    def __init__(self):
        ''' All objects have a version number and their commit status '''
        self.version = get_unique_string()
        self.extends = [] # Stores the previous version of the object

        # Flags indicate the state of the object in the store
        self.potentially_live = False   # Pending commands could make it live
        self.actually_live = False   # Successful command made it live

    def new_version(self, new_version = None):
        ''' Make a deep copy of an object with a new version number '''
        clone = deepcopy(self)
        clone.extends = [ self.get_version() ]
        clone.version = new_version
        if clone.version is None:
            clone.version = get_unique_string()

        # New object are neither potentially or actually live
        clone.potentially_live = False   # Pending commands could make it live
        clone.actually_live = False   # Successful command made it live
        return clone

    def get_version(self):
        ''' Return a unique version number to this object and version '''
        return self.version
    
    def set_version(self, version):
        ''' Sets the version of the objects. Useful for contructors. '''
        self.version = version

    def get_potentially_live(self):
        return self.potentially_live

    def set_potentially_live(self, flag):
        self.potentially_live = flag

    def get_actually_live(self):
        return self.actually_live

    def set_actually_live(self, flag):
        self.actually_live = flag

    def get_json_data_dict(self, flag, update_dict = None):
        ''' Get a data dictionary compatible with JSON serilization (json.dumps) '''
        if update_dict is None:
            update_dict = {}

        update_dict.update({
            'version' : self.version,
            'extends' : self.extends,
            'potentially_live' : self.potentially_live,
            'actually_live' : self.actually_live
        })

        self.add_object_type(update_dict)
        return update_dict

    @classmethod
    def from_json_data_dict(cls, data, flag, self):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        assert self is not None
        self.version = data['version']
        self.extends = data['extends']
        self.potentially_live = bool(data['potentially_live'])
        self.actually_live = bool(data['actually_live'])
