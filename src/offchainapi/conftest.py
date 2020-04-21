from .payment import PaymentActor, PaymentAction, PaymentObject, KYCData
from .business import BusinessContext, VASPInfo
from .storage import StorableFactory
from .payment_logic import Status, PaymentProcessor
from .protocol import OffChainVASP, VASPPairChannel
from .executor import ProtocolExecutor
from .command_processor import CommandProcessor
from .libra_address import LibraAddress

import types
import json
import dbm
from copy import deepcopy
from unittest.mock import MagicMock, PropertyMock
from mock import AsyncMock
import pytest


@pytest.fixture
def three_addresses():
    a0 = LibraAddress.encode_to_Libra_address(b'A'*16)
    a1 = LibraAddress.encode_to_Libra_address(b'B' + b'A'*15)
    a2 = LibraAddress.encode_to_Libra_address(b'B'*16)
    return (a0, a1, a2)


@pytest.fixture
def sender_actor():
    return PaymentActor('AAAA', 'aaaa', Status.none, [])


@pytest.fixture
def receiver_actor():
    return PaymentActor('BBBB', 'bbbb', Status.none, [])


@pytest.fixture
def payment_action():
    return PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')


@pytest.fixture
def payment(sender_actor, receiver_actor, payment_action):
    return PaymentObject(
        sender_actor, receiver_actor, 'ref', 'orig_ref', 'desc', payment_action
    )


@pytest.fixture
def kyc_data():
    return KYCData("""{
        "payment_reference_id" : "PAYMENT_XYZ",
        "type" : "individual",
        "other_field" : "other data"
    }""")


@pytest.fixture
def store():
    return StorableFactory({})


@pytest.fixture
def processor(store):
    bcm = AsyncMock(spec=BusinessContext)
    return PaymentProcessor(bcm, store)


@pytest.fixture
def executor(three_addresses, store):
    a0, _, a1 = three_addresses
    channel = MagicMock(spec=VASPPairChannel)
    channel.get_my_address.return_value = a0
    channel.get_other_address.return_value = a1
    with store:
        channel.storage = store
        command_processor = MagicMock(spec=CommandProcessor)
        return ProtocolExecutor(channel, command_processor)


@pytest.fixture
def vasp(three_addresses, store):
    a0, _, _ = three_addresses
    command_processor = MagicMock(spec=CommandProcessor)
    info_context = MagicMock(spec=VASPInfo)
    return OffChainVASP(a0, command_processor, store, info_context)


@pytest.fixture
def two_channels(three_addresses, vasp, store):
    def monkey_tap(pair):
        pair.msg = []

        def to_tap(self, msg):
            assert msg is not None
            self.msg += [deepcopy(msg)]

        def tap(self):
            msg = self.msg
            self.msg = []
            return msg

        pair.tap = types.MethodType(tap, pair)
        pair.send_request = types.MethodType(to_tap, pair)
        pair.send_response = types.MethodType(to_tap, pair)
        return pair

    a0, a1, _ = three_addresses
    command_processor = MagicMock(spec=CommandProcessor)
    server = VASPPairChannel(
        a0, a1, vasp, store, command_processor
    )
    client = VASPPairChannel(
        a1, a0, vasp, store, command_processor
    )

    server, client = monkey_tap(server), monkey_tap(client)
    return (server, client)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / 'db.dat'
    with dbm.open(str(db_path), 'c') as xdb:
        yield xdb
