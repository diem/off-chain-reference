# The main storage interface

import dbm
import json
from pathlib import PosixPath

class Storable:

    def get_name(self):
        pass

    def get_root(self):
        pass

    def persist(self):
        pass

    def dirty(self):
        pass

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
        db_key = str(self.base_key() / str(key))
        return self.xtype(json.loads(self.db[db_key]))

    def __setitem__(self, key, value):
        db_key = str(self.base_key() / str(key))
        if db_key not in self.db:
            xlen = self.length.get_value()
            self.length.set_value(xlen+1)
        self.db[db_key] = json.dumps(value)

    def __len__(self):
        xlen =  self.length.get_value()
        return xlen

    def __delitem__(self, key):
        db_key = str(self.base_key() / str(key))
        if db_key in self.db:
            xlen = self.length.get_value()
            self.length.set_value(xlen-1)
            del self.db[db_key]
    
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
        return self.xtype(json.loads(self.db[db_key]))

    def __setitem__(self, key, value):
        if type(key) is not int:
            raise KeyError('Key must be an int.')
        xlen = len(self)
        if not 0<= key < xlen:
            raise KeyError('Key does not exist')
        db_key = str(self.base_key() / str(key))
        self.db[db_key] = json.dumps(value)

    def __len__(self):
        xlen =  self.length.get_value()
        assert type(xlen) is int
        return xlen
    
    def __iadd__(self, other):
        for item in other:
            assert type(item) is self.xtype
            xlen = self.length.get_value()
            self.length.set_value(xlen+1)
            self[xlen] = item
            return self

    def __iter__(self):
        for key in range(len(self)):
            yield self[key]


class StorableValue(Storable):

    def __init__(self, db, name, xtype, root=None):
        if root is None:
            self.root = PosixPath('/')
        else:
            self.root = root.base_key()
        self.name = name
        self.type = xtype
        self.db = db
        self.dirty = False

        # self.db = dbm.open(str(fname), 'c')

    def set_value(self, value):
        self.db[str(self.base_key())] = json.dumps(value)
        self.dirty = True

    def get_value(self):
        val = json.loads(self.db[str(self.base_key())])
        return self.type(val)
    
    def exists(self):
        return str(self.base_key()) in self.db

    def base_key(self):
        return self.root / self.name
    
    def get_name(self):
        return self.name

    def get_root(self):
        return self.root

    def persist(self):
        if self.dirty:
            # self.db.sync()
            self.dirty = False

    def get_dirty(self):
        return self.dirty
