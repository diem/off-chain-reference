from ..status_logic import Status
from ..payment_command import PaymentCommand, PaymentLogicError
from ..business import BusinessForceAbort, BusinessValidationFailure

from ..payment import PaymentObject
from ..libra_address import LibraAddress

from unittest.mock import MagicMock
import pytest



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


def test_payment_processor_check(payment, processor, executor):
    states = [
        ('AAAA', 'BBBB', 'AAAA', True),
        ('BBBB', 'AAAA', 'AAAA', True),
        ('CCCC', 'AAAA', 'AAAA', False),
        ('BBBB', 'CCCC', 'AAAA', False),
        ('DDDD', 'CCCC', 'AAAA', False),
        ('AAAA', 'BBBB', 'BBBB', True),
        ('BBBB', 'AAAA', 'DDDD', False),
    ]
    for state in states:
        src_addr, dst_addr, origin_addr, res = state

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
    bcm.ready_for_settlement.side_effect = [ True ]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [False]
    new_payment2 = processor.payment_process(new_payment)
    assert new_payment2.receiver.status == Status.ready_for_settlement

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [ True ]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]
    new_payment3 = processor.payment_process(new_payment2)
    assert new_payment3.receiver.status == Status.settled


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
