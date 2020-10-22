# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

# The main storage interface.
from hashlib import sha256
import json
from threading import RLock

from .utils import JSONFlag, JSONSerializable, get_unique_string

def make_key(ns, key):
    return ns + "@@" + key


class BasicStore:
    def __init__(self):
        self.data = {}

    def get(self, ns, key):
        return self.data[make_key(ns, key)]

    def try_get(self, ns, key):
        """
        Returns value if key exists in storage, otherwise returns None
        """
        try:
            return self.data[make_key(ns, key)]
        except KeyError:
            return None

    def put(self, ns, key, val):
        self.data[make_key(ns, key)] = val

    def delete(self, ns, key):
        del self.data[make_key(ns, key)]

    def isin(self, ns, key):
        return make_key(ns, key) in self.data

    def getkeys(self, ns):
        keys = []
        for k, v in self.data.items():
            if k.startswith(ns+"@@"):
                keys.append(k[len(ns+"@@"):])
        return keys

    def count(self, ns):
        return len(self.getkeys(ns))


def key_join(strs):
    ''' Joins a sequence of strings to form a storage key. '''
    # Ensure this is parseable and one-to-one to avoid collisions.
    return '||'.join([f'[{len(s)}:{s}]' for s in strs])


class Storable:
    """Base class for objects that can be stored.

    Args:
        xtype (*): the type (or base type) of the objects to be stored.
    """

    def __init__(self, xtype):
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
            the type constructor.
        """
        if issubclass(self.xtype, JSONSerializable):
            return self.xtype.parse(val, JSONFlag.STORE)
        else:
            return self.xtype(val)


class StorableFactory:
    ''' This class maintains an overview of the full storage subsystem,
    and creates specific classes for values, lists and dictionary like
    types that can be stored persistently. It also provides a context
    manager to provide atomic, all-or-nothing crash resistent
    transactions.

    Initialize the ``StorableFactory`` with a persistent key-value
    store ``db``. In case the db already contains data the initializer
    runs the crash recovery procedure to cleanly re-open it.
    '''

    def __init__(self, db):
        self.rlock = RLock()
        self.db = db
        self.current_transaction = None
        self.levels = 0

        # # Transaction cache: keep data in memory
        # # until the transaction completes.
        # self.cache = {}
        # self.del_cache = set()

        # # Check and fix the database, if this is needed
        # self.crash_recovery()

    def make_dir(self, name, root=None):
        ''' Makes a new value-like storable.

            Parameters:
                * name : a string representing the name of the object.
                * xtype : the type of the object. It may be a simple type
                  or a subclass of JSONSerializable.
                * root : another storable object that acts as a logical
                  folder to this one.
                * default : the default value of the storable.

        '''
        v = StorableValue(self.db, name, root)
        v.factory = self
        return v

    def make_dict(self, name, xtype, root):
        ''' A new map-like storable object.

            Parameters:
                * name : a string representing the name of the object.
                * xtype : the type of the object stored in the map.
                  It may be a simple type or a subclass of
                  JSONSerializable. The keys are always strings.
                * root : another storable object that acts as a logical
                  folder to this one.

        '''
        v = StorableDict(self.db, name, xtype, root)
        v.factory = self
        return v

    # def persist_cache(self):
    #     ''' Safely persist the cache once the transaction is over.
    #         This is called internally when the context manager exists.
    #     '''

    #     from itertools import chain

    #     # Create a backup of all affected values.
    #     old_entries = {}
    #     non_existent_entries = []
    #     for key in chain(self.cache.keys(), self.del_cache):
    #         if key in self.db:
    #             old_entries[key] = self.db[key]
    #         else:
    #             non_existent_entries += [key]

    #     if len(old_entries) == 0 and len(non_existent_entries) == 0:
    #         return

    #     backup_data = json.dumps([old_entries, non_existent_entries])
    #     self.db['__backup_recovery'] = backup_data
    #     # TODO: call to flush to disk

    #     # Write new values to the database
    #     for item in self.cache:
    #         self.db[item] = self.cache[item]
    #     for item in self.del_cache:
    #         if item in self.db:
    #             del self.db[item]

    #     # Upon completion of write, clean up
    #     del self.db['__backup_recovery']
    #     self.cache = {}
    #     self.del_cache = set()

    # def crash_recovery(self):
    #     ''' Detects whether a database contains potentially inconsistent state
    #         and recovers a good state of the database. '''

    #     if not self.db.isin('__backup_recovery'):
    #         return

    #     # Recover the old good state.
    #     backup_data = json.loads(self.db['__backup_recovery'])
    #     old_entries = backup_data[0]
    #     non_existent_entries = backup_data[1]

    #     # Note, this may be executed many times in case of crash during
    #     # crash recovery.
    #     for item in old_entries:
    #         self.db[item] = old_entries[item]
    #     for item in non_existent_entries:
    #         if item in self.db:
    #             del self.db[item]

    #     # TODO: Ensure the writes are complete?
    #     del self.db['__backup_recovery']

    # Define the interfaces as a context manager

    def atomic_writes(self):
        ''' Returns a context manager that ensures
            all writes in its body on the objects created by this
            StorableFactory are atomic.

            Attempting to write to the objects created by this
            StorableFactory outside the context manager will
            throw an exception. The context manager is re-entrant
            and commits to disk occur when the outmost context
            manager (with) exits.'''
        return self

    def __enter__(self):
        if self.levels == 0:
            self.current_transaction = get_unique_string()

        self.levels += 1

    def __exit__(self, type, value, traceback):
        self.levels -= 1
        if self.levels == 0:
            self.current_transaction = None
            # self.persist_cache()


class StorableDict(Storable):
    """ Implements a persistent dictionary like type. Entries are stored
        by key directly, and a separate doubly linked list structure is
        stored to enable traversal of keys and values.

        Supports:
            * __getitem__(self, key)
            * __setitem__(self, key, value)
            * keys(self)
            * values(self)
            * __len__(self)
            * __contains__(self, item)
            * __delitem__(self, key)

        Keys should be strings or any object with a unique str representation.
        """

    def __init__(self, db, name, xtype, root=None):

        if root is None:
            self.root = ['']
        else:
            self.root = root.base_key()
        self.name = name
        self.db = db
        self.xtype = xtype

        # self.ns = sha256(key_join(self.base_key()).encode('utf8')).digest().hex()
        self.ns = key_join(self.base_key())

    def base_key(self):
        return self.root + [self.name]

    def try_get(self, key):
        """
        Returns value if key exists in storage, otherwise returns None
        """
        val =  self.db.try_get(self.ns, key)
        if val is None:
            return None
        return self.post_proc(json.loads(val))

    def __getitem__(self, key):
        return self.post_proc(json.loads(self.db.get(self.ns, key)))

    def __setitem__(self, key, value):
        data = json.dumps(self.pre_proc(value))
        self.db.put(self.ns, key, data)

    def keys(self):
        ''' An iterator over the keys of the dictionary. '''
        return self.db.getkeys(self.ns)

    def __len__(self):
        return self.db.count(self.ns)

    def is_empty(self):
        ''' Returns True if dict is empty and False if it contains some elements.'''
        return self.db.count(self.ns) == 0

    def __delitem__(self, key):
        self.db.delete(self.ns, key)

    def __contains__(self, key):
        return self.db.isin(self.ns, key)


class StorableValue():
    """ Implements a cached persistent value. The value is stored to storage
        but a cached variant is stored for quick reads.
    """

    def __init__(self, db, name, root=None):
        if root is None:
            self.root = ['']
        else:
            self.root = root.base_key()

        self.name = name
        self.db = db
        # self.ns = sha256(key_join(self.base_key()).encode('utf8')).digest().hex()
        self.ns = key_join(self.base_key())

    def base_key(self):
        return self.root + [ self.name ]
