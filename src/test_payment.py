import pytest

from payment import *
from decimal import Decimal

def test_payment_action_creation():
    action = PaymentAction(Decimal('10.00'), 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Try negative payment, should fail
        _ = PaymentAction(Decimal('-10.00'), 'LBT', 'charge', '2020-01-01 19:00 UTC')

with pytest.raises(StructureException):
    # Try zero payment, should fail
    _ = PaymentAction(Decimal('0.0'), 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use floating point for value
        _ = PaymentAction(0.01, 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use int for currency
        _ = PaymentAction(Decimal('10.00'), 5, 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use wrong type for action
        _ = PaymentAction(Decimal('10.00'), 'LBT', 0, '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use wrong type for timestamp
        _ = PaymentAction(Decimal('10.00'), 'LBT', 'charge', 0)

def test_payment_actor_creation():
    actor = PaymentActor('ABCD', 'XYZ', 'none', [])

    with pytest.raises(StructureException):
        # Bad address type
        _ = PaymentActor(0, 'XYZ', 'none', [])

    with pytest.raises(StructureException):
        # Bad subaddress type
        _ = PaymentActor('ABCD', 0, 'none', [])

    with pytest.raises(StructureException):
        # Bad status type
        _ = PaymentActor('ABCD', 'XYZ', 0, [])

    with pytest.raises(StructureException):
        # Bad metadata type
        _ = PaymentActor('ABCD', 'XYZ', 'none', 0)


def test_payment_actor_update_stable_id():
    actor = PaymentActor('ABCD', 'XYZ', 'none', [])
    actor.add_stable_id('AAAA')
    assert actor.data['stable_id'] == 'AAAA'

    with pytest.raises(StructureException):
        # Cannot add a new stable id
        actor.add_stable_id('BBBB')

    with pytest.raises(StructureException):
        # Wrong type of stable ID
        actor = PaymentActor('ABCD', 'XYZ', 'none', [])
        actor.add_stable_id(0)

def test_payment_actor_update_status():
    actor = PaymentActor('ABCD', 'XYZ', 'none', [])
    actor.change_status('need_kyc')
    actor.change_status('ready_to_settle')

    with pytest.raises(StructureException):
        actor.change_status(0)

def test_payment_actor_update_kyc():
    kyc = KYCData('KYCDATA')
    actor = PaymentActor('ABCD', 'XYZ', 'none', [])
    actor.add_kyc_data(kyc, 'sigXXXX', 'certXXX')

    with pytest.raises(StructureException):
        # Cannot change KYC data once set
        actor.add_kyc_data(kyc, 'sigXXXX', 'certXXX')

    with pytest.raises(StructureException):
        # Wrong type for kyc data
        actor = PaymentActor('ABCD', 'XYZ', 'none', [])
        actor.add_kyc_data(0, 'sigXXXX', 'certXXX')

    with pytest.raises(StructureException):
        # Wrong type for sig data
        actor = PaymentActor('ABCD', 'XYZ', 'none', [])
        actor.add_kyc_data(kyc, 0, 'certXXX')

    with pytest.raises(StructureException):
        # Wrong type for cert data
        actor = PaymentActor('ABCD', 'XYZ', 'none', [])
        actor.add_kyc_data(kyc, 'sigXXXX', 0)

def test_payment_object_creation():
    sender = PaymentActor('AAAA', 'aaaa', 'none', [])
    receiver = PaymentActor('BBBB', 'bbbb', 'none', [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')

    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

def test_payment_object_update():
    sender = PaymentActor('AAAA', 'aaaa', 'none', [])
    receiver = PaymentActor('BBBB', 'bbbb', 'none', [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')

    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    payment.add_recipient_signature('SIG')

    with pytest.raises(StructureException):
        payment.add_recipient_signature('SIG2')
