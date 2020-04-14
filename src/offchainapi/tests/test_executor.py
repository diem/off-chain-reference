from ..protocol import *
from ..executor import *
from ..payment import *
from ..payment_logic import PaymentCommand
from ..business import BusinessContext

from unittest.mock import MagicMock, PropertyMock
import pytest


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment

def test_handlers(basic_payment):

    a0 = LibraAddress.encode_to_Libra_address(b'A'*16)
    a1 = LibraAddress.encode_to_Libra_address(b'B'*16)
    proc = MagicMock(spec=CommandProcessor)
    store = StorableFactory({})

    vasp = MagicMock(spec=OffChainVASP)
    vasp.info_context = PropertyMock(autospec=True)
    vasp.info_context.get_peer_base_url.return_value = '/'

    proc = MagicMock(spec=CommandProcessor)
    net = MagicMock()
    channel = VASPPairChannel(a0, a1, vasp, store, proc, net)
    object_store = channel.executor.object_store

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

    with store as tx_no: 
        pe.sequence_next_command(cmd1)
        v1 = cmd1.creates_versions[0]
        assert v1 not in channel.executor.object_store

        pe.set_success(0)
        assert v1 in object_store
    
    assert v1 in object_store
    assert len(object_store) == 1
    
    with store as tx_no: 
        assert v1 in object_store
        pe.sequence_next_command(cmd2)
        object_store._check_invariant()
        v2 = cmd2.creates_versions[0]
        assert v2 not in object_store
        object_store._check_invariant()

        pe.set_success(1)
        assert v2 in object_store
        object_store._check_invariant()
    
    object_store._check_invariant()

    assert v1 != v2
    assert v1 in object_store
    assert v2 in object_store
    assert len(object_store) == 2

    #print('Store keys:', list(object_store.keys()))
    #print('deps', cmd3.dependencies)
    
    with pytest.raises(ExecutorException):
        with store as tx_no: 
            pe.sequence_next_command(cmd3)
            # pe.set_fail(2)

    assert stat.success_no == 2
    assert stat.failure_no == 0
