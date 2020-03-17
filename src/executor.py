from utils import JSONSerializable, JSONFlag
from command_processor import CommandProcessor
from libra_address import LibraAddress
from shared_object import SharedObject

# Interface we need to do commands:
class ProtocolCommand(JSONSerializable):
    def __init__(self):
        self.dependencies = []
        self.creates   = []
        self.commit_status = None
        self.origin = None # Takes a LibraAddress
    
    def set_origin(self, origin):
        ''' Sets the Libra address that proposed this command '''
        assert self.origin == None or origin == self.origin
        self.origin = origin
    
    def get_origin(self):
        ''' Gets the Libra address that proposed this command '''
        return self.origin

    def get_dependencies(self):
        ''' Get the list of dependencies. This is a list of version numbers. '''
        return set(self.dependencies)

    def new_object_versions(self):
        ''' Get the list of version numbers created by this command. '''
        return set(self.creates)

    def get_object(self, version_number, dependencies):
        ''' Returns the actual shared object with this version number. '''
        assert version_number in self.new_object_versions()
        raise NotImplementedError('You need to subclass and override this method')

    def get_json_data_dict(self, flag):
        ''' Get a data dictionary compatible with JSON serilization (json.dumps) '''
        data_dict = {
            "dependencies" : self.dependencies,
            "creates"    : self.creates,
        }

        if flag == JSONFlag.STORE:
            data_dict.update({
                "commit_status" : self.commit_status,
            })
            if self.origin is not None:
                data_dict.update({
                    "origin" : self.origin.plain()
                })

        self.add_object_type(data_dict)
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        self = cls.__new__(cls)
        ProtocolCommand.__init__(self)
        self.dependencies = list(data['dependencies'])
        self.creates = list(data['creates'])
        if flag == JSONFlag.STORE:
            self.commit_status = data["commit_status"]
            if "origin" in data:
                self.origin = LibraAddress(data["origin"])
        return self


class ExecutorException(Exception):
    pass

class ProtocolExecutor:
    def __init__(self, channel, processor):

        if __debug__:
            # No need for this import unless we are debugging
            from protocol import VASPPairChannel
            assert isinstance(processor, CommandProcessor)
            assert isinstance(channel, VASPPairChannel)

        self.processor = processor
        self.channel   = channel

        # <STARTS to persist>

        # Configure storage hierarchy
        vasp = channel.get_vasp()
        storage_factory = vasp.get_storage_factory()
        root = storage_factory.make_value(channel.myself.plain(), None)
        other_vasp = storage_factory.make_value(channel.other.plain(), None, root=root)

        # The common sequence of commands 
        self.command_sequence = storage_factory.make_list('command_sequence', ProtocolCommand, root=other_vasp)

        # The highest sequence command confirmed as success of failure.
        self._last_confirmed = storage_factory.make_value('last_confirmed', int, root=other_vasp)
        if not self._last_confirmed.exists():
            self.last_confirmed = 0

        # This is the primary store of shared objects.
        # It maps version numbers -> objects
        self.object_store = storage_factory.make_dict('object_store', SharedObject, root=other_vasp) # TODO: persist this structure

        # <ENDS to persist>
    
    @property
    def last_confirmed(self):
        return self._last_confirmed.get_value()
    
    @last_confirmed.setter
    def last_confirmed(self, value):
        self._last_confirmed.set_value(value)

    
    def set_outcome(self, command, is_success):
        ''' Execute successful commands, and notify of failed commands'''
        vasp, channel, executor = self.get_context()
        self.processor.process_command(vasp, channel, executor, command, is_success)

    def next_seq(self):
        ''' Returns the next sequence number in the common sequence.'''
        return len(self.command_sequence)

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
    
    def get_context(self):
        """ Returns a (vasp, channel, executor) context. """
        return (self.channel.get_vasp(), self.channel, self)

    def sequence_next_command(self, command, do_not_sequence_errors = False):
        ''' Sequence the next command in the shared sequence. '''
        dependencies = command.get_dependencies()
        all_good = False
        pos = None

        myself = self.channel.get_my_address()
        own = (command.origin == myself)

        try:
            # For our own commands we do speculative execution
            # For the other commands we do actual execution
            predicate_own = lambda obj: obj.get_potentially_live()
            predicate_other = lambda obj: obj.get_actually_live()
            predicate = [predicate_other, predicate_own][own]

            all_good = self.all_true(dependencies, predicate)
            if not all_good:
                raise ExecutorException('Required objects do not exist')

            vasp, channel, executor = self.get_context()
            self.processor.check_command(vasp, channel, executor, command)

            if all_good:
                new_versions = command.new_object_versions()
                for version in new_versions:
                    obj = command.get_object(version, self.object_store)
                    obj.set_potentially_live(True)
                    self.object_store[version] = obj

        # TODO: have a less catch-all exception here to detect expected vs. unexpected exceptions
        except Exception as e:
            all_good = False
            type_str = str(type(e)) +": "+str(e)
            raise ExecutorException(type_str)

        finally:
            # Sequence if all is good, or if we were asked to
            if all_good or not do_not_sequence_errors:
                pos = len(self.command_sequence)
                self.command_sequence += [ command ]

        return pos

    def set_success(self, seq_no):
        ''' Sets the command at a specific sequence number to be a success. '''
        assert seq_no == self.last_confirmed
        self.last_confirmed += 1

        command = self.command_sequence[seq_no]
        
        # Consumes old objects
        dependencies = command.get_dependencies()
        for version in dependencies:
            obj = self.object_store[version]
            obj.set_actually_live(False)
            obj.set_potentially_live(False)
            self.object_store[version] = obj

        # Creates new objects
        new_versions = command.new_object_versions()
        for version in new_versions:
            obj = self.object_store[version]
            obj.set_potentially_live(True)
            obj.set_actually_live(True)
            self.object_store[version] = obj
        
        if command.commit_status is None:
            command.commit_status = True
            self.command_sequence[seq_no] = command
            self.set_outcome(command, is_success=True)
        

    def set_fail(self, seq_no):
        ''' Sets the command at a specific sequence number to be a failure. '''
        assert seq_no == self.last_confirmed
        self.last_confirmed += 1

        command = self.command_sequence[seq_no]

        new_versions = command.new_object_versions()
        for version in new_versions:
            if version in self.object_store:
                obj = self.object_store[version]
                obj.set_actually_live(False)
                obj.set_potentially_live(False)
                del self.object_store[version]
        
        if command.commit_status is None:
            command.commit_status = False
            self.command_sequence[seq_no] = command
            self.set_outcome(command, is_success=False)
