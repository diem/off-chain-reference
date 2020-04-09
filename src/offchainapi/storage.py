# The main storage interface

import dbm
import json
from pathlib import PosixPath

from .utils import JSONFlag, JSONSerializable, get_unique_string

class Storable:
    """ Base class for objects that can be stored """

    def __init__(self, xtype):
        """ Specify the type (or base type) of the objects to be stored """
        self.xtype = xtype
        self.factory = None

    def pre_proc(self, val):
        """ Pre-processing of objects before storage. By default 
            it calls get_json_data_dict for JSONSerializable objects or
            their base type. eg int('10'). The result must be a structure
            that can be passed to json.dumps.
        """
        if issubclass(self.xtype, JSONSerializable):
            return val.get_json_data_dict(JSONFlag.STORE)
        else:
            return self.xtype(val)
    
    def post_proc(self, val):
        """ Post-processing to convert a json parsed structure into a Python
            object. It uses parse on JSONSerializable objects, and otherwise
            the type constructor. """
        if issubclass(self.xtype, JSONSerializable):
            return self.xtype.parse(val, JSONFlag.STORE)
        else:
            # assert not self.xtype.issubclass(JSONSerializable)
            return self.xtype(val)

class StorableFactory:
    ''' This class maintains an overview of the full storage subsystem.'''

    def __init__(self, db):
        self.db = db
        self.current_transaction = None
        self.levels = 0

        # Transaction cache: keep data in memory
        # until the transaction completes.
        self.cache = {}
        self.del_cache = set()

        # Check and fix the database, if this is needed
        self.crash_recovery()

    def make_value(self, name, xtype, root = None, default=None):
        ''' A new value-like storable'''
        v = StorableValue(self, name, xtype, root, default)
        v.factory = self
        return v

    def make_list(self, name, xtype, root):
        ''' A new list-like storable'''
        v = StorableList(self, name, xtype, root)
        v.factory = self
        return v

    def make_dict(self, name, xtype, root):
        ''' A new map-like storable'''
        v = StorableDict(self, name, xtype, root)
        v.factory = self
        return v

    # Define central interfaces as a dictionary structure 
    # (with no keys or value enumeration)

    def __getitem__(self, key):
        # First look into the cache
        if key in self.del_cache:
            raise KeyError('The key is to be deleted.')
        if key in self.cache:
            return self.cache[key]
        return self.db[key]

    def __setitem__(self, key, value):
        # Ensure all writes are within a transaction.
        if self.current_transaction is None:
            raise RuntimeError('Writes must happen within a transaction context')
        self.cache[key] = value
        if key in self.del_cache:
            self.del_cache.remove(key)
    
    def __contains__(self, item):
        if item in self.cache:
            return True
        return item in self.db
    
    def __delitem__(self, key):
        if self.current_transaction is None:
            raise RuntimeError('Writes must happen within a transaction context')
        if key in self.cache:
            del self.cache[key]
        self.del_cache.add(key)
        
    def persist_cache(self):
        ''' Safely persist the cache once the transaction is over. '''
        
        from itertools import chain

        # Create a backup of all affected values.
        old_entries = {}
        non_existent_entries = []
        for key in chain(self.cache.keys(), self.del_cache):
            if key in self.db:
                old_entries[key] = self.db[key]
            else:
                non_existent_entries += [ key ]
        
        backup_data = json.dumps([old_entries, non_existent_entries])
        self.db['__backup_recovery'] = backup_data
        # TODO: call to flush to disk

        # Write new values to the database
        for item in self.cache:
            self.db[item] = self.cache[item]
        for item in self.del_cache:
            if item in self.db:
                del self.db[item]
        
        # Upon completion of write, clean up
        del self.db['__backup_recovery']
        self.cache = {}
        self.del_cache = set()

    def crash_recovery(self):
        ''' Detects whether a database contains potentially inconsistent state
            and recovers a good state of the database. '''

        if '__backup_recovery' not in self.db:
            return
        
        # Recover the old good state.
        backup_data = json.loads(self.db['__backup_recovery'])
        old_entries = backup_data[0]
        non_existent_entries = backup_data[1]

        # Note, this may be executed many times in case of crash during
        # crash recovery. 
        for item in old_entries:
            self.db[item] = old_entries[item]
        for item in non_existent_entries:
            if item in self.db:
                del self.db[item]
        
        # TODO: Ensure the writes are complete?
        del self.db['__backup_recovery']

    # Define the interfaces as a context manager

    def atomic_writes(self):
        ''' Returns a context that ensures all writes in its body are atomic '''
        return self

    def __enter__(self):
        if self.levels == 0:
            self.current_transaction = get_unique_string()

        #print('Enter Tx %s (%s)' % (self.current_transaction, self.levels))
        self.levels += 1

    def __exit__(self, type, value, traceback):
        #print('Exit Tx', self.current_transaction)
        self.levels -= 1
        if self.levels == 0:
            self.current_transaction = None
            # print('Commit')
            # TODO: commit state
            self.persist_cache()

class StorableDict(Storable):

    def __init__(self, db, name, xtype, root=None):
        """ Implements a persistent dictionary like type. Entries are stored
            by key directly, and a separate doubly linked list structure is
            stored to enable traversal of keys and values. """
        if root is None:
            self.root = PosixPath('/')
        else:
            self.root = root.base_key()
        self.name = name
        self.db = db
        self.xtype = xtype

        # We create a doubly linked list to support traveral with O(1) lookup
        # addition and creation.
        meta = StorableValue(db, '__META', str, root=self)
        self.first_key = StorableValue(db, '__FIRST_KEY', str, root=meta)
        self.length = StorableValue(db, '__LEN', int, root=meta, default=0)

        
    def base_key(self):
        return self.root / self.name

    def __getitem__(self, key):
        db_key = str(self.base_key() / str(key))
        return self.post_proc(json.loads(self.db[db_key]))

    def __setitem__(self, key, value):
        db_key = str(self.base_key() / str(key))
        db_key_LL = str(self.base_key() / 'LL' / str(key))
        data = json.dumps(self.pre_proc(value))

        # Ensure nothing fails after that

        if db_key not in self.db:
            assert db_key_LL not in self.db
            xlen = self.length.get_value()
            self.length.set_value(xlen+1)

            # Make the linked list entry
            if self.first_key.exists():
                # All new entries to the front
                first_value_key = self.first_key.get_value()

                # Format of the LL_entry is:
                # [prev_LL_key, next_LL_key, db_key, key]
                ll_entry = [None, first_value_key, str(db_key), key]

                # Modify the record of first value
                first_ll_entry = json.loads(self.db[first_value_key])
                first_ll_entry[0] = db_key_LL
                self.db[first_value_key] = json.dumps(first_ll_entry)

            else:
                # This is the first entry, setup the record and first key
                ll_entry = [None, None, str(db_key), key]
            
            self.first_key.set_value(str(db_key_LL))
            self.db[db_key_LL] = json.dumps(ll_entry)

        self.db[db_key] = data
    
    def keys(self):
        if not self.first_key.exists():
            return
        ll_value_key = self.first_key.get_value()
        while True:
            ll_entry = json.loads(self.db[ll_value_key])
            #if len(ll_entry) < 2:
            #    print('DEBUG'*3, ll_entry)
            ll_value_key = ll_entry[1]
            yield ll_entry[3]
            if ll_value_key is None:
                break
    
    def values(self):
        for k in self.keys():
            yield self[k]

    def __len__(self):
        xlen =  self.length.get_value()
        return xlen

    def __delitem__(self, key):
        db_key = str(self.base_key() / str(key))
        if db_key in self.db:
            xlen = self.length.get_value()
            self.length.set_value(xlen-1)
            del self.db[db_key]

            # Now fix the LL structure
            db_key_LL = str(self.base_key() / 'LL' / str(key))
            ll_entry = json.loads(self.db[db_key_LL])
            prev_key, next_key, _, _ = tuple(ll_entry)

            prev_entry = None
            if prev_key is not None:
                prev_entry = json.loads(self.db[prev_key])
                prev_entry[1] = next_key
                self.db[prev_key] = json.dumps(prev_entry)
            
            next_entry = None
            if next_key is not None:
                next_entry = json.loads(self.db[next_key])
                next_entry[0] = prev_key
                self.db[next_key] = json.dumps(next_entry)
                if prev_key is None:
                    self.first_key.set_value(next_key)
            
            del  self.db[db_key_LL]
            
    
    def __contains__(self, item):
        db_key = str(self.base_key() / str(item))
        return db_key in self.db


class StorableList(Storable):
    
    def __init__(self, db, name, xtype, root=None):
        if root is None:
            self.root = PosixPath('/')
        else:
            self.root = root.base_key()
        self.name = name
        self.db = db
        self.xtype = xtype

        self.length = StorableValue(db, '__LEN', int, root=self, default=0)
        if not self.length.exists():
            self.length.set_value(0)


    def base_key(self):
        return self.root / self.name
    
    def __getitem__(self, key):
        if type(key) is not int:
            raise KeyError('Key must be an int.')
        xlen = len(self)
        if not 0 <= key < xlen:
            raise KeyError('Key does not exist')

        db_key = str(self.base_key() / str(key))
        return self.post_proc(json.loads(self.db[db_key]))

    def __setitem__(self, key, value):
        if type(key) is not int:
            raise KeyError('Key must be an int.')
        xlen = len(self)
        if not 0<= key < xlen:
            raise KeyError('Key does not exist')
        db_key = str(self.base_key() / str(key))
        self.db[db_key] = json.dumps(self.pre_proc(value))

    def __len__(self):
        xlen =  self.length.get_value()
        assert type(xlen) is int
        return xlen
    
    def __iadd__(self, other):
        for item in other:
            assert isinstance(item, self.xtype)
            xlen = self.length.get_value()
            self.length.set_value(xlen+1)
            self[xlen] = item
            return self

    def __iter__(self):
        for key in range(len(self)):
            yield self[key]


class StorableValue(Storable):
    """ Implements a cached persistent value. The value is stored to storage
        but a cached variant is stored for quick reads. 
    """

    def __init__(self, db, name, xtype, root=None, default=None):
        if root is None:
            self.root = PosixPath('/')
        else:
            self.root = root.base_key()
        self.name = name
        self.xtype = xtype
        self.db = db
        self._base_key = self.root / self.name
        self._base_key_str = str(self._base_key)
        self.immut_type = xtype in {int, str, float}
        self.default = default

        self.has_value = False
        if self.exists():
            self.value = self.get_value()
            self.has_value = True
        else:
            self.value = None

    def set_value(self, value):
        # Optimization for immutable types: no need to write if same.
        if self.has_value and self.immut_type and value == self.value:
            return

        json_data = json.dumps(self.pre_proc(value))
        key = self._base_key_str
        self.db[key] = json_data

        self.has_value = True
        self.value = value

    def get_value(self):
        # Optimization for immutable types: since they cannot change
        # we can cache and return them.
        if self.has_value and self.immut_type:
            return self.value
        
        # If there is no stored value return default
        if not self.exists() and self.default is not None:
            return self.default
        
        val = json.loads(self.db[self._base_key_str])
        self.value = self.post_proc(val)
        self.has_value = True
        return self.value
    
    def exists(self):
        return self.has_value or self._base_key_str in self.db

    def base_key(self):
        return self._base_key
