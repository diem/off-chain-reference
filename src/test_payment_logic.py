from payment_logic import *
from payment import *

from unittest.mock import MagicMock
import pytest


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

def test_payment_create_from_sender(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect=[ True ]

    diff = basic_payment.get_full_record()
    new_payment = check_new_payment(bcm, diff)
    assert new_payment == basic_payment

def test_payment_create_from_sender_sig_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect=[ True ]
    bcm.validate_recipient_signature.side_effect = [ BusinessValidationFailure('Sig fails') ]

    diff = basic_payment.get_full_record()
    with pytest.raises(BusinessValidationFailure):
        new_payment = check_new_payment(bcm, diff)
        assert new_payment == basic_payment

def test_payment_create_from_sender(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect=[ False ]

    diff = basic_payment.get_full_record()
    new_payment = check_new_payment(bcm, diff)
    assert new_payment == basic_payment

def test_payment_create_from_sender_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect=[ True ]

    basic_payment.data['receiver'].update({ 'status': Status.ready_for_settlement})
    diff = basic_payment.get_full_record()
    with pytest.raises(PaymentLogicError):
        _ = check_new_payment(bcm, diff)

def test_payment_create_from_receiver_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect=[ False ]

    basic_payment.data['sender'].update({ 'status': Status.ready_for_settlement})
    basic_payment.data['receiver'].update({ 'status': Status.ready_for_settlement})
    diff = basic_payment.get_full_record()
    with pytest.raises(PaymentLogicError):
        _ = check_new_payment(bcm, diff)

def test_payment_process_receiver_new_payment(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect=[ True, True ]
    bcm.check_account_existence.side_effect=[ None ]
    bcm.next_kyc_level_to_request.side_effect=[ Status.needs_kyc_data ]
    bcm.next_kyc_to_provide.side_effect = [ { Status.none } ]
    bcm.ready_for_settlement.side_effect = [ False ]

    assert basic_payment.data['receiver'].data['status'] == Status.none
    new_payment = payment_process(bcm, basic_payment)

    assert new_payment.data['receiver'].data['status'] == Status.needs_kyc_data

    new_payment.data['receiver'].data['status'] == Status.ready_for_settlement
    bcm.is_recipient.side_effect=[ True, True ]
    bcm.check_account_existence.side_effect=[ None ]
    bcm.next_kyc_level_to_request.side_effect=[ Status.none ]
    bcm.next_kyc_to_provide.side_effect = [ { Status.none } ]
    bcm.ready_for_settlement.side_effect = [ True ]
    bcm.want_single_payment_settlement.side_effect = [ True ]
    bcm.has_settled.side_effect = [ False ]

    new_payment2 = payment_process(bcm, new_payment)
    assert new_payment2.data['receiver'].data['status'] == Status.ready_for_settlement

    bcm.is_recipient.side_effect=[ True, True ]
    bcm.check_account_existence.side_effect=[ None ]
    bcm.next_kyc_level_to_request.side_effect=[ Status.none ]
    bcm.next_kyc_to_provide.side_effect = [ { Status.none } ]
    bcm.ready_for_settlement.side_effect = [ True ]
    bcm.want_single_payment_settlement.side_effect = [ True ]
    bcm.has_settled.side_effect = [ True ]

    new_payment3 = payment_process(bcm, new_payment2)
    assert new_payment3.data['receiver'].data['status'] == Status.settled
