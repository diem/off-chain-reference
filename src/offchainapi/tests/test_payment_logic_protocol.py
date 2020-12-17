# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..asyncnet import Aionet
from ..storage import StorableFactory
from ..libra_address import LibraAddress
from ..payment_logic import PaymentProcessor, PaymentCommand
from ..payment import PaymentAction, PaymentActor, PaymentObject, StatusObject
from ..status_logic import Status

from .basic_business_context import TestBusinessContext

from mock import AsyncMock
import pytest
import asyncio

@pytest.fixture
def payment_sender_init():
    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)

    action = PaymentAction(5, 'TIK', 'charge', 887355)

    s_addr = LibraAddress.from_bytes("dm", b'A'*16, b'a'*8).as_str()
    sender = PaymentActor(s_addr, StatusObject(Status.needs_kyc_data), [])
    r_addr = LibraAddress.from_bytes("dm", b'B'*16, b'b'*8).as_str()
    receiver = PaymentActor(r_addr, StatusObject(Status.none), [])

    ref = f'{other_addr.as_str()}_XGGXHSHHSJ'

    payment = PaymentObject(sender, receiver, ref, None, None, action)
    return payment

def test_logic_protocol_check(payment_sender_init, loop, db):
    # Test the protocol given a sequence of commands.

    store = StorableFactory(db)

    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)
    bcm = TestBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment_sender_init)
    cmd.set_origin(other_addr)

    processor.check_command(my_addr, other_addr, cmd)


def test_logic_protocol_process_start(payment_sender_init, loop, db):
    # Test the protocol given a sequence of commands.

    store = StorableFactory(db)

    my_addr = LibraAddress.from_bytes("dm", b'B'*16)
    other_addr = LibraAddress.from_bytes("dm", b'A'*16)
    bcm = TestBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment_sender_init)
    cmd.set_origin(other_addr)

    processor.process_command(other_addr, cmd, cid=0, status_success=True)

    # Ensure an obligration is scheduled
    assert len(asyncio.all_tasks(loop)) == 1

    # Get the response command
    assert len(net.method_calls) == 0

    _ = loop.run_until_complete(asyncio.all_tasks(loop).pop())
    assert len(net.method_calls) > 0

    assert net.method_calls[0][0] == 'sequence_command'
    cmd_response = net.method_calls[0].args[1]
    assert isinstance(cmd_response, PaymentCommand)
