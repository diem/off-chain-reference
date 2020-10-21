# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

# Tests for the storage framework
from ..storage import StorableDict, StorableValue, StorableFactory, BasicStore
from ..payment_logic import PaymentCommand
from ..protocol_messages import make_success_response, CommandRequestObject, \
    make_command_error
from ..errors import OffChainErrorCode

import pytest

def test_dict_basic(db):

    D = StorableDict(db, 'mary', int)
    assert D.is_empty()
    D['x'] = 10
    assert not D.is_empty()
    assert D['x'] == 10
    assert len(D) == 1
    D['hello'] = 2
    assert len(D) == 2
    del D['x']
    assert not D.is_empty()
    assert len(D) == 1
    assert D['hello'] == 2
    assert 'x' not in D
    assert 'hello' in D


def test_dict_dict(db):
    D = StorableDict(db, 'mary', int)
    assert list(D.keys()) == []

    D['x'] = 10
    D['y'] = 20
    D['z'] = 30
    D['a'] = 40
    D['b'] = 50

    assert len(list(D.keys())) == 5
    assert len(D) == 5
    assert set(D.keys()) == {'x', 'y', 'z', 'a', 'b'}

    D = StorableDict(db, 'anna', int)
    D['x'] = 10
    D['y'] = 20
    D['z'] = 30
    D['a'] = 40
    D['b'] = 50

    del D['x']
    assert len(D) == 4
    assert set(D.keys()) == {'y', 'z', 'a', 'b'}
    del D['b']
    assert len(D) == 3
    assert set(D.keys()) == {'y', 'z', 'a'}

def test_dict_dict_del_to_empty(db):
    D = StorableDict(db, 'to_del', bool)
    D['x'] = True
    del D['x']
    D['y'] = True
    del D['y']
    assert len(D) == 0


def test_dict_index(db):
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


def test_hierarchy(db):
    val = StorableValue(db, 'counter', None)

    val2 = StorableDict(db, 'counter', int, root=val)
    val2['xx'] = 20
    assert val2['xx'] == 20


def test_complicated_objects(db, payment):
    payment_dict = StorableDict(db, 'payment', payment.__class__)
    payment_dict['foo'] = payment
    pay2 = payment_dict['foo']
    assert payment == pay2

    cmd = PaymentCommand(payment)
    cmd_dict = StorableDict(db, 'command', PaymentCommand)
    cmd_dict['foo'] = cmd
    assert cmd_dict['foo'] == cmd

    cmd.writes_version_map = [('xxxxxxxx', 'xxxxxxxx')]
    assert cmd_dict['foo'] != cmd
    cmd_dict['foo'] = cmd
    assert cmd_dict['foo'] == cmd

    request = CommandRequestObject(cmd)
    request.cid = '10'

    request_dict = StorableDict(db, 'command', CommandRequestObject)
    request_dict['foo'] = request
    assert request_dict['foo'] == request

    request.response = make_success_response(request)
    assert request.response is not None
    assert request_dict['foo'] != request
    assert request_dict['foo'].response is None


def test_storable_factory(db):
    store = StorableFactory(db)

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
