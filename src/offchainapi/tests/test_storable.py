# Copyright (c) Facebook, Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Tests for the storage framework
from ..storage import StorableDict, StorableList, StorableValue, StorableFactory
from ..payment_logic import PaymentCommand
from ..protocol_messages import make_success_response, CommandRequestObject, \
    make_command_error

import pytest

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
    assert list(D.keys()) == []

    D['x'] = 10
    D['y'] = 20
    D['z'] = 30
    D['a'] = 40
    D['b'] = 50

    assert len(list(D.keys())) == 5
    assert set(D.keys()) == {'x', 'y', 'z', 'a', 'b'}

    D = StorableDict(db, 'anna', int)
    D['x'] = 10
    D['y'] = 20
    D['z'] = 30
    D['a'] = 40
    D['b'] = 50

    del D['x']
    assert set(D.keys()) == {'y', 'z', 'a', 'b'}
    del D['b']
    assert set(D.keys()) == {'y', 'z', 'a'}

    assert set(D.values()) == {20, 30, 40}

def test_dict_dict_del_to_empty():
    db = {}
    D = StorableDict(db, 'to_del', bool)
    D['x'] = True
    del D['x']
    D['y'] = True
    del D['y']
    assert len(D) == 0


def test_dict_index():
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
    lst += [1]
    assert len(lst) == 1
    assert lst[0] == 1
    lst += [2]
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
    lst += [1]
    assert len(lst) == 1
    assert lst[0] == 1
    lst += [2]
    assert len(lst) == 2
    lst[0] = 10
    assert lst[0] == 10
    lst2 = StorableList(db, 'jacklist', int)
    assert len(lst2) == 2
    assert lst2[0] == 10

    assert list(lst2) == [10, 2]


def test_value(db):
    # Test default
    val0 = StorableValue(db, 'counter_zero', int, default=0)
    assert val0.get_value() == 0
    assert val0.exists()
    val0.set_value(10)
    assert val0.get_value() == 10

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


def test_value_payment(db, payment):
    val = StorableValue(db, 'payment', payment.__class__)
    assert val.exists() is False
    val.set_value(payment)
    assert val.exists() is True
    pay2 = val.get_value()
    assert payment == pay2

    lst = StorableList(db, 'jacklist', payment.__class__)
    lst += [payment]
    assert lst[0] == pay2

    D = StorableDict(db, 'mary', payment.__class__)
    D[pay2.version] = pay2
    assert D[pay2.version] == payment


def test_value_command(db, payment):

    cmd = PaymentCommand(payment)

    val = StorableValue(db, 'command', PaymentCommand)
    val.set_value(cmd)
    assert val.get_value() == cmd

    cmd.creates_versions = ['xxxxxxxx']
    assert val.get_value() != cmd
    val.set_value(cmd)
    assert val.get_value() == cmd


def test_value_request(db, payment):
    cmd = CommandRequestObject(PaymentCommand(payment))
    cmd.cid = '10'

    val = StorableValue(db, 'command', CommandRequestObject)
    val.set_value(cmd)
    assert val.get_value() == cmd

    cmd.response = make_success_response(cmd)
    assert cmd.response is not None
    assert val.get_value() != cmd
    assert val.get_value().response is None

    val.set_value(cmd)
    assert val.get_value() == cmd

    cmd.response = make_command_error(cmd, code='Something went wrong')
    assert val.get_value() != cmd
    val.set_value(cmd)
    assert val.get_value() == cmd


def test_recovery():

    class CrashNow(Exception):
        pass

    # Define an underlying storage that crashes
    class CrashDict(dict):

        def __init__(self, *args, **kwargs):
            dict.__init__(self, *args, **kwargs)
            self.crash = None

        def __setitem__(self, key, value):
            if self.crash is not None:
                self.crash -= 1
                if self.crash == 0:
                    self.crash = None
                    raise CrashNow()
            dict.__setitem__(self, key, value)

    # Test the crashing dict itself.
    cd = CrashDict()
    cd.crash = 2

    cd['A'] = 1
    with pytest.raises(CrashNow):
        cd['B'] = 2

    cd2 = CrashDict()
    assert cd2.crash is None
    sf = StorableFactory(cd2)

    with sf as tx_id:
        sf["1"] = 1
        assert "1" in sf.cache
        sf["2"] = 2
        assert "2" in sf.cache
        sf["4"] = 4

    assert sf.cache == {}
    assert cd2 == {"1": 1, "2": 2, '4': 4}
    sf.__enter__()
    sf["1"] = 10
    assert "1" in sf.cache
    sf["3"] = 30
    assert "3" in sf.cache
    del sf['4']

    cd2.crash = 3
    with pytest.raises(CrashNow):
        sf.persist_cache()
    assert '__backup_recovery' in cd2

    sf2 = StorableFactory(cd2)
    assert '__backup_recovery' not in cd2
    assert cd2 == {"1":1, "2":2, '4':4}

def test_dict_trans():
    d = {}
    store = StorableFactory(d)

    with store as _:
        eg = store.make_dict('eg', int, None)

    with store as _:
        eg['x'] = 10
        eg['x'] = 20
        eg['y'] = 20
        eg['x'] = 30

    with store as _:
        x = eg['x']
        l = len(eg)
        eg['z'] = 20

    assert len(eg) == 3
    assert set(eg.keys()) == set(['x', 'y', 'z'])
