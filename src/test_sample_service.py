from sample_service import *
from test_protocol import FakeAddress, FakeVASPInfo
from payment_logic import PaymentProcessor
from payment import *

import pytest

@pytest.fixture
def basic_payment_as_receiver():
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(str(40), '1', Status.none, [])
    action = PaymentAction(Decimal('5.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

@pytest.fixture
def kyc_payment_as_receiver():
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(str(40), '1', Status.none, [])
    action = PaymentAction(Decimal('5.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
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
    action = PaymentAction(Decimal('5.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
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
    action = PaymentAction(Decimal('5.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
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



def test_business_simple():
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

def test_business_is_related(basic_payment_as_receiver):
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

    proc = PaymentProcessor(bc)
    payment = basic_payment_as_receiver

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level != Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()
    assert ret_payment.data['receiver'].data['status'] == Status.needs_kyc_data

def test_business_is_kyc_provided(kyc_payment_as_receiver):
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

    proc = PaymentProcessor(bc)
    payment = kyc_payment_as_receiver
    
    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = bc.ready_for_settlement(ret_payment)
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.ready_for_settlement

def test_business_is_kyc_provided_sender(kyc_payment_as_sender):
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

    proc = PaymentProcessor(bc)
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


def test_business_settled(settled_payment_as_receiver):
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

    proc = PaymentProcessor(bc)
    payment = settled_payment_as_receiver

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = bc.ready_for_settlement(ret_payment)
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.settled

    assert bc.get_account('1')['pending_transactions']['ref']['settled']
    assert bc.get_account('1')['balance'] == 15.0
   

def test_vasp_simple():
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    vc = sample_vasp(a0)
