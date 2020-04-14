from ..payment_logic import *
from ..payment import *
from ..protocol_messages import *
from ..protocol import *
from ..utils import *
from ..libra_address import *
from ..sample_command import *

from unittest.mock import MagicMock
from mock import AsyncMock
import pytest
import asyncio


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment


def test_payment_command_serialization_net(basic_payment):
    cmd = PaymentCommand(basic_payment)
    data = cmd.get_json_data_dict(JSONFlag.NET)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.NET)
    assert cmd == cmd2


def test_payment_command_serialization_parse(basic_payment):
    cmd = PaymentCommand(basic_payment)
    data = cmd.get_json_data_dict(JSONFlag.NET)
    obj = JSONSerializable.parse(data, JSONFlag.NET)
    assert obj == cmd

    cmd_s = SampleCommand('Hello', deps=['World'])
    data2 = cmd_s.get_json_data_dict(JSONFlag.NET)
    cmd_s2 = JSONSerializable.parse(data2, JSONFlag.NET)
    assert cmd_s == cmd_s2


def test_payment_command_serialization_store(basic_payment):
    cmd = PaymentCommand(basic_payment)
    data = cmd.get_json_data_dict(JSONFlag.STORE)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.STORE)
    assert cmd == cmd2


def test_payment_end_to_end_serialization(basic_payment):
    # Define a full request/reply with a Payment and test serialization
    cmd = PaymentCommand(basic_payment)
    request = CommandRequestObject(cmd)
    request.seq = 10
    request.response = make_success_response(request)
    data = request.get_json_data_dict(JSONFlag.STORE)
    request2 = CommandRequestObject.from_json_data_dict(data, JSONFlag.STORE)
    assert request == request2


def test_payment_command_multiple_dependencies_fail(basic_payment):
    new_payment = basic_payment.new_version('v1')
    # Error: 2 dependencies
    new_payment.previous_versions += ['v2']
    cmd = PaymentCommand(new_payment)
    with pytest.raises(PaymentLogicError):
        cmd.get_object(new_payment.get_version(), 
            { basic_payment.get_version():basic_payment })


def test_payment_command_create_fail(basic_payment):
    cmd = PaymentCommand(basic_payment)
    # Error: two new versions
    cmd.creates_versions += [ basic_payment.get_version() ]
    with pytest.raises(PaymentLogicError):
        cmd.get_object(basic_payment.get_version(), {})


def test_payment_command_missing_dependency_fail(basic_payment):
    new_payment = basic_payment.new_version('v1')
    cmd = PaymentCommand(new_payment)
    with pytest.raises(PaymentLogicError):
        cmd.get_object(new_payment.get_version(), {})


# ----- check_new_payment -----

@pytest.fixture
def payment_processor_context():
    bcm = MagicMock(spec=BusinessContext)
    store = StorableFactory({})
    proc = PaymentProcessor(bcm, store)
    return (bcm, proc)

def test_payment_create_from_recipient(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True] * 4
    pp.check_new_payment(basic_payment)
    

def test_payment_create_from_sender_sig_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False] * 4
    basic_payment.add_recipient_signature('BAD SINGNATURE')
    bcm.validate_recipient_signature.side_effect = [BusinessValidationFailure('Sig fails')]

    with pytest.raises(BusinessValidationFailure):
        pp.check_new_payment(basic_payment)


def test_payment_create_from_sender(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False] * 4
    pp.check_new_payment(basic_payment)



def test_payment_create_from_sender_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True]
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        pp.check_new_payment(basic_payment)

def test_payment_create_from_receiver_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False] * 4

    basic_payment.data['sender'].update({'status': Status.ready_for_settlement})
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        pp.check_new_payment(basic_payment)


def test_payment_create_from_receiver_bad_state_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False]

    basic_payment.data['receiver'].update({'status': Status.needs_recipient_signature})
    with pytest.raises(PaymentLogicError):
        pp.check_new_payment(basic_payment)


# ----- check_new_update -----


def test_payment_update_from_sender(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False] * 4
    diff = {}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_sender_modify_receiver_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True]
    diff = {'receiver': {'status': "settled"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.data['receiver'].data['status'] != basic_payment.data['receiver'].data['status']
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_receiver_invalid_state_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False]
    diff = {'receiver': {'status': "needs_recipient_signature"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_receiver_invalid_transition_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False]
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    diff = {'receiver': {'status': "needs_kyc_data"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_receiver_unilateral_abort_fail(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [False]
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    diff = {'receiver': {'status': "abort"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


# ----- payment_process -----
@pytest.fixture(params=[
    ('AAAA', 'BBBB', 'AAAA', True),
    ('BBBB', 'AAAA', 'AAAA', True),
    ('CCCC', 'AAAA', 'AAAA', False),
    ('BBBB', 'CCCC', 'AAAA', False),
    ('DDDD', 'CCCC', 'AAAA', False),
    ('AAAA', 'BBBB', 'BBBB', True),
    ('BBBB', 'AAAA', 'DDDD', False),
])
def states(request):
    return request.param

def test_payment_processor_check(states, basic_payment, payment_processor_context):
    src_addr, dst_addr, origin_addr, res = states
    bcm, pp = payment_processor_context
    vasp = MagicMock()
    channel = MagicMock()
    channel.other.as_str.side_effect = [ src_addr ] 
    channel.myself.as_str.side_effect = [ dst_addr ] 
    executor = MagicMock()
    command = PaymentCommand(basic_payment)
    origin = MagicMock(spec=LibraAddress)
    origin.as_str.return_value = origin_addr
    command.set_origin(origin)

    if res:
        pp.check_command(vasp, channel, executor, command)
    else:
        with pytest.raises(PaymentLogicError):
            pp.check_command(vasp, channel, executor, command)

def async_return(result):
    f = asyncio.Future()
    f.set_result(result)
    return f

def test_payment_process_receiver_new_payment(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.needs_kyc_data]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [async_return(False)]

    assert basic_payment.data['receiver'].data['status'] == Status.none
    new_payment = pp.payment_process(basic_payment)

    assert new_payment.data['receiver'].data['status'] == Status.needs_kyc_data

    new_payment.data['receiver'].data['status'] == Status.ready_for_settlement
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [async_return(True)]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [False]

    store = StorableFactory({})
    pp = PaymentProcessor(bcm, store)
    new_payment2 = pp.payment_process(new_payment)
    assert new_payment2.data['receiver'].data['status'] == Status.ready_for_settlement

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [async_return(True)]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]

    store = StorableFactory({})
    pp = PaymentProcessor(bcm, store)
    new_payment3 = pp.payment_process(new_payment2)
    assert new_payment3.data['receiver'].data['status'] == Status.settled


def test_payment_process_abort(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessForceAbort]

    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['status'] == Status.abort


def test_payment_process_abort_from_sender(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True]
    bcm.ready_for_settlement.side_effect = [async_return(False)]
    basic_payment.data['sender'].data['status'] = Status.abort
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['status'] == Status.abort


def test_payment_process_get_stable_id(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [ set([ Status.needs_stable_id ]) ]
    bcm.get_stable_id.side_effect = ['stable_id']
    bcm.ready_for_settlement.side_effect = [async_return(False)]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['stable_id'] == 'stable_id'


def test_payment_process_get_extended_kyc(basic_payment, payment_processor_context):
    bcm, pp = payment_processor_context
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [ set([Status.needs_kyc_data]) ]
    kyc_data = KYCData('{"payment_reference_id": "123", "type": "A"}')
    bcm.get_extended_kyc.side_effect = [
        (kyc_data, 'sig', 'cert')
    ]
    bcm.ready_for_settlement.side_effect = [async_return(True)]
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['kyc_data'] == kyc_data
    assert new_payment.data['receiver'].data['kyc_signature'] == 'sig'
    assert new_payment.data['receiver'].data['kyc_certificate'] == 'cert'
