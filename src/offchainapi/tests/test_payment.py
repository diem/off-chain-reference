from ..payment import *
from ..utils import JSONFlag

import json
import pytest


def test_json_payment(payment):
    data = json.dumps(payment.get_json_data_dict(flag=JSONFlag.STORE))
    pay2 = PaymentObject.from_json_data_dict(json.loads(data), flag=JSONFlag.STORE)
    assert payment == pay2


def test_json_payment_flags(payment):
    payment.actually_live = False
    payment.potentially_live = True
    data = json.dumps(payment.get_json_data_dict(flag=JSONFlag.STORE))
    pay2 = PaymentObject.from_json_data_dict(json.loads(data), flag=JSONFlag.STORE)
    assert pay2.potentially_live and not pay2.actually_live

    payment.actually_live = True
    payment.potentially_live = False
    data = json.dumps(payment.get_json_data_dict(flag=JSONFlag.STORE))
    pay2 = PaymentObject.from_json_data_dict(json.loads(data), flag=JSONFlag.STORE)
    assert not pay2.potentially_live and pay2.actually_live

    assert payment.version == pay2.version
    assert payment.version is not None


def test_kyc_data_missing_payment_reference_fail():
    with pytest.raises(StructureException):
        kyc_data = KYCData('{"type": "A"}')


def test_kyc_data_missing_type_fail():
    with pytest.raises(StructureException):
        kyc_data = KYCData('{"payment_reference_id": "1234"}')


def test_payment_action_creation():
    action = PaymentAction(10, 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Try negative payment, should fail
        _ = PaymentAction(-10, 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Try zero payment, should fail
        _ = PaymentAction(0, 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use floating point for value
        _ = PaymentAction(0.01, 'LBT', 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use int for currency
        _ = PaymentAction(10, 5, 'charge', '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use wrong type for action
        _ = PaymentAction(10, 'LBT', 0, '2020-01-01 19:00 UTC')

    with pytest.raises(StructureException):
        # Use wrong type for timestamp
        _ = PaymentAction(10, 'LBT', 'charge', 0)


def test_payment_actor_creation():
    actor = PaymentActor('ABCD', 'XYZ', Status.none, [])

    with pytest.raises(StructureException):
        # Bad address type
        _ = PaymentActor(0, 'XYZ', Status.none, [])

    with pytest.raises(StructureException):
        # Bad subaddress type
        _ = PaymentActor('ABCD', 0, Status.none, [])

    with pytest.raises(StructureException):
        # Bad status type
        _ = PaymentActor('ABCD', 'XYZ', 0, [])

    with pytest.raises(StructureException):
        # Bad metadata type
        _ = PaymentActor('ABCD', 'XYZ', Status.none, 0)


def test_payment_actor_update_stable_id(sender_actor):
    sender_actor.add_stable_id('AAAA')
    assert sender_actor.data['stable_id'] == 'AAAA'

    with pytest.raises(StructureException):
        # Cannot add a new stable id
        sender_actor.add_stable_id('BBBB')

    with pytest.raises(StructureException):
        # Wrong type of stable ID
        sender_actor.add_stable_id(0)


def test_payment_actor_update_status(sender_actor):
    sender_actor.change_status(Status.needs_kyc_data)
    sender_actor.change_status(Status.ready_for_settlement)

    with pytest.raises(StructureException):
        sender_actor.change_status(0)


def test_payment_actor_update_kyc(sender_actor, kyc_data):
    sender_actor.add_kyc_data(kyc_data, 'sigXXXX', 'certXXX')

    # We tolerate writing again strictly the same record
    sender_actor.add_kyc_data(kyc_data, 'sigXXXX', 'certXXX')

    with pytest.raises(StructureException):
        # Cannot change KYC data once set
        sender_actor.add_kyc_data(kyc_data, 'sigYYYY', 'certYYYY')

    with pytest.raises(StructureException):
        # Wrong type for kyc data
        sender_actor.add_kyc_data(0, 'sigXXXX', 'certXXX')

    with pytest.raises(StructureException):
        # Wrong type for sig data
        sender_actor.add_kyc_data(kyc_data, 0, 'certXXX')

    with pytest.raises(StructureException):
        # Wrong type for cert data
        sender_actor.add_kyc_data(kyc_data, 'sigXXXX', 0)


def test_payment_object_creation(sender_actor, receiver_actor, payment_action):
    payment = PaymentObject(
        sender_actor, receiver_actor, 'ref', 'orig_ref', 'desc', payment_action
    )


def test_payment_object_update(payment):
    payment.add_recipient_signature('SIG')
    with pytest.raises(StructureException):
        payment.add_recipient_signature('SIG2')


def test_payment_to_diff(payment, sender_actor, receiver_actor, payment_action):
    record = payment.get_full_diff_record()
    new_payment = PaymentObject.create_from_record(record)
    assert payment == new_payment

    payment2 = PaymentObject(
        sender_actor, receiver_actor, 'ref2', 'orig_ref', 'desc', payment_action
    )
    assert payment2 != new_payment


def test_to_json(kyc_data, sender_actor, receiver_actor, payment_action):
    sender_actor.add_kyc_data(kyc_data, "sigSENDER", 'certSENDER')
    receiver_actor.add_kyc_data(kyc_data, "sigSENDER", 'certSENDER')
    payment = PaymentObject(
        sender_actor, receiver_actor, 'ref2', 'orig_ref', 'desc', payment_action
    )

    json_payment = json.dumps(payment.get_full_diff_record())
    new_payment = PaymentObject.create_from_record(json.loads(json_payment))
    assert payment == new_payment


def test_payment_actor_update_bad_kyc_fails(sender_actor):
    diff = {'kyc_data': '1234'}
    with pytest.raises(StructureException):
        sender_actor.custom_update_checks(diff)

    diff = {'kyc_data': '1234', 'kyc_signature': '1234'}
    with pytest.raises(StructureException):
        sender_actor.custom_update_checks(diff)

    diff = {'kyc_certificate': '1234', 'kyc_signature': '1234'}
    with pytest.raises(StructureException):
        sender_actor.custom_update_checks(diff)


def test_payment_actor_update_bad_status_fails(sender_actor):
    diff = {'status': 'wrong_status'}
    with pytest.raises(StructureException):
        sender_actor.custom_update_checks(diff)


def test_payment_actor_update_bad_metadata_fails(sender_actor):
    diff = {'metadata': [1234]}
    with pytest.raises(StructureException):
        sender_actor.custom_update_checks(diff)


def test_payment_actor_add_metadata(sender_actor):
    sender_actor.add_metadata('abcd')
    assert sender_actor.data['metadata'] == ['abcd']
