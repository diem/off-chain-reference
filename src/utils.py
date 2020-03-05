REQUIRED = True
OPTIONAL = False

WRITE_ONCE = True
UPDATABLE = False


class StructureException(Exception):
    pass


class StructureChecker:
    def __init__(self):
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

    def get_full_record(self):
        ''' Returns a hierarchy of diffs applied to this object and children'''
        diff = {}
        for new_diff in self.update_record:
            for field in new_diff:
                if isinstance(new_diff[field], StructureChecker):
                    diff[field] = new_diff[field].get_full_record()
                else:
                    if type(new_diff[field]) in {str, int, list}:
                        diff[field] = new_diff[field]
                    else:
                        diff[field] = str(new_diff[field])
        return diff

    def __eq__(self, other):
        ''' Define equality as equality between data fields only '''
        if not isinstance(other, type(self)):
            return False
        for field, value in self.data.items():
            if field not in other.data or not value == other.data[field]:
                return False
        return True

    @classmethod
    def from_full_record(cls, diff):
        ''' Constructs an instance from a diff '''
        parse_further = {
            field: field_type for field,
            field_type,
            _,
            _ in cls.fields if issubclass(
                field_type,
                StructureChecker)}
        constructors = {
            field: field_type for field,
            field_type,
            _,
            _ in cls.fields if not issubclass(
                field_type,
                StructureChecker)}
        self = cls.__new__(cls)
        StructureChecker.__init__(self)
        new_diff = {}
        for field in diff:
            if field in parse_further:
                nested_class = parse_further[field]
                new_diff[field] = nested_class.from_full_record(diff[field])
            else:
                # Use default constructor of the type
                cons = constructors[field]
                new_diff[field] = cons(diff[field])
        self.update(new_diff)
        self.flatten()
        return self

    def custom_update_checks(self, diff):
        pass

    def update(self, diff):
        ''' Applies changes to the object and checks for validity rules '''
        # Check all types and write mode before update
        all_fields = set()
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
                        'Wrong update: field %s cannot be changed')

        # Check we are not updating unknown fields
        for key in diff:
            if key not in all_fields:
                raise StructureException('Unknown: field %s' % key)

        # Finally update
        for key in diff:
            self.data[key] = diff[key]

        self.check_structure()

        # Do custom checks on object
        self.custom_update_checks(diff)

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
JSON_NET = 0
JSON_STORE = 1

class JSONParsingError(Exception):
    pass

class JSONSerializable:
    def get_json_data_dict(self, flag):
        ''' Get a data disctionary compatible with JSON serilization (json.dumps) '''
        raise NotImplemented

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        raise NotImplemented
