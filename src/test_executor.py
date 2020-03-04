from executor import *
from payment import *
from payment_logic import PaymentCommand

import pytest


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment




def test_exec(basic_payment):
    pe = ProtocolExecutor()
    cmd1 = PaymentCommand(basic_payment)

    pay2 = basic_payment.new_version()
    pay2.data['sender'].change_status(Status.maybe_needs_kyc)
    cmd2 = PaymentCommand(pay2)

    pay3 = pay2.new_version()
    pay3.data['sender'].change_status(Status.needs_stable_id)
    cmd3 = PaymentCommand(pay3)

    pe.sequence_next_command(cmd1)
    pe.sequence_next_command(cmd2)
    pe.sequence_next_command(cmd3)

    assert pe.count_potentially_live() == 3

    # Diverge -- branch A

    pay4a = pay3.new_version()
    pay4a.data['sender'].change_status(Status.ready_for_settlement)
    cmd4a = PaymentCommand(pay4a)

    pay5a = pay4a.new_version()
    pay5a.data['sender'].change_status(Status.settled)
    cmd5a = PaymentCommand(pay5a)

    pe.sequence_next_command(cmd4a)
    pe.sequence_next_command(cmd5a)

    # Diverge -- branch B

    pay4b = pay3.new_version()
    pay4b.data['sender'].change_status(Status.needs_kyc_data)
    cmd4b = PaymentCommand(pay4b)

    pay5b = pay4b.new_version()
    pay5b.data['sender'].change_status(Status.abort)
    cmd5b = PaymentCommand(pay5b)

    pe.sequence_next_command(cmd4b)
    pe.sequence_next_command(cmd5b)

    assert pe.count_potentially_live() == 7

    pe.set_success(0)
    pe.set_success(1)
    pe.set_success(2)
    assert pe.count_potentially_live() == 5
    assert pe.count_actually_live() == 1

    pe.set_success(3)
    pe.set_success(4)

    assert pe.count_potentially_live() == 3
    assert pe.count_actually_live() == 1

    pe.set_fail(5)
    pe.set_fail(6)

    assert pe.count_potentially_live() == 1
    assert pe.count_actually_live() == 1

    pay6 = pay5a.new_version()
    pay6.data['sender'].change_status(Status.abort)
    cmd6 = PaymentCommand(pay6)

    pe.sequence_next_command(cmd6)
