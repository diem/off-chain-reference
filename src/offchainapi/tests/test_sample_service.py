from ..sample_service import *
from ..payment_logic import PaymentProcessor
from ..payment import *
from ..libra_address import LibraAddress
from ..utils import *
from ..protocol_messages import *
from ..business import VASPInfo

from unittest.mock import MagicMock
import pytest



def test_business_simple():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
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

    with proc.storage_factory as _:
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

    with proc.storage_factory as _:
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






def test_vasp_simple(simple_request_json, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, asset_path)
    vc.process_request(AddrOther, simple_request_json)
    responses = vc.collect_messages()
    assert len(responses) == 2
    assert responses[0].type is CommandRequestObject
    assert responses[1].type is CommandResponseObject
    assert 'success' in responses[1].content

def test_vasp_simple_wrong_VASP(simple_request_json, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'X'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, asset_path)
    vc.process_request(AddrOther, simple_request_json)
    responses = vc.collect_messages()
    assert len(responses) == 1
    assert responses[0].type is CommandResponseObject
    assert 'failure' in responses[0].content


def test_vasp_response(simple_response_json_error, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)
    vc = sample_vasp(AddrThis, asset_path)
    vc.process_response(AddrOther, simple_response_json_error)

from unittest.mock import patch

def test_vasp_simple_interrupt(simple_request_json, asset_path):
    AddrThis   = LibraAddress.encode_to_Libra_address(b'B'*16)
    AddrOther = LibraAddress.encode_to_Libra_address(b'A'*16)

    # Patch business context to first return an exception
    vc = sample_vasp(AddrThis, asset_path)
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
