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

def xxtest_payment_creation(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.sure_is_retail_payment.side_effect=[ False, False ]
    bcm.check_actor_existence.side_effect=[True]
    bcm.last_chance_to_abort.side_effect=[True]
    bcm.want_single_payment_settlement.side_effect=[True]

    new_payment = sender_progress_payment(bcm, basic_payment)
    assert new_payment.data['sender'].data['status'] == Status.needs_stable_id

    # We do not add stable_ID unless the other side asks for it.
    assert len(new_payment.update_record) == 0
