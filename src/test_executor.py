from protocol import *
from executor import *
from payment import *
from payment_logic import PaymentCommand
from business import BusinessContext

from unittest.mock import MagicMock
import pytest


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment


def test_exec(basic_payment):
    channel = MagicMock(spec=VASPPairChannel)
    bcm = MagicMock(spec=BusinessContext)
    proc = MagicMock(spec=CommandProcessor)
    pe = ProtocolExecutor(channel, proc)


    cmd1 = PaymentCommand(basic_payment)
    cmd1.set_origin(channel.get_my_address())
    assert cmd1.get_origin() == channel.get_my_address()

    pay2 = basic_payment.new_version()
    pay2.data['sender'].change_status(Status.needs_stable_id)
    cmd2 = PaymentCommand(pay2)
    cmd2.set_origin(channel.get_my_address())

    pay3 = pay2.new_version()
    pay3.data['sender'].change_status(Status.needs_stable_id)
    cmd3 = PaymentCommand(pay3)
    cmd3.set_origin(channel.get_my_address())

    assert cmd1.dependencies == []
    assert cmd2.dependencies == cmd1.creates_versions
    assert cmd3.dependencies == cmd2.creates_versions

    pe.sequence_next_command(cmd1)
    pe.sequence_next_command(cmd2)
    pe.sequence_next_command(cmd3)

    assert pe.count_potentially_live() == 3

    # Diverge -- branch A

    pay4a = pay3.new_version()
    pay4a.data['sender'].change_status(Status.ready_for_settlement)
    cmd4a = PaymentCommand(pay4a)
    cmd4a.set_origin(channel.get_my_address())

    pay5a = pay4a.new_version()
    pay5a.data['sender'].change_status(Status.settled)
    cmd5a = PaymentCommand(pay5a)
    cmd5a.set_origin(channel.get_my_address())


    pe.sequence_next_command(cmd4a)
    pe.sequence_next_command(cmd5a)

    # Diverge -- branch B

    pay4b = pay3.new_version()
    pay4b.data['sender'].change_status(Status.needs_kyc_data)
    cmd4b = PaymentCommand(pay4b)
    cmd4b.set_origin(channel.get_my_address())

    pay5b = pay4b.new_version()
    pay5b.data['sender'].change_status(Status.abort)
    cmd5b = PaymentCommand(pay5b)
    cmd5b.set_origin(channel.get_my_address())

    pe.sequence_next_command(cmd4b)
    pe.sequence_next_command(cmd5b)

    assert pe.count_potentially_live() == 7

    # Try to sequence a really bad command
    pay_bad = pay4b.new_version()
    pay_bad.data['sender'].change_status(Status.abort)
    cmd_bad = PaymentCommand(pay_bad)
    cmd_bad.command['action'] = {'amount':  1000000}
    cmd_bad.set_origin(channel.get_my_address())
    with pytest.raises(ExecutorException):
        pe.sequence_next_command(cmd_bad, do_not_sequence_errors=True)

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

def test_handlers(basic_payment):
    channel = MagicMock(spec=VASPPairChannel)
    bcm = MagicMock(spec=BusinessContext)
    proc = MagicMock(spec=CommandProcessor)
    
    class Stats(CommandProcessor):
        def __init__(self, bc):
            self.success_no = 0
            self.failure_no = 0
            self.bc = bc
        
        def business_context(self):
            return self.bc

        def process_command(self, vasp, channel, executor, command, status, error=None):
            if status:
                self.success_no += 1
            else:
                self.failure_no += 1

    stat = Stats(bcm)
    pe = ProtocolExecutor(channel, stat)

    cmd1 = PaymentCommand(basic_payment)
    cmd1.set_origin(channel.get_my_address())

    pay2 = basic_payment.new_version()
    pay2.data['sender'].change_status(Status.needs_stable_id)
    cmd2 = PaymentCommand(pay2)
    cmd2.set_origin(channel.get_my_address())


    pay3 = basic_payment.new_version()
    pay3.data['sender'].change_status(Status.needs_stable_id)
    cmd3 = PaymentCommand(pay3)
    cmd3.set_origin(channel.get_my_address())

    assert cmd1.dependencies == []
    assert cmd2.dependencies == list(cmd1.creates_versions)
    assert cmd3.dependencies == list(cmd1.creates_versions)

    pe.sequence_next_command(cmd1)
    pe.sequence_next_command(cmd2)
    pe.sequence_next_command(cmd3)
    pe.set_success(0)
    pe.set_success(1)
    pe.set_fail(2)

    assert stat.success_no == 2
    assert stat.failure_no == 1
