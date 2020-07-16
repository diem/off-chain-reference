# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..payment import PaymentActor, PaymentAction, PaymentObject, KYCData
from ..business import BusinessContext, VASPInfo
from ..storage import StorableFactory
from ..payment_logic import Status, PaymentProcessor, PaymentCommand
from ..protocol import OffChainVASP, VASPPairChannel
from ..executor import ProtocolExecutor
from ..command_processor import CommandProcessor
from ..libra_address2 import LibraAddress
from ..protocol_messages import CommandRequestObject
from ..utils import JSONFlag
from ..crypto import ComplianceKey

import types
import dbm
from copy import deepcopy
from unittest.mock import MagicMock
from mock import AsyncMock
import pytest
import json


@pytest.fixture
def three_addresses():
    a0 = LibraAddress.from_bytes(b'A'*16)
    a1 = LibraAddress.from_bytes(b'B' + b'A'*15)
    a2 = LibraAddress.from_bytes(b'B'*16)
    return (a0, a1, a2)


@pytest.fixture
def sender_actor():
    s_addr = LibraAddress.from_bytes(b'A'*16, b'a'*8).as_str()
    return PaymentActor(s_addr, Status.none, [])


@pytest.fixture
def receiver_actor():
    s_addr = LibraAddress.from_bytes(b'B'*16, b'b'*8).as_str()
    return PaymentActor(s_addr, Status.none, [])


@pytest.fixture
def payment_action():
    return PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')


@pytest.fixture
def payment(sender_actor, receiver_actor, payment_action):
    return PaymentObject(
        sender_actor, receiver_actor, '_ref', 'orig_ref', 'desc', payment_action
    )


@pytest.fixture
def kyc_data():
    return KYCData({
        "payload_type": "KYC_DATA",
        "payload_version": 1,
        "type": "individual",
    })


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
def key():
    return ComplianceKey.generate()


@pytest.fixture
def vasp(three_addresses, store, key):
    a0, _, _ = three_addresses
    command_processor = MagicMock(spec=CommandProcessor)
    info_context = MagicMock(spec=VASPInfo)
    info_context.get_peer_compliance_verification_key.return_value = key
    info_context.get_peer_compliance_signature_key.return_value = key
    return OffChainVASP(a0, command_processor, store, info_context)


@pytest.fixture
def channel(three_addresses, vasp, store):
    a0, a1, _ = three_addresses
    command_processor = MagicMock(spec=CommandProcessor)
    return VASPPairChannel(a1, a0, vasp, store, command_processor)


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


@pytest.fixture
def command(payment_action):
    sender = PaymentActor('C', Status.none, [])
    receiver = PaymentActor('1', Status.none, [])
    payment = PaymentObject(
        sender, receiver, 'XYZ_ABC', 'orig_ref', 'desc', payment_action
    )
    return PaymentCommand(payment)


@pytest.fixture
def json_request(command):
    request = CommandRequestObject(command)
    request.seq = 0
    request.command_seq = 0
    return request.get_json_data_dict(JSONFlag.NET)


@pytest.fixture
def json_response():
    return {"seq": 0, "command_seq": 0, "status": "success"}


@pytest.fixture
def signed_json_request(json_request, key):
    return key.sign_message(json.dumps(json_request))

@pytest.fixture
def signed_json_response(json_response, key):
    return key.sign_message(json.dumps(json_response))
