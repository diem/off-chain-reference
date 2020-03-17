from enum import Enum
from os import urandom
from base64 import standard_b64encode
from copy import deepcopy



REQUIRED = True
OPTIONAL = False

WRITE_ONCE = True
UPDATABLE = False


class StructureException(Exception):
    pass


class StructureChecker:
    ''' A class that allows us to keep track of objects in terms of 
    diffs, namely operations that mutate their fields. Also does 
    automatic type checking and checking for mutability/immutability
    and required / optional fields.'''

    fields = {}

    def __init__(self):
        ''' Initialize the class. Presumes a class level variable fields is defined. '''
        assert self.fields
        self.data = {}
        self.update_record = []
    
    def __getattr__(self, name):
        ''' Provide a more humaine interface to the data '''
        if name == "data":
            raise AttributeError()
        if name in self.data:
            return self.data[name]
        raise AttributeError()


    def record(self, diff):
        ''' Record all diffs applied to the object '''
        self.update_record += [diff]

    def flatten(self):
        ''' Resets all diffs applied to this object '''
        self.update_record = []
        for field in self.data:
            if isinstance(self.data[field], StructureChecker):
                self.data[field].flatten()

    @classmethod
    def parse_map(cls):
        ''' Returns a map of fields to their respective type, and whether
            the type is a subclass of StructureChecker. '''
        parse_map = {
                field: (field_type, issubclass(field_type, StructureChecker))
                for field, field_type, _, _ in cls.fields
            }
        return parse_map


    def get_full_record(self):
        ''' Returns a hierarchy of diffs applied to this object and children'''
        parse = self.parse_map()
        diff = {}
        for field in self.data:
            xtype, parse_more = parse[field]
            if parse_more:
                diff[field] = self.data[field].get_full_record()
            else:
                if xtype in {str, int, list, dict}:
                    diff[field] = self.data[field]
                elif issubclass(xtype, Enum):
                    diff[field] = self.data[field].name
                else:
                    diff[field] = str(self.data[field])
        return diff
    
    def has_changed(self):
        parse = self.parse_map()
        for new_diff in self.update_record:
            for field in new_diff:
                return True

        for field in self.data:
            _, parse_more = parse[field]
            if parse_more:
                if self.data[field].has_changed():
                    return True
        
        return False

    def __eq__(self, other):
        ''' Define equality as equality between data fields only '''
        if not isinstance(other, type(self)):
            return False
        if set(self.data) != set(other.data):
            return False
        for field, value in self.data.items():
            if not value == other.data[field]:
                return False
        return True


    @classmethod
    def from_full_record(cls, diff, base_instance = None):
        ''' Constructs an instance from a diff. '''
        
        if base_instance is None:
            self = cls.__new__(cls)
            StructureChecker.__init__(self)
        else:
            # TODO: Profile and see if this deep copy is necessary.
            self = deepcopy(base_instance)
        
        parse = cls.parse_map()
        new_diff = {}
        for field in diff:
            if field in parse:
                xtype, parse_further = parse[field]

                if parse_further:

                    if field in self.data:
                        # When the instance exists we update it in place, and
                        # We do not register this as a field update
                        # (to respect WRITE ONCE).
                        existing_instance = self.data[field]
                        self.data[field] = xtype.from_full_record(diff[field], existing_instance)
                    else:
                        new_diff[field] = xtype.from_full_record(diff[field])
                else:
                    # Use default constructor of the type
                    if xtype in {int, str, list}:
                        new_diff[field] = xtype(diff[field])
                    elif issubclass(xtype, Enum):
                        new_diff[field] = xtype[diff[field]]
                    else:
                        new_diff[field] = xtype(diff[field])

            else:
                # We tolerate fielse we do not know about, but ignore them
                # TODO: log unknown fields?
                pass

        self.update(new_diff)
        return self

    def custom_update_checks(self, diff):
        ''' Overwrite this class to implement more complex 
            custom checks on a diff. '''
        pass

    def update(self, diff):
        ''' Applies changes to the object and checks for validity rules '''
        # Check all types and write mode before update
        all_fields = set()
        updates = False
        for field, field_type, required, write_mode in self.fields:
            all_fields.add(field)
            if field in diff:

                # Check the type is right
                value = diff[field]
                if not isinstance(value, field_type):
                    actual_type = type(value)
                    raise StructureException(
                        'Wrong type: field %s, expected %s but got %s' %
                        (field, field_type, actual_type))

                # Check you can write again
                if field in self.data and write_mode == WRITE_ONCE:
                    if self.data[field] !=  diff[field]:
                        raise StructureException(
                            'Wrong update: field %s cannot be changed' % field)

        # Check we are not updating unknown fields
        for key in diff:
            if key not in all_fields:
                raise StructureException('Unknown: field %s' % key)

        # Finally update
        for key in diff:
            if key not in self.data or self.data[key] != diff[key]:
                self.data[key] = diff[key]
                updates = True

        self.check_structure()

        # Do custom checks on object
        self.custom_update_checks(diff)

        if updates:
            self.record(diff)

    def check_structure(self):
        ''' Checks all structural requirements are met '''
        for field, field_type, required, _ in self.fields:
            if field in self.data:
                if not isinstance(self.data[field], field_type):
                    actual_type = type(self.data[field])
                    raise StructureException(
                        'Wrong type: field %s, expected %s but got %s' %
                        (field, field_type, type(actual_type)))
            else:
                if required == REQUIRED:
                    raise StructureException('Missing field: %s' % field)

# define serializaqtion flags
class JSONFlag(Enum):
    NET = 'NET'
    STORE = 'STORE'

class JSONParsingError(Exception):
    pass

class JSONSerializable:

    # Define a type map for decoding
    # It maps ObjectType attributes to a JSONSerializable subclass
    json_type_map = {}

    def get_json_data_dict(self, flag, update_dict = None):
        ''' Get a data dictionary compatible with JSON serilization (json.dumps) '''
        raise NotImplementedError()

    @classmethod
    def from_json_data_dict(cls, data, flag, self=None):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        raise NotImplementedError()
    
    @classmethod
    def json_type(cls):
        ''' Overwrite this method to have a nicer json type identifier.'''
        return str(cls)
    
    @classmethod
    def register(cls, other_cls):
        cls.json_type_map[other_cls.json_type()] = other_cls
        return other_cls
    
    @classmethod
    def add_object_type(cls, value_dict):
        assert 'ObjectType' not in value_dict
        value_dict['ObjectType'] = cls.json_type()
        return value_dict
    
    @classmethod
    def parse(cls, data, flag):
        if 'ObjectType' not in data:
            print(data)
            raise JSONParsingError('No object type information')

        if data['ObjectType'] not in cls.json_type_map:
            raise JSONParsingError('Unknown object type: %s' % data['ObjectType'])

        new_cls = cls.json_type_map[data['ObjectType']]
        return new_cls.from_json_data_dict(data, flag)

# Utilities

def get_unique_string():
    ''' Returns a strong random 16 byte string encoded in base64. '''
    return standard_b64encode(urandom(16)).decode('ascii')
