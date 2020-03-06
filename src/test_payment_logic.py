from payment_logic import *
from payment import *
from protocol_messages import *
from protocol import *
from business import BusinessAsyncInterupt
from utils import *

from unittest.mock import MagicMock
import pytest

@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

def test_payment_command_serialization_net(basic_payment):
    cmd = PaymentCommand(basic_payment)
    data = cmd.get_json_data_dict(JSON_NET)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSON_NET)
    assert cmd == cmd2

def test_payment_command_serialization_store(basic_payment):
    cmd = PaymentCommand(basic_payment)
    data = cmd.get_json_data_dict(JSON_STORE)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSON_STORE)
    assert cmd == cmd2

def test_payment_end_to_end_serialization(basic_payment):
    # Define a full request/reply with a Payment and test serialization
    CommandRequestObject.register_command_type(PaymentCommand)

    cmd = PaymentCommand(basic_payment)
    request = CommandRequestObject(cmd)
    request.seq = 10
    request.response = make_success_response(request)
    data = request.get_json_data_dict(JSON_STORE)
    request2 = CommandRequestObject.from_json_data_dict(data, JSON_STORE)
    assert request == request2

# ----- check_new_payment -----

def test_payment_create_from_recipient(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [True]

    diff = basic_payment.get_full_record()
    new_payment = check_new_payment(bcm, diff)
    assert new_payment == basic_payment


def test_payment_create_from_sender_sig_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [True]
    bcm.validate_recipient_signature.side_effect = [BusinessValidationFailure('Sig fails')]

    diff = basic_payment.get_full_record()
    with pytest.raises(BusinessValidationFailure):
        new_payment = check_new_payment(bcm, diff)
        assert new_payment == basic_payment


def test_payment_create_from_sender(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [False]

    diff = basic_payment.get_full_record()
    new_payment = check_new_payment(bcm, diff)
    assert new_payment == basic_payment


def test_payment_create_from_sender_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [True]

    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    diff = basic_payment.get_full_record()
    with pytest.raises(PaymentLogicError):
        _ = check_new_payment(bcm, diff)


def test_payment_create_from_receiver_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [False]

    basic_payment.data['sender'].update({'status': Status.ready_for_settlement})
    basic_payment.data['receiver'].update({'status': Status.ready_for_settlement})
    diff = basic_payment.get_full_record()
    with pytest.raises(PaymentLogicError):
        _ = check_new_payment(bcm, diff)


# ----- check_new_update -----


def test_payment_update_from_sender_modify_receiver_fail(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [False]
    diff = {}
    new_payment = check_new_update(bcm, basic_payment, diff)
    assert new_payment == basic_payment


# ----- payment_process -----


def test_payment_process_receiver_new_payment(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.needs_kyc_data]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [False]

    assert basic_payment.data['receiver'].data['status'] == Status.none
    pp = PaymentProcessor(bcm)
    new_payment = pp.payment_process(basic_payment)

    assert new_payment.data['receiver'].data['status'] == Status.needs_kyc_data

    new_payment.data['receiver'].data['status'] == Status.ready_for_settlement
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [True]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [False]

    pp = PaymentProcessor(bcm)
    new_payment2 = pp.payment_process(new_payment)
    assert new_payment2.data['receiver'].data['status'] == Status.ready_for_settlement

    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [Status.none]
    bcm.next_kyc_to_provide.side_effect = [{Status.none}]
    bcm.ready_for_settlement.side_effect = [True]
    bcm.want_single_payment_settlement.side_effect = [True]
    bcm.has_settled.side_effect = [True]

    pp = PaymentProcessor(bcm)
    new_payment3 = pp.payment_process(new_payment2)
    assert new_payment3.data['receiver'].data['status'] == Status.settled


def test_payment_process_interrupt(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessAsyncInterupt(1234)]
    
    pp = PaymentProcessor(bcm)
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['status'] == Status.none


def test_payment_process_abort(basic_payment):
    bcm = MagicMock(spec=BusinessContext)
    bcm.is_recipient.side_effect = [True, True]
    bcm.check_account_existence.side_effect = [None]
    bcm.next_kyc_level_to_request.side_effect = [BusinessForceAbort]

    pp = PaymentProcessor(bcm)
    new_payment = pp.payment_process(basic_payment)
    assert new_payment.data['receiver'].data['status'] == Status.abort
