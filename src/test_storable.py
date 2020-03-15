# Tests for the storage framework

from storage import *
from pathlib import PosixPath

import pytest

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / 'db.dat'
    xdb = dbm.open(str(db_path), 'c')
    return xdb

def test_dict(db):
    D = StorableDict(db, 'mary', int)
    D['x'] = 10
    assert D['x'] == 10 
    assert len(D) == 1
    D['hello'] = 2
    assert len(D) == 2
    del D['x']
    assert D['hello'] == 2 
    assert len(D) == 1
    assert 'hello' in D
    assert 'x' not in D

def test_dict_dict():
    db = {}
    D = StorableDict(db, 'mary', int)
    D['x'] = 10
    assert D['x'] == 10 
    assert len(D) == 1
    D['hello'] = 2
    assert len(D) == 2
    del D['x']
    assert D['hello'] == 2 
    assert len(D) == 1
    assert 'hello' in D
    assert 'x' not in D




def test_list(db):
    lst = StorableList(db, 'jacklist', int)
    lst += [ 1 ]
    assert len(lst) == 1
    assert lst[0] == 1
    lst += [ 2 ]
    assert len(lst) == 2
    lst[0] = 10
    assert lst[0] == 10
    lst2 = StorableList(db, 'jacklist', int)
    assert len(lst2) == 2
    assert lst2[0] == 10

    assert list(lst2) == [10, 2]


def test_list_dict():
    db = {}
    lst = StorableList(db, 'jacklist', int)
    lst += [ 1 ]
    assert len(lst) == 1
    assert lst[0] == 1
    lst += [ 2 ]
    assert len(lst) == 2
    lst[0] = 10
    assert lst[0] == 10
    lst2 = StorableList(db, 'jacklist', int)
    assert len(lst2) == 2
    assert lst2[0] == 10

    assert list(lst2) == [10, 2]


def test_value(db):
    val = StorableValue(db, 'counter', int)
    assert val.exists() is False
    val.set_value(10)
    assert val.exists() is True

    val2 = StorableValue(db, 'counter', int)
    assert val2.exists() is True
    assert val2.get_value() == 10

def test_value_dict():
    db = {}
    val = StorableValue(db, 'counter', int)
    assert val.exists() is False
    val.set_value(10)
    assert val.exists() is True

    val2 = StorableValue(db, 'counter', int)
    assert val2.exists() is True
    assert val2.get_value() == 10


def test_hierarchy(db):
    val = StorableValue(db, 'counter', int)
    val.set_value(10)

    val2 = StorableValue(db, 'counter', int, root=val)
    assert val2.exists() is False
    val2.set_value(20)
    assert val.get_value() == 10
    assert val2.get_value() == 20
