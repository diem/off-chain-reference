from sample_service import *
from test_protocol import FakeAddress, FakeVASPInfo
from payment_logic import PaymentProcessor
from payment import *

def test_business_simple():
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

def test_business_is_related():
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

    proc = PaymentProcessor(bc)

    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(str(40), '1', Status.none, [])
    action = PaymentAction(Decimal('5.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level != Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()
    assert ret_payment.data['receiver'].data['status'] == Status.needs_kyc_data

def test_business_is_kyc_provided():
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    bc = sample_business(a0)

    proc = PaymentProcessor(bc)

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

    kyc_level = bc.next_kyc_level_to_request(payment)
    assert kyc_level == Status.none

    ret_payment = proc.payment_process(payment)
    assert ret_payment.has_changed()

    ready = bc.ready_for_settlement(ret_payment)
    assert ready
    assert ret_payment.data['receiver'].data['status'] == Status.ready_for_settlement



def test_vasp_simple():
    a0 = FakeVASPInfo(FakeAddress(0, 10), FakeAddress(0, 40))
    vc = sample_vasp(a0)
