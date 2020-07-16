# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..sample.sample_service import sample_business, sample_vasp
from ..payment_logic import Status, PaymentProcessor, PaymentCommand
from ..payment import PaymentActor, PaymentObject, StatusObject
from ..libra_address import LibraAddress
from ..utils import JSONFlag
from ..protocol_messages import CommandRequestObject, CommandResponseObject, \
    OffChainError
from ..asyncnet import Aionet

from mock import AsyncMock
import json
import pytest
import asyncio


@pytest.fixture
def business_and_processor(three_addresses, store):
    _, _, a0 = three_addresses
    bc = sample_business(a0)
    proc = PaymentProcessor(bc, store)
    proc.loop = asyncio.new_event_loop()
    return (bc, proc)


@pytest.fixture
def payment_as_receiver(three_addresses, sender_actor, payment_action):
    _, _, a0 = three_addresses
    subaddr = LibraAddress.encode(a0.decoded_address, b'x'*8)
    receiver = PaymentActor(subaddr.as_str(), StatusObject(Status.none), [])
    return PaymentObject(
        sender_actor, receiver, 'ref', 'orig_ref', 'desc', payment_action
    )


@pytest.fixture
def kyc_payment_as_receiver(payment_as_receiver, kyc_data):
    payment = payment_as_receiver
    payment.sender.add_kyc_data(kyc_data)
    payment.receiver.add_kyc_data(kyc_data)
    payment.sender.change_status(StatusObject(Status.needs_recipient_signature))
    return payment


@pytest.fixture
def settled_payment_as_receiver(kyc_payment_as_receiver):
    payment = kyc_payment_as_receiver
    payment.add_recipient_signature('SIG')
    payment.sender.change_status(Status.ready_for_settlement)
    return payment


@pytest.fixture
def payment_as_sender(three_addresses, receiver_actor, payment_action):
    _, _, a0 = three_addresses
    subaddr = LibraAddress.encode(a0.decoded_address, b'x'*8)
    sender = PaymentActor(subaddr.as_str(), StatusObject(Status.none), [])
    return PaymentObject(
        sender, receiver_actor, 'ref', 'orig_ref', 'desc', payment_action
    )


@pytest.fixture
def kyc_payment_as_sender(payment_as_sender, kyc_data):
    payment = payment_as_sender
    payment.sender.add_kyc_data(kyc_data)
    payment.receiver.add_kyc_data(kyc_data)
    payment.sender.change_status(StatusObject(Status.needs_recipient_signature))
    payment.add_recipient_signature('SIG')
    assert payment.sender is not None
    return payment


@pytest.fixture
def my_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0


@pytest.fixture
def other_addr(three_addresses):
    _, _, a0 = three_addresses
    return a0


@pytest.fixture
def vasp(my_addr):
    return sample_vasp(my_addr)


@pytest.fixture
def json_request(my_addr, other_addr, payment_action):
    sub_sender = LibraAddress.encode(my_addr.decoded_address, b'a'*8)
    sub_receiver = LibraAddress.encode(other_addr.decoded_address, b'b'*8)

    sender = PaymentActor(sub_sender.as_str(), StatusObject(Status.none), [])
    receiver = PaymentActor(sub_receiver.as_str(), StatusObject(Status.none), [])
    ref = f'{other_addr.as_str()}_XYZ'
    payment = PaymentObject(
        sender, receiver, ref, 'Original Reference', 'A description...', payment_action
    )
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.cid = 0
    return request.get_json_data_dict(JSONFlag.NET)


@pytest.fixture(params=[
    (None, None, 'failure', True, 'parsing'),
    (0, 0, 'success', None, None),
    (0, 0, 'success', None, None),
    (10, 10, 'success', None, None),
])
def simple_response_json_error(request, key):
    cid, cmd_seq, status, protoerr, errcode = request.param
    resp = CommandResponseObject()
    resp.status = status
    resp.cid = cid
    if status == 'failure':
        resp.error = OffChainError(protoerr, errcode)
    json_obj = resp.get_json_data_dict(JSONFlag.NET)
    signed_json = key.sign_message(json.dumps(json_obj))
    return signed_json


def test_business_simple(my_addr):
    bc = sample_business(my_addr)


def test_business_is_related(business_and_processor, payment_as_receiver):
    bc, proc = business_and_processor
    payment = payment_as_receiver

    kyc_level = proc.loop.run_until_complete(
        bc.next_kyc_level_to_request(payment))
    assert kyc_level == Status.needs_kyc_data

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()
    assert ret_payment.receiver.status.as_status() == Status.needs_kyc_data


def test_business_is_kyc_provided(business_and_processor, kyc_payment_as_receiver):
    bc, proc = business_and_processor
    payment = kyc_payment_as_receiver

    kyc_level = proc.loop.run_until_complete(
        bc.next_kyc_level_to_request(payment))
    assert kyc_level == Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = proc.loop.run_until_complete(bc.ready_for_settlement(ret_payment))
    assert ready
    assert ret_payment.receiver.status.as_status() == Status.ready_for_settlement


def test_business_is_kyc_provided_sender(business_and_processor, kyc_payment_as_sender):
    bc, proc = business_and_processor
    payment = kyc_payment_as_sender
    assert bc.is_sender(payment)
    kyc_level = proc.loop.run_until_complete(
        bc.next_kyc_level_to_request(payment))
    assert kyc_level == Status.needs_recipient_signature

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = proc.loop.run_until_complete(bc.ready_for_settlement(ret_payment))
    assert ready
    assert ret_payment.sender.status.as_status() == Status.ready_for_settlement
    assert bc.get_account('x'*8)['balance'] == 5.0


def test_vasp_simple(json_request, vasp, other_addr, loop):
    vasp.pp.loop = loop
    net = AsyncMock(Aionet)
    vasp.pp.set_network(net)

    key = vasp.info_context.get_peer_compliance_signature_key(other_addr)
    signed_json_request = key.sign_message(json.dumps(json_request))
    xx = vasp.process_request(other_addr, signed_json_request)
    assert xx
    requests = [xx]
    assert len(requests) == 1
    assert requests[0].type is CommandResponseObject

    assert len(vasp.pp.futs) == 1
    for fut in vasp.pp.futs:
        vasp.pp.loop.run_until_complete(fut)
        fut.result()

    assert len(net.method_calls) == 2


def test_vasp_simple_wrong_VASP(json_request, other_addr, loop, key):
    my_addr = LibraAddress.encode(b'X'*16)
    vasp = sample_vasp(my_addr)
    vasp.pp.loop = loop

    key = vasp.info_context.get_peer_compliance_signature_key(other_addr)
    signed_json_request = key.sign_message(json.dumps(json_request))

    try:
        # vasp.pp.start_processor()
        resp = vasp.process_request(other_addr, signed_json_request)
        responses = [resp]
        assert len(responses) == 1
        assert responses[0].type is CommandResponseObject
        content = json.loads(key.verify_message(responses[0].content))
        assert 'failure' == content['status']
    finally:
        # vasp.pp.stop_processor()
        pass


def test_vasp_response(simple_response_json_error, vasp, other_addr):
    with pytest.raises(Exception):
        vasp.process_response(other_addr, simple_response_json_error)
