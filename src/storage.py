# The main storage interface

import dbm
import json
from pathlib import PosixPath

from utils import JSONFlag, JSONSerializable

class Storable:
    """ Base class for objects that can be stored """

    def __init__(self, xtype):
        """ Specify the type (or base type) of the objects to be stored """
        self.xtype = xtype

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

    def make_value(self, name, xtype, root = None):
        ''' A new value-like storable'''
        return StorableValue(self.db, name, xtype, root)

    def make_list(self, name, xtype, root):
        ''' A new list-like storable'''
        return StorableList(self.db, name, xtype, root)

    def make_dict(self, name, xtype, root):
        ''' A new map-like storable'''
        return StorableDict(self.db, name, xtype, root)

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
        self.length = StorableValue(db, '__LEN', int, root=meta)
        if not self.length.exists():
            self.length.set_value(0)
        
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

        self.length = StorableValue(db, '__LEN', int, root=self)
        if not self.length.exists():
            self.length.set_value(0)


    def base_key(self):
        return self.root / self.name
    
    def __getitem__(self, key):
        if type(key) is not int:
            raise KeyError('Key must be an int.')
        xlen = len(self)
        if not 0<= key < xlen:
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

    def __init__(self, db, name, xtype, root=None):
        if root is None:
            self.root = PosixPath('/')
        else:
            self.root = root.base_key()
        self.name = name
        self.xtype = xtype
        self.db = db

        self.has_value = False
        if self.exists():
            self.has_value = True
            self.value = self.get_value()
        else:
            self.value = None

        # self.db = dbm.open(str(fname), 'c')

    def set_value(self, value):
        if self.has_value and value == self.value:
            return

        json_data = json.dumps(self.pre_proc(value))
        key = str(self.base_key())
        self.db[key] = json_data

        self.has_value = True
        self.value = value

    def get_value(self):
        if self.has_value:
            return self.value
        val = json.loads(self.db[str(self.base_key())])
        return self.post_proc(val)
    
    def exists(self):
        return self.has_value or str(self.base_key()) in self.db

    def base_key(self):
        return self.root / self.name
