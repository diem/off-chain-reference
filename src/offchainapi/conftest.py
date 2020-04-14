from .payment import PaymentActor, PaymentAction, PaymentObject, KYCData
from .payment_logic import Status
from .business import BusinessContext
from .storage import StorableFactory
from .payment_logic import PaymentProcessor, PaymentCommand
from .protocol import OffChainVASP, VASPPairChannel
from .executor import CommandProcessor
from .libra_address import LibraAddress
from .sample_service import sample_business
from .protocol_messages import CommandRequestObject, CommandResponseObject, OffChainError
from .utils import JSONFlag

import types
from copy import deepcopy
import json
import dbm
from unittest.mock import MagicMock, PropertyMock
import pytest


@pytest.fixture
def basic_actor():
    actor = PaymentActor('AAAA', 'aaaa', Status.none, [])
    return actor


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment


@pytest.fixture
def payment_processor_context():
    bcm = MagicMock(spec=BusinessContext)
    store = StorableFactory({})
    proc = PaymentProcessor(bcm, store)
    return (bcm, proc)


@pytest.fixture(params=[
    ('AAAA', 'BBBB', 'AAAA', True),
    ('BBBB', 'AAAA', 'AAAA', True),
    ('CCCC', 'AAAA', 'AAAA', False),
    ('BBBB', 'CCCC', 'AAAA', False),
    ('DDDD', 'CCCC', 'AAAA', False),
    ('AAAA', 'BBBB', 'BBBB', True),
    ('BBBB', 'AAAA', 'DDDD', False),
])
def states(request):
    return request.param


@pytest.fixture(params=[
    (None, None, 'failure', True, 'parsing'),
    (0, 0, 'success', None, None),
    (0, 0, 'success', None, None),
    (10, 10, 'success', None, None),
])
def simple_response_json_error(request):
    seq, cmd_seq, status, protoerr, errcode = request.param
    sender_addr = LibraAddress.encode_to_Libra_address(b'A'*16).encoded_address
    receiver_addr = LibraAddress.encode_to_Libra_address(b'B'*16).encoded_address
    resp = CommandResponseObject()
    resp.status = status
    resp.seq = seq
    resp.command_seq = cmd_seq
    if status == 'failure':
        resp.error = OffChainError(protoerr, errcode)
    json_obj = json.dumps(resp.get_json_data_dict(JSONFlag.NET))
    return json_obj


@pytest.fixture
def three_address():
    a0 = LibraAddress.encode_to_Libra_address(b'A'*16)
    a1 = LibraAddress.encode_to_Libra_address(b'B' + b'A'*15)
    a2 = LibraAddress.encode_to_Libra_address(b'B'*16)
    return (a0, a1, a2)


@pytest.fixture
def mockVASP():
    vasp = MagicMock(spec=OffChainVASP)
    vasp.info_context = PropertyMock(autospec=True)
    vasp.info_context.get_peer_base_url.return_value = '/'
    return vasp


@pytest.fixture
def mockProcessor():
    proc = MagicMock(spec=CommandProcessor)
    return proc


@pytest.fixture
def simple_request_json():
    sender_addr = LibraAddress.encode_to_Libra_address(b'A'*16).encoded_address
    receiver_addr = LibraAddress.encode_to_Libra_address(b'B'*16).encoded_address
    assert type(sender_addr) == str
    assert type(receiver_addr) == str

    sender = PaymentActor(sender_addr, 'C', Status.none, [])
    receiver = PaymentActor(receiver_addr, '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref_payment_1',
                            'orig_ref...', 'description ...', action)
    command = PaymentCommand(payment)
    request = CommandRequestObject(command)
    request.seq = 0
    request_json = json.dumps(request.get_json_data_dict(JSONFlag.NET))
    return request_json


@pytest.fixture
def network_client():
    network_client = MagicMock()
    network_client.get_url.return_value = '/'
    network_client.send_request.return_value = None
    return network_client


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


@pytest.fixture
def server_client(three_address, mockVASP, mockProcessor, network_client):
    a0, a1, _ = three_address

    store_server = StorableFactory({})
    server = VASPPairChannel(a0, a1, mockVASP, store_server, mockProcessor, network_client)
    store_client = StorableFactory({})
    client = VASPPairChannel(a1, a0, mockVASP, store_client, mockProcessor, network_client)

    server = monkey_tap(server)
    client = monkey_tap(client)

    return (server, client)


@pytest.fixture
def asset_path(request):
    from pathlib import Path
    asset_path = Path(request.fspath).resolve()
    asset_path = asset_path.parents[3] / 'test_vectors'
    return asset_path


@pytest.fixture
def basic_payment_as_receiver():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment


@pytest.fixture
def kyc_payment_as_receiver():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Charlie"
    }
    """

    kycA = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Alice"
    }
    """

    payment.data['sender'].add_kyc_data(KYCData(kyc), 'KYC_SIG', 'CERT')
    payment.data['receiver'].add_kyc_data(KYCData(kycA), 'KYC_SIG', 'CERT')
    payment.data['sender'].change_status(Status.needs_recipient_signature)

    return payment


@pytest.fixture
def kyc_payment_as_sender():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(a0.as_str(), '1', Status.none, [])
    receiver = PaymentActor(str(100), 'C', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Charlie"
    }
    """

    kycA = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Alice"
    }
    """

    payment.data['sender'].add_kyc_data(KYCData(kycA), 'KYC_SIG', 'CERT')
    payment.data['receiver'].add_kyc_data(KYCData(kyc), 'KYC_SIG', 'CERT')
    payment.data['sender'].change_status(Status.needs_recipient_signature)
    payment.add_recipient_signature('SIG')
    assert payment.data['sender'] is not None
    return payment


@pytest.fixture
def settled_payment_as_receiver():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    sender = PaymentActor(str(100), 'C', Status.none, [])
    receiver = PaymentActor(a0.as_str(), '1', Status.none, [])
    action = PaymentAction(5, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)

    kyc = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Charlie"
    }
    """

    kycA = """{
        "payment_reference_id": "ref",
        "type": "individual",
        "name": "Alice"
    }
    """

    payment.data['sender'].add_kyc_data(KYCData(kyc), 'KYC_SIG', 'CERT')
    payment.data['receiver'].add_kyc_data(KYCData(kycA), 'KYC_SIG', 'CERT')
    payment.add_recipient_signature('SIG')
    payment.data['sender'].change_status(Status.settled)
    return payment


@pytest.fixture
def addr_bc_proc():
    a0 = LibraAddress.encode_to_Libra_address(b'B'*16)
    bc = sample_business(a0)
    store = StorableFactory({})
    proc = PaymentProcessor(bc, store)
    return (a0, bc, proc)

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / 'db.dat'
    xdb = dbm.open(str(db_path), 'c')
    return xdb
