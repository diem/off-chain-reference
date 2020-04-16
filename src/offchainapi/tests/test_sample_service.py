from ..sample_service import *
from ..payment_logic import Status, PaymentProcessor, PaymentCommand
from ..payment import PaymentActor, PaymentObject
from ..libra_address import LibraAddress
from ..business import BusinessAsyncInterupt
from ..utils import JSONFlag
from ..protocol_messages import CommandRequestObject, CommandResponseObject, \
    OffChainError

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def business_and_processor(three_addresses, store):
    _, _, a0 = three_addresses
    bc = sample_business(a0)
    proc = PaymentProcessor(bc, store)
    return (bc, proc)


@pytest.fixture
def payment_as_receiver(three_addresses, sender_actor, payment_action):
    _, _, a0 = three_addresses
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    return PaymentObject(
        sender_actor, receiver, 'ref', 'orig_ref', 'desc', payment_action
    )


@pytest.fixture
def kyc_payment_as_receiver(payment_as_receiver, kyc_data):
    payment = payment_as_receiver
    payment.sender.add_kyc_data(kyc_data, 'KYC_SIG', 'CERT')
    payment.receiver.add_kyc_data(kyc_data, 'KYC_SIG', 'CERT')
    payment.sender.change_status(Status.needs_recipient_signature)
    return payment


@pytest.fixture
def settled_payment_as_receiver(kyc_payment_as_receiver):
    payment = kyc_payment_as_receiver
    payment.add_recipient_signature('SIG')
    payment.sender.change_status(Status.settled)
    return payment


@pytest.fixture
def payment_as_sender(three_addresses, receiver_actor, payment_action):
    _, _, a0 = three_addresses
    sender = PaymentActor(a0.as_str(), '1', Status.none, [])
    return PaymentObject(
        sender, receiver_actor, 'ref', 'orig_ref', 'desc', payment_action
    )


@pytest.fixture
def kyc_payment_as_sender(payment_as_sender, kyc_data):
    payment = payment_as_sender
    payment.sender.add_kyc_data(kyc_data, 'KYC_SIG', 'CERT')
    payment.receiver.add_kyc_data(kyc_data, 'KYC_SIG', 'CERT')
    payment.sender.change_status(Status.needs_recipient_signature)
    payment.add_recipient_signature('SIG')
    assert payment.sender is not None
    return payment


@pytest.fixture
def my_addr(three_addresses):
    _, _, a0 = three_addresses
    return a0


@pytest.fixture
def other_addr(three_addresses):
    a0, _, _ = three_addresses
    return a0


@pytest.fixture
def asset_path(request):
    asset_path = Path(request.fspath).resolve()
    asset_path = asset_path.parents[3] / 'test_vectors'
    return asset_path


@pytest.fixture
def vasp(my_addr, asset_path):
    return sample_vasp(my_addr, asset_path)


@pytest.fixture(params=[
    (None, None, 'failure', True, 'parsing'),
    (0, 0, 'success', None, None),
    (0, 0, 'success', None, None),
    (10, 10, 'success', None, None),
])
def simple_response_json_error(request):
    seq, cmd_seq, status, protoerr, errcode = request.param
    resp = CommandResponseObject()
    resp.status = status
    resp.seq = seq
    resp.command_seq = cmd_seq
    if status == 'failure':
        resp.error = OffChainError(protoerr, errcode)
    json_obj = json.dumps(resp.get_json_data_dict(JSONFlag.NET))
    return json_obj


@pytest.fixture
def simple_request_json(payment_action, my_addr, other_addr):
    sender = PaymentActor(other_addr.as_str(), 'C', Status.none, [])
    receiver = PaymentActor(my_addr.as_str(), '1', Status.none, [])
    payment = PaymentObject(
        sender, receiver, 'ref', 'orig_ref', 'desc', payment_action
    )
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.seq = 0
    return json.dumps(request.get_json_data_dict(JSONFlag.NET))


def test_business_simple(my_addr):
    bc = sample_business(my_addr)


def test_business_is_related(business_and_processor, payment_as_receiver):
    bc, proc = business_and_processor
    payment = payment_as_receiver

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.needs_kyc_data

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()
    assert ret_payment.receiver.status == Status.needs_kyc_data


def test_business_is_kyc_provided(business_and_processor, kyc_payment_as_receiver):
    bc, proc = business_and_processor
    payment = kyc_payment_as_receiver

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.none

    with proc.storage_factory as _:
        ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    assert bc.ready_for_settlement(ret_payment)
    assert ret_payment.receiver.status == Status.ready_for_settlement


def test_business_is_kyc_provided_sender(business_and_processor, kyc_payment_as_sender):
    bc, proc = business_and_processor
    payment = kyc_payment_as_sender
    assert bc.is_sender(payment)
    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.needs_recipient_signature

    with proc.storage_factory as _:
        ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    assert bc.ready_for_settlement(ret_payment)
    assert ret_payment.sender.status == Status.ready_for_settlement
    assert bc.get_account('1')['balance'] == 5.0


def test_business_settled(business_and_processor, settled_payment_as_receiver):
    bc, proc = business_and_processor
    payment = settled_payment_as_receiver

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    assert bc.ready_for_settlement(ret_payment)
    assert ret_payment.receiver.status == Status.settled

    assert bc.get_account('1')['pending_transactions']['ref']['settled']
    assert bc.get_account('1')['balance'] == 15.0


def test_vasp_simple(simple_request_json, vasp, other_addr):
    vasp.process_request(other_addr, simple_request_json)
    responses = vasp.collect_messages()
    assert len(responses) == 2
    assert responses[0].type is CommandRequestObject
    assert responses[1].type is CommandResponseObject
    assert 'success' in responses[1].content


def test_vasp_simple_wrong_VASP(simple_request_json, asset_path, other_addr):
    my_addr = LibraAddress.encode_to_Libra_address(b'X'*16)
    vasp = sample_vasp(my_addr, asset_path)
    vasp.process_request(other_addr, simple_request_json)
    responses = vasp.collect_messages()
    assert len(responses) == 1
    assert responses[0].type is CommandResponseObject
    assert 'failure' in responses[0].content


def test_vasp_response(simple_response_json_error, vasp, other_addr):
    vasp.process_response(other_addr, simple_response_json_error)


def test_vasp_simple_interrupt(simple_request_json, vasp, other_addr):
    # Patch business context to first return an exception
    with patch.object(
        vasp.bc, 'ready_for_settlement', side_effect=[BusinessAsyncInterupt(1234)]
    ) as mock_thing:
        assert vasp.bc.ready_for_settlement == mock_thing
        vasp.process_request(other_addr, simple_request_json)
        responses = vasp.collect_messages()

    assert len(responses) == 2
    assert responses[0].type is CommandRequestObject
    assert responses[1].type is CommandResponseObject
    assert 'success' in responses[1].content

    with patch.object(
        vasp.bc, 'ready_for_settlement', return_value=True
    ) as mock_thing:
        assert vasp.bc.ready_for_settlement == mock_thing
        vasp.vasp.processor.notify_callback(1234)
        responses = vasp.collect_messages()

    assert len(responses) > 0
    assert 'ready_for' in str(responses[0].content)


def test_sample_vasp_info_is_authorised(request, vasp, other_addr):
    cert_file = Path(request.fspath).resolve()
    cert_file = cert_file.parents[3] / 'test_vectors' / 'client_cert.pem'
    cert_file = cert_file.resolve()
    with open(cert_file, 'rt') as f:
        cert_str = f.read()
    cert = OpenSSL.crypto.load_certificate(
        OpenSSL.crypto.FILETYPE_PEM, cert_str
    )
    assert vasp.info_context.is_authorised_VASP(cert, other_addr)
