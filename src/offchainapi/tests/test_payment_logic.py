# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..protocol import VASPPairChannel
from ..status_logic import Status, STATUS_HEIGHTS
from ..payment_command import PaymentCommand, PaymentLogicError
from ..business import BusinessForceAbort, BusinessValidationFailure

from ..payment import PaymentObject, StatusObject, PaymentActor
from ..libra_address import LibraAddress
from ..asyncnet import Aionet
from ..storage import StorableFactory
from ..payment_logic import PaymentProcessor
from ..utils import JSONFlag
from ..errors import OffChainErrorCode

from .basic_business_context import TestBusinessContext

from unittest.mock import MagicMock
from mock import AsyncMock
import pytest
import copy


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
    payment.receiver.update({'status': StatusObject(Status.ready_for_settlement)})
    with pytest.raises(PaymentLogicError) as e:
        processor.check_new_payment(payment)
    assert e.value.error_code == OffChainErrorCode.payment_wrong_status


def test_check_new_payment_receiver_set_sender_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.sender.update({'status': StatusObject(Status.ready_for_settlement)})
    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)

def test_check_signatures_bad_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4
    payment.add_recipient_signature('BAD SINGNATURE')
    bcm.validate_recipient_signature.side_effect = [
        BusinessValidationFailure('Sig fails'),
        BusinessValidationFailure('Sig fails')
    ]
    with pytest.raises(BusinessValidationFailure):
        processor.check_signatures(payment)

    with pytest.raises(PaymentLogicError):
        processor.check_new_payment(payment)

def test_bad_sender_actor_address(payment, processor):
    snone = StatusObject(Status.none)
    actor = PaymentActor('XYZ', snone, [])

    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4

    payment.sender = actor
    with pytest.raises(PaymentLogicError) as e:
        processor.check_new_payment(payment)
    assert e.value.error_code == OffChainErrorCode.payment_invalid_libra_address

def test_empty_sender_actor_subaddress(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4

    addr = LibraAddress.from_encoded_str(payment.sender.address)
    addr2 = LibraAddress.from_bytes("dm", addr.onchain_address_bytes, None)
    payment.sender.address = addr2.as_str()

    processor.check_new_payment(payment)

def test_bad_receiver_actor_address(payment, processor):
    snone = StatusObject(Status.none)
    actor = PaymentActor('XYZ', snone, [])

    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4

    payment.receiver = actor
    with pytest.raises(PaymentLogicError) as e:
        processor.check_new_payment(payment)
    assert e.value.error_code == OffChainErrorCode.payment_invalid_libra_address

def test_empty_receiver_actor_subaddress(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 4

    addr = LibraAddress.from_encoded_str(payment.sender.address)
    addr2 = LibraAddress.from_bytes("dm", addr.onchain_address_bytes, None)
    payment.receiver.address = addr2.as_str()

    processor.check_new_payment(payment)

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
    diff = {'receiver': {'status': { 'status': "ready_for_settlement"}}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.receiver.data['status'] != payment.receiver.data['status']
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)

def test_check_new_update_bad_signature(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False] * 5
    bcm.validate_recipient_signature.side_effect = [
        BusinessValidationFailure('Bad signature') ]

    diff = {'recipient_signature': 'XXX_BAD_SIGN'}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)

    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_check_new_update_receiver_modify_sender_state_fail(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [False]*5
    diff = {'sender': {'status': { 'status': "ready_for_settlement"}}}
    new_obj = payment.new_version()
    new_obj = PaymentObject.from_full_record(diff, base_instance=new_obj)
    assert new_obj.sender.data['status'] != payment.sender.data['status']
    with pytest.raises(PaymentLogicError):
        processor.check_new_update(payment, new_obj)


def test_check_command(three_addresses, payment, processor):
    states = [
        (b'AAAA', b'BBBB', b'AAAA', True),
        (b'BBBB', b'AAAA', b'AAAA', True),
        (b'CCCC', b'AAAA', b'AAAA', False),
        (b'BBBB', b'CCCC', b'AAAA', False),
        (b'DDDD', b'CCCC', b'AAAA', False),
        (b'AAAA', b'BBBB', b'BBBB', True),
        (b'BBBB', b'AAAA', b'DDDD', False),
    ]
    a0, _, a1 = three_addresses
    channel = MagicMock(spec=VASPPairChannel)
    channel.get_my_address.return_value = a0
    channel.get_other_address.return_value = a1

    for state in states:
        src_addr, dst_addr, origin_addr, res = state

        a0 = LibraAddress.from_bytes("dm", src_addr*4)
        a1 = LibraAddress.from_bytes("dm", dst_addr*4)
        origin = LibraAddress.from_bytes("dm", origin_addr*4)

        channel.get_my_address.return_value = a0
        channel.get_other_address.return_value = a1

        payment.data['reference_id'] = f'{origin.as_str()}_XYZ'
        command = PaymentCommand(payment)
        command.set_origin(origin)

        if res:
            my_address = channel.get_my_address()
            other_address = channel.get_other_address()
            processor.check_command(my_address, other_address, command)
        else:
            with pytest.raises(PaymentLogicError):
                my_address = channel.get_my_address()
                other_address = channel.get_other_address()
                processor.check_command(my_address, other_address, command)

def test_check_command_bad_refid(three_addresses, payment, processor):
    a0, _, a1 = three_addresses
    channel = MagicMock(spec=VASPPairChannel)
    channel.get_my_address.return_value = a0
    channel.get_other_address.return_value = a1
    origin = a1 # Only check new commands from other side

    # Wrong origin ref_ID address
    payment.reference_id = f'{origin.as_str()[:-2]}ZZ_XYZ'
    command = PaymentCommand(payment)
    command.set_origin(origin)

    my_address = channel.get_my_address()
    other_address = channel.get_other_address()

    with pytest.raises(PaymentLogicError) as e:
        processor.check_command(my_address, other_address, command)
    assert e.value.error_code == OffChainErrorCode.payment_wrong_structure


def test_payment_process_receiver_new_payment(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.needs_kyc_data]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [False]
    assert payment.receiver.status.as_status() == Status.none
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.status.as_status() == Status.needs_kyc_data

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [ True ]
    new_payment2 = processor.payment_process(new_payment)
    assert new_payment2.receiver.status.as_status() == Status.ready_for_settlement

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [ True ]
    new_payment3 = processor.payment_process(new_payment2)
    assert new_payment3.receiver.status.as_status() == Status.ready_for_settlement


def test_payment_process_abort_from_receiver(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [ BusinessForceAbort(OffChainErrorCode.payment_insufficient_funds, 'Not enough money in account.') ]
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.status.as_status() == Status.abort


def test_payment_process_abort_from_sender(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    bcm.ready_for_settlement.side_effect = [False]
    payment.sender.status = StatusObject(Status.abort, 'code', 'msg')
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.status.as_status() == Status.abort

def test_payment_process_abort_from_business(payment, processor):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    bcm.ready_for_settlement.side_effect = [
        BusinessForceAbort(OffChainErrorCode.payment_vasp_error, 'MESSAGE')

     ]
    new_payment = processor.payment_process(payment)
    assert payment.receiver.status.as_status() != Status.abort
    assert new_payment.receiver.status.as_status() == Status.abort
    assert new_payment.receiver.status.abort_code == OffChainErrorCode.payment_vasp_error.value
    assert new_payment.receiver.status.abort_message == 'MESSAGE'

def test_payment_process_get_extended_kyc(payment, processor, kyc_data):
    bcm = processor.business_context()
    bcm.is_recipient.side_effect = [True]
    bcm.next_kyc_to_provide.side_effect = [set([Status.needs_kyc_data])]
    bcm.get_extended_kyc.side_effect = [kyc_data]
    bcm.ready_for_settlement.side_effect = [Status.ready_for_settlement]
    new_payment = processor.payment_process(payment)
    assert new_payment.receiver.kyc_data == kyc_data


def test_process_command_success_no_proc(payment, loop, db):
    store = StorableFactory(db)

    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)
    bcm = TestBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)
    cmd.set_origin(my_addr)

    # No obligation means no processing
    coro = processor.process_command_success_async(other_addr, cmd, seq=10)
    _ = loop.run_until_complete(coro)

def test_process_command_success_vanilla(payment, loop, db):
    store = StorableFactory(db)

    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)
    bcm = TestBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)
    cmd.set_origin(other_addr)

    # No obligation means no processing
    coro = processor.process_command_success_async(other_addr, cmd, seq=10)
    _ = loop.run_until_complete(coro)

    assert [call[0] for call in net.method_calls] == [
        'sequence_command', 'send_request']

async def test_process_command_happy_path(payment, loop, db):
    store = StorableFactory(db)

    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)
    my_bcm = TestBusinessContext(my_addr)
    other_bcm = TestBusinessContext(other_addr)
    # Use the same store/DB backend
    my_processor = PaymentProcessor(my_bcm, store, loop)
    other_processor = PaymentProcessor(other_bcm, store, loop)
    net = AsyncMock(Aionet)
    my_processor.set_network(net)
    other_processor.set_network(net)

    other_cmd = PaymentCommand(payment)
    other_cmd.set_origin(other_addr)

    # me: process success command
    assert len(my_processor.object_store) == 0
    fut = my_processor.process_command(other_addr, other_cmd, other_cmd.get_request_cid(), True)

    assert len(my_processor.object_store) == 1
    other_cmd_new_vers = list(other_cmd.get_new_object_versions())
    assert len(other_cmd_new_vers) == 1
    assert my_processor.object_store[other_cmd_new_vers[0]] == payment

    assert my_processor.get_latest_payment_by_ref_id(payment.reference_id) == payment
    await fut

    # Make some differences, and test that commands are isolated per VASPs
    payment2 = copy.deepcopy(payment)
    payment2.update({
        'original_payment_reference_id': payment.reference_id
    })

    my_cmd = PaymentCommand(payment2)
    my_cmd.set_origin(my_addr)
    # other: process success command
    assert len(other_processor.object_store) == 0
    fut = other_processor.process_command(other_addr, my_cmd, my_cmd.get_request_cid(), True)

    assert len(other_processor.object_store) == 1
    my_cmd_new_vers = list(my_cmd.get_new_object_versions())
    assert len(my_cmd_new_vers) == 1

    # Even though payment and payment2 have the same version id and share
    # the db backend, they can distinguish the payments
    assert other_processor.object_store[my_cmd_new_vers[0]] == payment2
    assert my_processor.object_store[other_cmd_new_vers[0]] != payment2
    assert my_processor.object_store[other_cmd_new_vers[0]] == payment

    assert other_processor.get_latest_payment_by_ref_id(payment2.reference_id) == payment2
    await fut

def reset_payment_status(payment):
    payment.sender.status = StatusObject(Status.none)
    payment.receiver.status = StatusObject(Status.none)

def update_role_status(payment, role, status):
    if status == Status.abort:
        payment.data[role].status = StatusObject(status, "", "")
    else:
        payment.data[role].status = StatusObject(status)

def test_can_change_status(payment, loop, db):
    """ Test invalid status change are rejected """
    store = StorableFactory(db)
    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)
    bcm = TestBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    # 1: if one side is aborted, it should never switch to other status
    # sender action
    update_role_status(payment, "sender", Status.abort)
    assert processor.can_change_status(payment, Status.abort, actor_is_sender=True)
    assert not processor.can_change_status(payment, Status.ready_for_settlement, actor_is_sender=True)
    reset_payment_status(payment)

    # receiver action
    update_role_status(payment, "receiver", Status.abort)
    assert processor.can_change_status(payment, Status.abort, actor_is_sender=False)
    assert not processor.can_change_status(payment, Status.ready_for_settlement, actor_is_sender=False)
    reset_payment_status(payment)

    # 2: if one side aborts, the other side cannot transit to status other than abort
    # sender action
    update_role_status(payment, "receiver", Status.abort)
    assert processor.can_change_status(payment, Status.abort, actor_is_sender=True)
    assert not processor.can_change_status(payment, Status.ready_for_settlement, actor_is_sender=True)
    reset_payment_status(payment)

    # receiver action
    update_role_status(payment, "sender", Status.abort)
    assert processor.can_change_status(payment, Status.abort, actor_is_sender=False)
    assert not processor.can_change_status(payment, Status.ready_for_settlement, actor_is_sender=False)
    reset_payment_status(payment)

    # 3: if one side is ready_for_settlement, it can only switch to abort
    # when the other side turns to abort
    # sender action
    update_role_status(payment, "sender", Status.ready_for_settlement)
    update_role_status(payment, "receiver", Status.needs_kyc_data)
    assert not processor.can_change_status(payment, Status.abort, actor_is_sender=True)
    assert not processor.can_change_status(payment, Status.soft_match, actor_is_sender=True)
    reset_payment_status(payment)

    # receiver action
    update_role_status(payment, "sender", Status.needs_kyc_data)
    update_role_status(payment, "receiver", Status.ready_for_settlement)
    assert not processor.can_change_status(payment, Status.abort, actor_is_sender=False)
    assert not processor.can_change_status(payment, Status.needs_recipient_signature, actor_is_sender=False)
    reset_payment_status(payment)

    # 4: if both sides are ready_for_settlement, neither side can change status
    update_role_status(payment, "sender", Status.ready_for_settlement)
    update_role_status(payment, "receiver", Status.ready_for_settlement)
    assert not processor.can_change_status(payment, Status.abort, actor_is_sender=True)
    assert not processor.can_change_status(payment, Status.abort, actor_is_sender=False)
    reset_payment_status(payment)

    # 5: one side cannot change to lower status
    # sender action
    for old_status in Status:
        update_role_status(payment, "sender", old_status)
        for new_status in Status:
            if STATUS_HEIGHTS[new_status] < STATUS_HEIGHTS[old_status]:
                assert not processor.can_change_status(payment, new_status, actor_is_sender=True)

    reset_payment_status(payment)

    # receiver action
    for old_status in Status:
        update_role_status(payment, "receiver", old_status)
        for new_status in Status:
            if STATUS_HEIGHTS[new_status] < STATUS_HEIGHTS[old_status]:
                assert not processor.can_change_status(payment, new_status, actor_is_sender=False)
