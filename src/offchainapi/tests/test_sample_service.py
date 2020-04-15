from ..sample_service import *
from ..payment_logic import PaymentProcessor
from ..payment import *
from ..libra_address import LibraAddress
from ..utils import *
from ..protocol_messages import *
from ..business import VASPInfo

from unittest.mock import MagicMock
import pytest
import asyncio

@pytest.fixture
def asset_path(request):
    from pathlib import Path
    asset_path = Path(request.fspath).resolve()
    asset_path = asset_path.parents[3] / 'test_vectors'
    return asset_path

@pytest.fixture
def basic_payment_as_receiver():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

@pytest.fixture
def kyc_payment_as_receiver():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
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
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(a0.as_str(), '1', Status.none, [])
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
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
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
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    bc = sample_business(a0)
    store = StorableFactory({})
    proc = PaymentProcessor(bc, store)
    proc.loop = asyncio.get_event_loop()
    return (a0, bc, proc)

def test_business_simple():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    bc = sample_business(a0)

def test_business_is_related(basic_payment_as_receiver, addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = basic_payment_as_receiver

    kyc_level = proc.loop.run_until_complete(bc.next_kyc_level_to_request(payment))
    assert kyc_level == Status.needs_kyc_data

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()
    assert ret_payment.data['receiver'].data['status'] == Status.needs_kyc_data

def test_business_is_kyc_provided(kyc_payment_as_receiver, addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = kyc_payment_as_receiver

    kyc_level = proc.loop.run_until_complete(bc.next_kyc_level_to_request(payment))
    assert kyc_level == Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = proc.loop.run_until_complete(bc.ready_for_settlement(ret_payment))
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.ready_for_settlement

def test_business_is_kyc_provided_sender(kyc_payment_as_sender, addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = kyc_payment_as_sender
    assert payment.data['sender'] is not None
    assert bc.is_sender(payment)
    kyc_level = proc.loop.run_until_complete(bc.next_kyc_level_to_request(payment))
    assert kyc_level == Status.needs_recipient_signature

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = proc.loop.run_until_complete(bc.ready_for_settlement(ret_payment))
    assert ready
    assert ret_payment.data['sender'].data['status'] == Status.ready_for_settlement
    assert bc.get_account('1')['balance'] == 5.0


def test_business_settled(settled_payment_as_receiver,addr_bc_proc):
    a0, bc, proc = addr_bc_proc
    payment = settled_payment_as_receiver

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = proc.loop.run_until_complete(bc.ready_for_settlement(ret_payment))
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.settled

    assert bc.get_account('1')['pending_transactions']['ref']['settled']
    assert bc.get_account('1')['balance'] == 15.0


@pytest.fixture
def simple_request_json():
    sender_addr = LibraAddress.encode_to_Libra_address(b'A'*16).encoded_address
    receiver_addr = LibraAddress.encode_to_Libra_address(b'B'*16).encoded_address
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

def test_vasp_simple(simple_request_json, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, asset_path)
    vc.pp.start_processor()

    vc.process_request(AddrOther, simple_request_json)
    responses = vc.collect_messages()
    assert len(responses) == 1
    assert responses[0].type is CommandResponseObject
    assert 'success' in responses[0].content
    assert len(vc.pp.futs) == 1

    # Testing the threading / Async interface works
    try:
        for fut in vc.pp.futs:
            fut.result()
        requests = vc.collect_messages()
        assert len(requests) == 1
        assert requests[0].type is CommandRequestObject
    finally:
        vc.pp.stop_processor()


def test_vasp_simple_wrong_VASP(simple_request_json, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'X'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, asset_path)
    try:
        vc.pp.start_processor()

        vc.process_request(AddrOther, simple_request_json)
        responses = vc.collect_messages()
        assert len(responses) == 1
        assert responses[0].type is CommandResponseObject
        assert 'failure' in responses[0].content
    finally:
        vc.pp.stop_processor()

def test_vasp_response(simple_response_json_error, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, asset_path)
    vc.process_response(AddrOther, simple_response_json_error)

from unittest.mock import patch

def test_sample_vasp_info_is_authorised(request, asset_path):
    from pathlib import Path
    cert_file = Path(request.fspath).resolve()
    cert_file = cert_file.parents[3] / 'test_vectors' / 'client_cert.pem'
    cert_file = cert_file.resolve()
    with open(cert_file, 'rt') as f:
        cert_str = f.read()
    cert = OpenSSL.crypto.load_certificate(
        OpenSSL.crypto.FILETYPE_PEM, cert_str
    )
    my_addr   = LibraAddress.encode_to_Libra_address(b'B'*16)
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(my_addr, asset_path)
    assert vc.info_context.is_authorised_VASP(cert, other_addr)
