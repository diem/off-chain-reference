from status_logic import TypeEnumeration

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
                for field, field_type, _, _ 
                in cls.fields
            }
        return parse_map


    def get_full_record(self):
        ''' Returns a hierarchy of diffs applied to this object and children'''
        parse = self.parse_map()
        diff = {}
        for new_diff in self.update_record:
            for field in new_diff:
                xtype, parse_more = parse[field]
                if not parse_more:
                    # We serialize JSON native types directly
                    if xtype in {str, int, list, dict}:
                        diff[field] = new_diff[field]
                    else:
                        diff[field] = str(new_diff[field])

        for field in parse:
            xtype, parse_more = parse[field]
            if field in self.data and parse_more:
                inner_diff = self.data[field].get_full_record()
                if inner_diff != {}:
                    diff[field] = inner_diff

        return diff

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
                        (field, field_type, type(actual_type)))

                # Check you can write again
                if field in self.data and write_mode == WRITE_ONCE:
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
JSONFlag = TypeEnumeration([
    'NET',
    'STORE'
])

class JSONParsingError(Exception):
    pass

class JSONSerializable:
    def get_json_data_dict(self, flag):
        ''' Get a data disctionary compatible with JSON serilization (json.dumps) '''
        raise NotImplementedError()

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        raise NotImplementedError()

# Utilities

def get_unique_string():
    ''' Returns a strong random 16 byte string encoded in base64. '''
    return standard_b64encode(urandom(16)).decode('ascii')
