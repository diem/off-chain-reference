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

from payment import *

@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', 'none', [])
    receiver = PaymentActor('BBBB', 'bbbb', 'none', [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')

    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

def test_value_payment(db, basic_payment):
    val = StorableValue(db, 'payment', basic_payment.__class__)
    assert val.exists() is False
    val.set_value(basic_payment)
    assert val.exists() is True
    pay2 = val.get_value()
    assert basic_payment == pay2

    lst = StorableList(db, 'jacklist', basic_payment.__class__)
    lst += [ basic_payment ]
    assert lst[0] == pay2

    D = StorableDict(db, 'mary', basic_payment.__class__)
    D[pay2.version] = pay2
    assert D[pay2.version] == basic_payment

def test_value_command(db, basic_payment):
    from payment_logic import PaymentCommand
    from protocol_messages import make_success_response, CommandRequestObject, make_command_error

    cmd = PaymentCommand(basic_payment)
 
    val = StorableValue(db, 'command', PaymentCommand)
    val.set_value(cmd)
    assert val.get_value() == cmd

    cmd.creates = [ 'xxxxxxxx' ]
    assert val.get_value() != cmd
    val.set_value(cmd)
    assert val.get_value() == cmd


def test_value_request(db, basic_payment):
    from payment_logic import PaymentCommand
    from protocol_messages import make_success_response, CommandRequestObject, make_command_error
    CommandRequestObject.register_command_type(PaymentCommand)
    cmd = CommandRequestObject(PaymentCommand(basic_payment))
    cmd.seq = 10
 
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
