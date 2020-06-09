# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

# The main storage interface.

import json
from threading import RLock

from .utils import JSONFlag, JSONSerializable, get_unique_string


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

        # Transaction cache: keep data in memory
        # until the transaction completes.
        self.cache = {}
        self.del_cache = set()

        # Check and fix the database, if this is needed
        self.crash_recovery()

    def make_value(self, name, xtype, root=None, default=None):
        ''' Makes a new value-like storable.

            Parameters:
                * name : a string representing the name of the object.
                * xtype : the type of the object. It may be a simple type
                  or a subclass of JSONSerializable.
                * root : another storable object that acts as a logical
                  folder to this one.
                * default : the default value of the storable.

        '''
        assert default is None or type(default) == xtype
        v = StorableValue(self, name, xtype, root, default)
        v.factory = self
        return v

    def make_list(self, name, xtype, root):
        ''' Makes a new list-like storable. The type of the objects
            stored is xtype, or any subclass of JSONSerializable.

            Parameters:
                * name : a string representing the name of the object.
                * xtype : the type of the object stored in the list.
                  It may be a simple type or a subclass of
                  JSONSerializable.
                * root : another storable object that acts as a logical
                  folder to this one.
        '''
        v = StorableList(self, name, xtype, root)
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
            raise RuntimeError(
                'Writes must happen within a transaction context')
        self.cache[key] = value
        if key in self.del_cache:
            self.del_cache.remove(key)

    def __contains__(self, item):
        if item in self.del_cache:
            return False
        if item in self.cache:
            return True
        return item in self.db

    def __delitem__(self, key):
        if self.current_transaction is None:
            raise RuntimeError(
                'Writes must happen within a transaction context')
        if key in self.cache:
            del self.cache[key]
        self.del_cache.add(key)

    def persist_cache(self):
        ''' Safely persist the cache once the transaction is over.
            This is called internally when the context manager exists.
        '''

        from itertools import chain

        # Create a backup of all affected values.
        old_entries = {}
        non_existent_entries = []
        for key in chain(self.cache.keys(), self.del_cache):
            if key in self.db:
                old_entries[key] = self.db[key]
            else:
                non_existent_entries += [key]

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
        self.rlock.acquire()
        if self.levels == 0:
            self.current_transaction = get_unique_string()

        self.levels += 1

    def __exit__(self, type, value, traceback):
        try:
            self.levels -= 1
            if self.levels == 0:
                self.current_transaction = None
                self.persist_cache()
        finally:
            self.rlock.release()


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

        # We create a doubly linked list to support traveral with O(1) lookup
        # addition and creation.
        meta = StorableValue(db, '__META', str, root=self)
        self.first_key = StorableValue(
            db, '__FIRST_KEY', str,
            root=meta, default='_NONE')
        self.first_key.debug = True
        self.length = StorableValue(db, '__LEN', int, root=meta, default=0)

    if __debug__:
        def _check_invariant(self):
            if self.first_key.get_value() != '_NONE':
                first_value_key = self.first_key.get_value()
                # [prev_LL_key, next_LL_key, db_key, key]
                first_ll_entry = json.loads(self.db[first_value_key])
                assert first_ll_entry[0] is None

    def base_key(self):
        return self.root + [self.name]

    def __getitem__(self, key):
        db_key, db_key_LL = self.derive_keys(key)
        return self.post_proc(json.loads(self.db[db_key]))

    def _ll_cons(self, key):
        db_key, db_key_LL = self.derive_keys(key)
        assert db_key_LL not in self.db

        if self.first_key.get_value() != '_NONE':
            # All new entries to the front
            first_value_key = self.first_key.get_value()
            assert first_value_key is not None

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

        self.first_key.set_value(db_key_LL)
        self.db[db_key_LL] = json.dumps(ll_entry)

        if __debug__:
            self._check_invariant()

    def __setitem__(self, key, value):
        db_key, _ = self.derive_keys(key)
        data = json.dumps(self.pre_proc(value))

        # Ensure nothing fails after that
        if db_key not in self.db:
            xlen = self.length.get_value()
            self.length.set_value(xlen+1)

            # Add an entry to the linked list
            self._ll_cons(key)

        self.db[db_key] = data

        if __debug__:
            self._check_invariant()

    def keys(self):
        ''' An iterator over the keys of the dictionary. '''
        if __debug__:
            self._check_invariant()

        if not self.first_key.get_value() != '_NONE':
            return
        ll_value_key = self.first_key.get_value()
        while True:
            ll_entry = json.loads(self.db[ll_value_key])
            ll_value_key = ll_entry[1]
            yield ll_entry[3]
            if ll_value_key is None:
                break

    def values(self):
        ''' An iterator over the values of the dictionary. '''
        for k in self.keys():
            yield self[k]

    def __len__(self):
        xlen = self.length.get_value()
        return xlen

    def __delitem__(self, key):
        db_key, db_key_LL = self.derive_keys(key)
        if db_key in self.db:
            xlen = self.length.get_value()
            self.length.set_value(xlen-1)
            del self.db[db_key]

            # Now fix the LL structure
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
                    _, next_db_key_LL = self.derive_keys(next_key)
                    self.first_key.set_value(next_key)

            if next_key is None and prev_key is None:
                # The Linked List needs to become empty.
                self.first_key.set_value('_NONE')

            del self.db[db_key_LL]
        else:
            raise KeyError(key)

    def derive_keys(self, item):
        key = key_join(self.base_key() + [str(item)])
        key_LL = key_join(self.base_key() + ['LL', str(item)])
        return key, key_LL

    def __contains__(self, item):
        db_key = key_join(self.base_key() + [str(item)])
        return db_key in self.db


class StorableList(Storable):
    ''' A list-like object that can be stored.

    Supports:
        * __getitem__(self, key)
        * __setitem__(self, key, value)
        * __len__(self)
        * __iadd__(self, other)

    Keys are always integers.
    '''

    def __init__(self, db, name, xtype, root=None):
        if root is None:
            self.root = ['']
        else:
            self.root = root.base_key()
        self.name = name
        self.db = db
        self.xtype = xtype

        self.length = StorableValue(db, '__LEN', int, root=self, default=0)
        if not self.length.exists():
            self.length.set_value(0)

    def base_key(self):
        return self.root + [self.name]

    def __getitem__(self, key):
        if type(key) is not int:
            raise KeyError('Key must be an int.')
        xlen = len(self)
        if not 0 <= key < xlen:
            raise KeyError('Key does not exist')

        db_key = key_join(self.base_key() + [str(key)])
        return self.post_proc(json.loads(self.db[db_key]))

    def __setitem__(self, key, value):
        if type(key) is not int:
            raise KeyError('Key must be an int.')
        xlen = len(self)
        if not 0 <= key < xlen:
            raise KeyError('Key does not exist')
        db_key = key_join(self.base_key() + [str(key)])
        self.db[db_key] = json.dumps(self.pre_proc(value))

    def __len__(self):
        xlen = self.length.get_value()
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
            self.root = ['']
        else:
            self.root = root.base_key()

        self.name = name
        self.xtype = xtype
        self.db = db
        self._base_key = self.root + [self.name]
        self._base_key_str = key_join(self._base_key)

        self.has_value = False

        if self.exists():
            self.value = self.get_value()
        else:
            self.value = None
            if default is not None:
                self.set_value(default)

    def set_value(self, value):
        ''' Sets the vale for this instance.
            Value must be of the right type namely ``xtype``.
        '''
        json_data = json.dumps(self.pre_proc(value))
        key = self._base_key_str
        self.db[key] = json_data
        self.has_value = True
        self.value = value

    def get_value(self):
        ''' Get the value for this object. '''
        key = self._base_key_str
        encoded_value = self.db[key]
        val = json.loads(encoded_value)
        self.value = self.post_proc(val)
        self.has_value = True
        return self.value

    def exists(self):
        ''' Tests if this value exist in storage. '''
        return self.has_value or self._base_key_str in self.db

    def base_key(self):
        return self._base_key
