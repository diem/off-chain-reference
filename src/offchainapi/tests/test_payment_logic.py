from ..status_logic import Status
from ..payment_command import PaymentCommand, PaymentLogicError
from ..business import BusinessForceAbort, BusinessValidationFailure

from ..payment import PaymentObject
from ..libra_address import LibraAddress
from ..asyncnet import Aionet
from ..storage import StorableFactory
from ..payment_logic import PaymentProcessor
from ..utils import JSONFlag

from .basic_business_context import BasicBusinessContext

import asyncio
from unittest.mock import MagicMock
from mock import AsyncMock
import pytest


def test_check_new_payment_from_recipient(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True] * 4
    processor.check_new_payment(payment)


def test_check_new_payment_from_sender(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    processor.check_new_payment(payment)


def test_check_new_payment_sender_set_receiver_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    payment.receiver.update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)


def test_check_new_payment_receiver_set_sender_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.sender.update({'status': Status.ready_for_settlement})
    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)


def test_check_signatures_invalid_signature_fail(kyc_data, payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.receiver.add_kyc_data(kyc_data, 'kyc_sig', 'kyc_cert')
    bcm.validate_kyc_signature.side_effect = [
        BusinessValidationFailure('Sig fails')
    ]
    with pytest.raises(BusinessValidationFailure):
        processor.check_signatures(payment)


def test_check_signatures_bad_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.add_recipient_signature('BAD SINGNATURE')
    bcm.validate_recipient_signature.side_effect = [
        BusinessValidationFailure('Sig fails')
    ]
    with pytest.raises(BusinessValidationFailure):
        processor.check_signatures(payment)


def test_payment_update_from_sender(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    diff = {}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    processor.check_new_update(payment, new_obj)


def test_check_new_update_sender_modify_receiver_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]*5
    diff = {'receiver': {'status': "settled"}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.receiver.data['status'] != payment.receiver.data['status']
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_check_new_update_receiver_modify_sender_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False]*5
    diff = {'sender': {'status': "settled"}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.sender.data['status'] != payment.sender.data['status']
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_check_command(payment, processor, executor):
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
            processor.check_command(channel, command)
        else:
            with pytest.raises(PaymentLogicError):
                processor.check_command(channel, command)


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
    bcm.has_settled.side_effect = [False]
    new_payment2 = processor.payment_process(new_payment)
    assert new_payment2.receiver.status == Status.ready_for_settlement

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [ True ]
    bcm.has_settled.side_effect = [True]
    new_payment3 = processor.payment_process(new_payment2)
    assert new_payment3.receiver.status == Status.ready_for_settlement


def test_payment_process_abort_from_receiver(payment, processor):
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


def test_persist(payment):
    store = StorableFactory({})

    my_addr = LibraAddress(b'A'*32)
    my_addr_str = my_addr.as_str()
    bcm = BasicBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)
    print()
    print(cmd.pretty(JSONFlag.NET))

    assert len(processor.list_command_obligations()) == 0

    # Check that a  atomic write context must be in place.
    with pytest.raises(RuntimeError):
        processor.persist_command_obligation(my_addr_str, seq=10, command=cmd)

    # Create 1 oblogation
    with processor.storage_factory.atomic_writes():
        processor.persist_command_obligation(my_addr_str, seq=10, command=cmd)

    assert processor.obligation_exists(my_addr_str, seq=10)
    assert len(processor.list_command_obligations()) == 1

    # Check for something that does not exist
    assert not processor.obligation_exists(my_addr_str, seq=11)

    # delete obligation
    with processor.storage_factory.atomic_writes():
        processor.release_command_obligation(my_addr_str, seq=10)

    assert len(processor.list_command_obligations()) == 0


def test_reprocess(payment,  loop):
    store = StorableFactory({})

    my_addr = LibraAddress(b'A'*32)
    my_addr_str = my_addr.as_str()
    bcm = BasicBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)

    # Create 1 oblogation
    with processor.storage_factory.atomic_writes():
        processor.persist_command_obligation(my_addr_str, seq=10, command=cmd)

    assert len(processor.list_command_obligations()) == 1

    # Ensure is is recheduled
    coro = processor.retry_process_commands()
    tasks = loop.run_until_complete(coro)
    assert len(tasks) == 1
    assert tasks[0].done() == 1

    assert tasks[0].result() is None

    # Ensure that the obligation is cleared
    assert len(processor.list_command_obligations()) == 0


def test_process_command_success_no_proc(payment, loop):
    store = StorableFactory({})

    my_addr = LibraAddress(b'B'*32)
    other_addr = LibraAddress('AAAA')
    bcm = BasicBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)
    cmd.set_origin(my_addr)

    # No obligation means no processing
    coro = processor.process_command_success_async(other_addr, cmd, seq=10)
    _ = loop.run_until_complete(coro)

def test_process_command_success_vanilla(payment, loop):
    store = StorableFactory({})

    my_addr = LibraAddress(b'B'*32)
    other_addr = LibraAddress('AAAA')
    bcm = BasicBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)
    cmd.set_origin(other_addr)

    # Create an obligation first
    with processor.storage_factory.atomic_writes():
        processor.persist_command_obligation(other_addr.as_str(), seq=10, command=cmd)

    # No obligation means no processing
    coro = processor.process_command_success_async(other_addr, cmd, seq=10)
    _ = loop.run_until_complete(coro)

    assert [call[0] for call in net.method_calls] == [
        'sequence_command', 'send_request']
