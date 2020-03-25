from sample_service import *
from test_protocol import FakeAddress, FakeVASPInfo
from payment_logic import PaymentProcessor
from payment import *
from libra_address import LibraAddress
from utils import *
from protocol_messages import *
from business import VASPInfo

from unittest.mock import MagicMock
import pytest

@pytest.fixture
def basic_payment_as_receiver():
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(str(40), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

@pytest.fixture
def kyc_payment_as_receiver():
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(str(40), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Charlie"
    }
    """

    kycA = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Alice"
    }
    """

    payment.data['sender'].add_kyc_data(KYCData(kyc), 'KYC_SIG', 'CERT')
    payment.data['receiver'].add_kyc_data(KYCData(kycA), 'KYC_SIG', 'CERT')
    payment.data['sender'].change_status(Status.needs_recipient_signature)

    return payment

@pytest.fixture
def kyc_payment_as_sender():
    sender = PaymentActor(str(40), '1', Status.none, [])
    receiver = PaymentActor(str(100), 'C', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Charlie"
    }
    """

    kycA = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Alice"
    }
    """

    payment.data['sender'].add_kyc_data(KYCData(kycA), 'KYC_SIG', 'CERT')
    payment.data['receiver'].add_kyc_data(KYCData(kyc), 'KYC_SIG', 'CERT')
    payment.data['sender'].change_status(Status.needs_recipient_signature)
    payment.add_recipient_signature('SIG')
    assert payment.data['sender'] is not None
    return payment


@pytest.fixture
def settled_payment_as_receiver():
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(str(40), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Charlie"
    }
    """

    kycA = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Alice"
    }
    """

    payment.data['sender'].add_kyc_data(KYCData(kyc), 'KYC_SIG', 'CERT')
    payment.data['receiver'].add_kyc_data(KYCData(kycA), 'KYC_SIG', 'CERT')
    payment.add_recipient_signature('SIG')
    payment.data['sender'].change_status(Status.settled)
    return payment

@pytest.fixture
def addr_bc_proc():
    a0 = FakeAddress(0, 40)
    bc = sample_business(a0)
    proc = PaymentProcessor(bc)
    return (a0, bc, proc)

@pytest.fixture
def info_context():
    context = MagicMock(spec=VASPInfo)
    context.get_TLS_certificate.return_value = 'tls_cert.pem'
    context.get_TLS_key.return_value = 'tls_key.pem'
    context.get_peer_TLS_certificate.return_value = 'peer_cert.pem'
    context.get_all_peers_TLS_certificate.return_value = 'all_peers.pem'
    context.get_peer_base_url.return_value = ''
    return context

def test_business_simple():
    a0 = FakeAddress(0, 40)
    bc = sample_business(a0)

def test_business_is_related(basic_payment_as_receiver, addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = basic_payment_as_receiver

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.needs_kyc_data

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()
    assert ret_payment.data['receiver'].data['status'] == Status.needs_kyc_data

def test_business_is_kyc_provided(kyc_payment_as_receiver, addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = kyc_payment_as_receiver

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = bc.ready_for_settlement(ret_payment)
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.ready_for_settlement

def test_business_is_kyc_provided_sender(kyc_payment_as_sender, addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = kyc_payment_as_sender
    assert payment.data['sender'] is not None
    assert bc.is_sender(payment)
    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.needs_recipient_signature

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = bc.ready_for_settlement(ret_payment)
    assert ready
    assert ret_payment.data['sender'].data['status'] == Status.ready_for_settlement
    assert bc.get_account('1')['balance'] == 5.0


def test_business_settled(settled_payment_as_receiver,addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = settled_payment_as_receiver

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = bc.ready_for_settlement(ret_payment)
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.settled

    assert bc.get_account('1')['pending_transactions']['ref']['settled']
    assert bc.get_account('1')['balance'] == 15.0


@pytest.fixture
def simple_request_json():
    sender_addr = LibraAddress.encode_to_Libra_address(b'A'*16).encoded_address
    receiver_addr   = LibraAddress.encode_to_Libra_address(b'B'*16).encoded_address
    assert type(sender_addr) == str
    assert type(receiver_addr) == str

    sender = PaymentActor(sender_addr, 'C', Status.none, [])
    receiver = PaymentActor(receiver_addr, '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref_payment_1', 'orig_ref...', 'description ...', action)
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.seq = 0
    request_json = json.dumps(request.get_json_data_dict(JSONFlag.NET))
    return request_json

@pytest.fixture(params=[
    (None, None, 'failure', True, 'parsing'),
    (0, 0, 'success', None, None),
    (0, 0, 'success', None, None),
    (10, 10, 'success', None, None),
    ])
def simple_response_json_error(request):
    seq, cmd_seq, status, protoerr, errcode =  request.param
    sender_addr = LibraAddress.encode_to_Libra_address(b'A'*16).encoded_address
    receiver_addr   = LibraAddress.encode_to_Libra_address(b'B'*16).encoded_address
    resp = CommandResponseObject()
    resp.status = status
    resp.seq = seq
    resp.command_seq = cmd_seq
    if status == 'failure':
        resp.error = OffChainError(protoerr, errcode)
    json_obj = json.dumps(resp.get_json_data_dict(JSONFlag.NET))
    return json_obj

def test_vasp_simple(info_context, simple_request_json):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, info_context)
    vc.process_request(AddrOther, simple_request_json)
    responses = vc.collect_messages()
    assert len(responses) == 2
    assert responses[0].type is CommandRequestObject
    assert responses[1].type is CommandResponseObject
    assert 'success' in responses[1].content

def test_vasp_simple_wrong_VASP(info_context, simple_request_json):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'X'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, info_context)
    vc.process_request(AddrOther, simple_request_json)
    responses = vc.collect_messages()
    assert len(responses) == 1
    assert responses[0].type is CommandResponseObject
    assert 'failure' in responses[0].content


def test_vasp_response(info_context, simple_response_json_error):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, info_context)
    vc.process_response(AddrOther, simple_response_json_error)

from unittest.mock import patch

def test_vasp_simple_interrupt(info_context, simple_request_json):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)

    # Patch business context to first return an exception
    vc = sample_vasp(AddrThis, info_context)
    with patch.object(vc.bc, 'ready_for_settlement', side_effect = [ BusinessAsyncInterupt(1234) ]) as mock_thing:
        assert vc.bc.ready_for_settlement == mock_thing
        vc.process_request(AddrOther, simple_request_json)
        responses = vc.collect_messages()

    assert len(responses) == 2
    assert responses[0].type is CommandRequestObject
    assert responses[1].type is CommandResponseObject
    assert 'success' in responses[1].content

    with patch.object(vc.bc, 'ready_for_settlement', return_value = True ) as mock_thing:
        assert vc.bc.ready_for_settlement == mock_thing
        vc.vasp.processor.notify_callback(1234)
        responses = vc.collect_messages()

    assert len(responses) > 0
    assert 'ready_for' in str(responses[0].content)
