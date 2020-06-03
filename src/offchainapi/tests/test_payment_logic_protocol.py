# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0


from ..asyncnet import Aionet
from ..storage import StorableFactory
from ..libra_address import LibraAddress
from ..payment_logic import PaymentProcessor, PaymentCommand

from .basic_business_context import TestBusinessContext

from mock import AsyncMock

def test_logic_protocol(payment, loop):
    # Test the protocol given a sequence of commands.

    store = StorableFactory({})

    my_addr = LibraAddress.encode(b'B'*16)
    other_addr = LibraAddress.encode(b'A'*16)
    bcm = TestBusinessContext(my_addr)
    processor = PaymentProcessor(bcm, store, loop)

    net = AsyncMock(Aionet)
    processor.set_network(net)

    cmd = PaymentCommand(payment)
    cmd.set_origin(other_addr)
