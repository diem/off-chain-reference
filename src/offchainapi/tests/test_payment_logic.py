from ..payment_logic import *
from ..protocol_messages import CommandRequestObject, make_success_response
from ..business import BusinessAsyncInterupt
from ..utils import JSONFlag, JSONSerializable
from ..libra_address import LibraAddress
from ..sample_command import SampleCommand

from unittest.mock import MagicMock
import pytest


def test_payment_command_serialization_net(payment):
    cmd = PaymentCommand(payment)
    data = cmd.get_json_data_dict(JSONFlag.NET)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.NET)
    assert cmd == cmd2


def test_payment_command_serialization_parse(payment):
    cmd = PaymentCommand(payment)
    data = cmd.get_json_data_dict(JSONFlag.NET)
    obj = JSONSerializable.parse(data, JSONFlag.NET)
    assert obj == cmd

    cmd_s = SampleCommand('Hello', deps=['World'])
    data2 = cmd_s.get_json_data_dict(JSONFlag.NET)
    cmd_s2 = JSONSerializable.parse(data2, JSONFlag.NET)
    assert cmd_s == cmd_s2


def test_payment_command_serialization_store(payment):
    cmd = PaymentCommand(payment)
    data = cmd.get_json_data_dict(JSONFlag.STORE)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.STORE)
    assert cmd == cmd2


def test_payment_end_to_end_serialization(payment):
    # Define a full request/reply with a Payment and test serialization
    cmd = PaymentCommand(payment)
    request = CommandRequestObject(cmd)
    request.seq = 10
    request.response = make_success_response(request)
    data = request.get_json_data_dict(JSONFlag.STORE)
    request2 = CommandRequestObject.from_json_data_dict(data, JSONFlag.STORE)
    assert request == request2


def test_payment_command_multiple_dependencies_fail(payment):
    new_payment = payment.new_version('v1')
    # Error: 2 dependencies
    new_payment.previous_versions += ['v2']
    cmd = PaymentCommand(new_payment)
    with pytest.raises(PaymentLogicError):
        cmd.get_object(new_payment.get_version(),
                       {payment.get_version(): payment})


def test_payment_command_create_fail(payment):
    cmd = PaymentCommand(payment)
    # Error: two new versions
    cmd.creates_versions += [payment.get_version()]
    with pytest.raises(PaymentLogicError):
        cmd.get_object(payment.get_version(), {})


def test_payment_command_missing_dependency_fail(payment):
    new_payment = payment.new_version('v1')
    cmd = PaymentCommand(new_payment)
    with pytest.raises(PaymentLogicError):
        cmd.get_object(new_payment.get_version(), {})


def test_payment_create_from_recipient(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True] * 4
    processor.check_new_payment(payment)


def test_payment_create_from_sender_sig_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.add_recipient_signature('BAD SINGNATURE')
    bcm.validate_recipient_signature.side_effect = [
        BusinessValidationFailure('Sig fails')
    ]
    with pytest.raises(BusinessValidationFailure):
        processor.check_new_payment(payment)


def test_payment_create_from_sender(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    processor.check_new_payment(payment)


def test_payment_create_from_sender_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    payment.receiver.update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)


def test_payment_create_from_receiver_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.sender.update({'status': Status.ready_for_settlement})
    payment.receiver.update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)


def test_payment_create_from_receiver_bad_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False]
    payment.receiver.update({'status': Status.needs_recipient_signature})
    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)


def test_payment_update_from_sender(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    diff = {}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    processor.check_new_update(payment, new_obj)


def test_payment_update_from_sender_modify_receiver_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    diff = {'receiver': {'status': "settled"}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.receiver.data['status'] != payment.receiver.data['status']
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_payment_update_from_receiver_invalid_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False]
    diff = {'receiver': {'status': "needs_recipient_signature"}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_payment_update_from_receiver_invalid_transition_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False]
    payment.receiver.update({'status': Status.ready_for_settlement})
    diff = {'receiver': {'status': "needs_kyc_data"}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_payment_update_from_receiver_unilateral_abort_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False]
    payment.receiver.update({'status': Status.ready_for_settlement})
    diff = {'receiver': {'status': "abort"}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_payment_processor_check(states, payment, processor, executor):
    src_addr, dst_addr, origin_addr, res = states

    a0 = MagicMock(spec=LibraAddress)
    a0.as_str.return_value = src_addr
    a1 = MagicMock(spec=LibraAddress)
    a1.as_str.return_value = dst_addr
    origin = MagicMock(spec=LibraAddress)
    origin.as_str.return_value = origin_addr

    vasp, channel, _ = executor.get_context()
    channel.get_my_address.return_value = a0
    channel.get_other_address.return_value = a1

    command = PaymentCommand(payment)
    command.set_origin(origin)
    if res:
        processor.check_command(vasp, channel, executor, command)
    else:
        with pytest.raises(PaymentLogicError):
            processor.check_command(vasp, channel, executor, command)


def test_payment_process_receiver_new_payment(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.needs_kyc_data]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [False]
    assert payment.receiver.status == Status.none
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.status == Status.needs_kyc_data

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [True]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [False]
    new_payment2 = processor.payment_process(new_payment)
    assert new_payment2.receiver.status == Status.ready_for_settlement

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [True]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]
    new_payment3 = processor.payment_process(new_payment2)
    assert new_payment3.receiver.status == Status.settled


def test_payment_process_interrupt(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessAsyncInterupt(1234)]
    with processor.storage_factory as _:
        new_payment = processor.payment_process(payment)
    assert not new_payment.has_changed()
    assert new_payment.receiver.status == Status.none


def test_payment_process_interrupt_resume(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True, True, True, True]
    bcm.check_account_existence.side_effect = [None, None]
    bcm.next_kyc_level_to_request.side_effect = [Status.ready_for_settlement]
    bcm.next_kyc_to_provide.side_effect = [BusinessAsyncInterupt(1234)]

    assert payment.receiver.status == Status.none
    with processor.storage_factory as _:
        new_payment = processor.payment_process(payment)
    assert new_payment.has_changed()
    assert new_payment.receiver.status == Status.ready_for_settlement

    bcm.next_kyc_to_provide.side_effect = [set()]
    bcm.ready_for_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]

    processor.notify_callback(1234)
    with processor.storage_factory as _:
        L = processor.payment_process_ready()
    assert len(L) == 1
    assert len(processor.callbacks) == 0
    assert len(processor.ready) == 0
    print(bcm.method_calls)
    L[0].receiver.status == Status.settled


def test_payment_process_abort(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessForceAbort]
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.status == Status.abort


def test_payment_process_abort_from_sender(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    bcm.ready_for_settlement.side_effect = [False]
    payment.sender.status = Status.abort
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.status == Status.abort


def test_payment_process_get_stable_id(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [set([Status.needs_stable_id])]
    bcm.get_stable_id.side_effect = ['stable_id']
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.stable_id == 'stable_id'


def test_payment_process_get_extended_kyc(payment, processor, kyc_data):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [set([Status.needs_kyc_data])]
    bcm.get_extended_kyc.side_effect = [(kyc_data, 'sig', 'cert')]
    bcm.ready_for_settlement.side_effect = [Status.ready_for_settlement]
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.kyc_data == kyc_data
    assert new_payment.receiver.kyc_signature == 'sig'
    assert new_payment.receiver.kyc_certificate == 'cert'
