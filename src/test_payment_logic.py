from payment_logic import *
from payment import *
from protocol_messages import *
from protocol import *
from business import BusinessAsyncInterupt
from utils import *
from libra_address import *
from sample_command import *

from unittest.mock import MagicMock
import pytest


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
def ppctx():
    bcm = MagicMock(spec=BusinessContext)
    store = StorableFactory({})
    proc = PaymentProcessor(bcm, store)
    return (bcm, proc)

def test_payment_create_from_recipient(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True] * 4
    pp.check_new_payment(basic_payment)
    

def test_payment_create_from_sender_sig_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False] * 4
    basic_payment.add_recipient_signature('BAD SINGNATURE')
    bcm.validate_recipient_signature.side_effect = [BusinessValidationFailure('Sig fails')]

    with pytest.raises(BusinessValidationFailure):
        pp.check_new_payment(basic_payment)


def test_payment_create_from_sender(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False] * 4
    pp.check_new_payment(basic_payment)


def test_payment_create_from_sender_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True]

    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        pp.check_new_payment(basic_payment)

def test_payment_create_from_receiver_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False] * 4

    basic_payment.data['sender'].update({'status': Status.ready_for_settlement})
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        pp.check_new_payment(basic_payment)


def test_payment_create_from_receiver_bad_state_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False]

    basic_payment.data['receiver'].update({'status': Status.needs_recipient_signature})
    with pytest.raises(PaymentLogicError):
        pp.check_new_payment(basic_payment)


# ----- check_new_update -----


def test_payment_update_from_sender(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False] * 4
    diff = {}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_sender_modify_receiver_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True]
    diff = {'receiver': {'status': "settled"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.data['receiver'].data['status'] != basic_payment.data['receiver'].data['status']
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_receiver_invalid_state_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False]
    diff = {'receiver': {'status': "needs_recipient_signature"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_receiver_invalid_transition_fail(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [False]
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    diff = {'receiver': {'status': "needs_kyc_data"}}
    new_obj = basic_payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        pp.check_new_update(basic_payment, new_obj)


def test_payment_update_from_receiver_unilateral_abort_fail(basic_payment, ppctx):
    bcm, pp = ppctx
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

def test_payment_processor_check(states, basic_payment, ppctx):
    src_addr, dst_addr, origin_addr, res = states
    bcm, pp = ppctx
    vasp = MagicMock()
    channel = MagicMock()
    channel.other.plain.side_effect = [ src_addr ] 
    channel.myself.plain.side_effect = [ dst_addr ] 
    executor = MagicMock()
    command = PaymentCommand(basic_payment)
    origin = MagicMock(spec=LibraAddress)
    origin.plain.return_value = origin_addr
    command.set_origin(origin)

    if res:
        pp.check_command(vasp, channel, executor, command)
    else:
        with pytest.raises(PaymentLogicError):
            pp.check_command(vasp, channel, executor, command)

def test_payment_process_receiver_new_payment(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.needs_kyc_data]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [False]

    assert basic_payment.data['receiver'].data['status'] == Status.none
    new_payment = pp.payment_process(basic_payment)

    assert new_payment.data['receiver'].data['status'] == Status.needs_kyc_data

    new_payment.data['receiver'].data['status'] == Status.ready_for_settlement
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [True]
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
    bcm.ready_for_settlement.side_effect = [True]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]

    store = StorableFactory({})
    pp = PaymentProcessor(bcm, store)
    new_payment3 = pp.payment_process(new_payment2)
    assert new_payment3.data['receiver'].data['status'] == Status.settled


def test_payment_process_interrupt(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessAsyncInterupt(1234)]

    with pp.storage_factory as _:
        new_payment = pp.payment_process(basic_payment)
    assert not new_payment.has_changed()
    assert new_payment.data['receiver'].data['status'] == Status.none


def test_payment_process_interrupt_resume(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True, True, True, True]
    bcm.check_account_existence.side_effect = [None, None]
    bcm.next_kyc_level_to_request.side_effect = [Status.ready_for_settlement]
    bcm.next_kyc_to_provide.side_effect = [BusinessAsyncInterupt(1234)]

    assert basic_payment.data['receiver'].data['status'] == Status.none
    with pp.storage_factory as _:
        new_payment = pp.payment_process(basic_payment)
    assert new_payment.has_changed()
    assert new_payment.data['receiver'].data['status'] == Status.ready_for_settlement

    bcm.next_kyc_to_provide.side_effect = [set()]
    bcm.ready_for_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]

    pp.notify_callback(1234)
    with pp.storage_factory as _:
        L = pp.payment_process_ready()
    assert len(L) == 1
    assert len(pp.callbacks) == 0
    assert len(pp.ready) == 0
    print(bcm.method_calls)
    L[0].data['receiver'].data['status'] == Status.settled


def test_payment_process_abort(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessForceAbort]

    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['status'] == Status.abort


def test_payment_process_abort_from_sender(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True]
    bcm.ready_for_settlement.side_effect = [False]
    basic_payment.data['sender'].data['status'] = Status.abort
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['status'] == Status.abort


def test_payment_process_get_stable_id(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [ set([ Status.needs_stable_id ]) ]
    bcm.get_stable_id.side_effect = ['stable_id']
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['stable_id'] == 'stable_id'


def test_payment_process_get_extended_kyc(basic_payment, ppctx):
    bcm, pp = ppctx
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [ set([Status.needs_kyc_data]) ]
    kyc_data = KYCData('{"payment_reference_id": "123", "type": "A"}')
    bcm.get_extended_kyc.side_effect = [
        (kyc_data, 'sig', 'cert')
    ]
    bcm.ready_for_settlement.side_effect = [Status.ready_for_settlement]
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['kyc_data'] == kyc_data
    assert new_payment.data['receiver'].data['kyc_signature'] == 'sig'
    assert new_payment.data['receiver'].data['kyc_certificate'] == 'cert'
