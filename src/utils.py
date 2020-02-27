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

    def custom_update_checks(self, diff):
        pass

    def update(self, diff):
        ## Check all types and write mode before update
        all_fields = set()
        for field, field_type, required, write_mode in self.fields:
            all_fields.add(field)
            if field in diff:

                # Check the type is right
                value = diff[field]
                if not isinstance(value, field_type):
                    actual_type = type(value)
                    raise StructureException('Wrong type: field %s, expected %s but got %s' % (field, field_type, type(actual_type)))

                # Check you can write again
                if field in self.data and write_mode == WRITE_ONCE:
                    raise StructureException('Wrong update: field %s cannot be changed')

        ## Do custom checks on object
        self.custom_update_checks(diff)

        ## Check we are not updating unknown fields
        for key in diff:
            if key not in all_fields:
                raise StructureException('Unknown: field %s' % key)

        ## Finally update
        for key in diff:
            self.data[key] = diff[key]

        self.check_structure()

    def check_structure(self):
        for field, field_type, required, _ in self.fields:
            if field in self.data:
                if not isinstance(self.data[field], field_type):
                    actual_type = type(self.data[field])
                    raise StructureException('Wrong type: field %s, expected %s but got %s' % (field, field_type, type(actual_type)))
            else:
                if required == REQUIRED:
                    raise StructureException('Missing field: %s' % field)
