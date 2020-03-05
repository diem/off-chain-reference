''' These interfaces are heavily WIP, as we decide how to best implement the
    above state machines '''

from utils import JSONSerializable, JSON_NET, JSON_STORE

import random

from os import urandom
from base64 import standard_b64encode
from copy import deepcopy
def get_unique_string():
    return standard_b64encode(urandom(16))

# Generic interface to a shared object

class SharedObject:
    def __init__(self):
        ''' All objects have a version number and their commit status '''
        self.version = get_unique_string()
        self.extends = [] # Strores the version of the previous object

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

    def get_potentially_live(self):
        return self.potentially_live

    def set_potentially_live(self, flag):
        self.potentially_live = flag

    def get_actually_live(self):
        return self.actually_live

    def set_actually_live(self, flag):
        self.actually_live = flag


# Interface we need to do commands:
class ProtocolCommand(JSONSerializable):
    def __init__(self):
        self.depend_on = []
        self.creates   = []
        self.commit_status = None

    def get_dependencies(self):
        return set(self.depend_on)

    def new_object_versions(self):
        return set(self.creates)

    def validity_checks(self, dependencies, maybe_own=True):
        raise NotImplementedError('You need to subclass and override this method')

    def get_object(self, version_number, dependencies):
        assert version_number in self.new_object_versions()
        raise NotImplementedError('You need to subclass and override this method')

    def on_success(self):
        raise NotImplementedError('You need to subclass and override this method')

    def on_fail(self):
        raise NotImplementedError('You need to subclass and override this method')


    def get_json_data_dict(self, flag):
        ''' Get a data disctionary compatible with JSON serilization (json.dumps) '''
        data_dict = {
            "depend_on" : self.depend_on,
            "creates"    : self.creates,
        }

        if flag == JSON_STORE:
            data_dict["commit_status"] = self.commit_status

        return data_dict

    @classmethod
    def from_json_data_dict(cls, data):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        raise NotImplemented

class ProtocolExecutor:
    def __init__(self):
        self.seq = []
        self.last_confirmed = 0

        # This is the primary store of shared objects.
        # It maps version numbers -> objects
        self.object_store = { } # TODO: persist this structure

    def next_seq(self):
        return len(self.seq)

    def count_potentially_live(self):
        return sum(1 for obj in self.object_store.values() if obj.get_potentially_live())

    def count_actually_live(self):
        return sum(1 for obj in self.object_store.values() if obj.get_actually_live())

    def all_true(self, versions, predicate):
        for version in versions:
            if version not in self.object_store:
                return False
            obj = self.object_store[version]
            res = predicate(obj)
            if not res:
                return False
        return True

    def sequence_next_command(self, command, do_not_sequence_errors = False, own=True):
        dependencies = command.get_dependencies()

        if own:
            # For our own commands we do speculative execution
            predicate = lambda obj: obj.get_potentially_live()
        else:
            # For the other commands we do actual execution
            predicate = lambda obj: obj.get_actually_live()

        all_good = self.all_true(dependencies, predicate)

        # TODO: Here we need to pass the business logic.
        all_good &= command.validity_checks(self.object_store, own)

        if not all_good and do_not_sequence_errors:
            # TODO: Define proper exception
            raise ExecutorCannotSequence('Cannot sequence')

        pos = len(self.seq)
        self.seq += [ command ]

        if not all_good:
            # TODO: Define proper exception
            raise ExecutorCannotSequence('Invalid ... ')

        if all_good:
            new_versions = command.new_object_versions()
            for version in new_versions:
                obj = command.get_object(version, self.object_store)
                obj.set_potentially_live(True)
                self.object_store[version] = obj

        return pos

    def set_success(self, seq_no):
        assert seq_no == self.last_confirmed
        self.last_confirmed += 1

        command = self.seq[seq_no]
        command.commit_status = True
        # Consumes old objects
        dependencies = command.get_dependencies()
        for version in dependencies:
            del self.object_store[version]

        # Creates new objects
        new_versions = command.new_object_versions()
        for version in new_versions:
            obj = self.object_store[version]
            obj.set_actually_live(True)

        command.on_success()

    def set_fail(self, seq_no):
        assert seq_no == self.last_confirmed
        self.last_confirmed += 1

        command = self.seq[seq_no]
        command.commit_status = False

        new_versions = command.new_object_versions()
        for version in new_versions:
            if version in self.object_store:
                del self.object_store[version]

        command.on_fail()

class ExecutorCannotSequence(Exception):
    pass

# Define mock classes

class SampleObject(SharedObject):
    def __init__(self, item):
        SharedObject.__init__(self)
        self.item = item

class SampleCommand(ProtocolCommand):
    def __init__(self, command, deps=None):
        ProtocolCommand.__init__(self)
        command = SampleObject(command)
        if deps is None:
            self.depend_on = []
        else:
            self.depend_on = deps
        self.creates   = [ command.item ]
        self.command   = command
        self.always_happy = True


    def get_object(self, version_number, dependencies):
        return self.command

    def item(self):
        return self.command.item

    def __eq__(self, other):
        return self.depend_on == other.depend_on \
            and self.creates == other.creates \
            and self.command.item == other.command.item

    def validity_checks(self, dependencies, maybe_own=True):
        return maybe_own or self.always_happy or random.random() > 0.75

    def __str__(self):
        return 'CMD(%s)' % self.item()

    def get_json_data_dict(self, flag):
        data_dict = ProtocolCommand.get_json_data_dict(self, flag)
        data_dict["command"] = self.command.item
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        self = SampleCommand(data['command'], data['depend_on'])
        if flag == JSON_STORE:
            self.commit_status = data["commit_status"]
        return self

    def json_type(self):
        return "SampleCommand"

    def on_success(self):
        # TODO: Notify business logic of success and process PaymentCommand
        return

    def on_fail(self):
        # TODO: Notify business logic of failure
        return
