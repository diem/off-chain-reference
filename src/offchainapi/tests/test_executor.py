from ..executor import ProtocolExecutor, ExecutorException
from ..command_processor import CommandProcessor
from ..payment_logic import PaymentCommand, Status
from ..business import BusinessContext

from unittest.mock import MagicMock
import pytest


def test_handlers(payment, executor):
    _, channel, _ = executor.get_context()
    store = channel.storage
    bcm = MagicMock(spec=BusinessContext)

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

    cmd1 = PaymentCommand(payment)
    cmd1.set_origin(channel.get_my_address())

    pay2 = payment.new_version()
    pay2.sender.change_status(Status.needs_stable_id)
    cmd2 = PaymentCommand(pay2)
    cmd2.set_origin(channel.get_my_address())

    pay3 = payment.new_version()
    pay3.sender.change_status(Status.needs_stable_id)
    cmd3 = PaymentCommand(pay3)
    cmd3.set_origin(channel.get_my_address())

    assert cmd1.dependencies == []
    assert cmd2.dependencies == list(cmd1.creates_versions)
    assert cmd3.dependencies == list(cmd1.creates_versions)

    with store as tx_no:
        pe.sequence_next_command(cmd1)
        pe.sequence_next_command(cmd2)
        pe.sequence_next_command(cmd3)
        pe.set_success(0)
        pe.set_success(1)
        pe.set_fail(2)

    assert stat.success_no == 2
    assert stat.failure_no == 1
