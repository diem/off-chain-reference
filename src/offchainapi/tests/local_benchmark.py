# Sample benchmark to profile performance and observe bottlenecks.
#
# Run as:
# $ python -m cProfile -s tottime src/scripts/run_perf.py > report.txt
#
from ..business import VASPInfo
from ..libra_address import LibraAddress, LibraSubAddress
from ..payment_logic import PaymentCommand
from ..status_logic import Status
from ..payment import PaymentAction, PaymentActor, PaymentObject
from ..core import Vasp
from .basic_business_context import BasicBusinessContext
from ..crypto import ComplianceKey

from threading import Thread
import time
import asyncio

# A stand alone performance test.

PeerA_addr = LibraAddress.encode(b'A'*16)
PeerB_addr = LibraAddress.encode(b'B'*16)
peer_address = {
    PeerA_addr.as_str(): 'http://localhost:8091',
    PeerB_addr.as_str(): 'http://localhost:8092',
}

peer_keys = {
    PeerA_addr.as_str(): ComplianceKey.generate(),
    PeerB_addr.as_str(): ComplianceKey.generate(),
}


class SimpleVASPInfo(VASPInfo):

    def __init__(self, my_addr):
        self.my_addr = my_addr

    def get_peer_base_url(self, other_addr):
        assert other_addr.as_str() in peer_address
        return peer_address[other_addr.as_str()]

    def get_peer_compliance_verification_key(self, other_addr):
        return peer_keys[other_addr]

    def get_peer_compliance_signature_key(self, my_addr):
        return peer_keys[my_addr]

    def is_authorised_VASP(self, certificate, other_addr):
        return True


global_dir = {}


async def update_dir(vasp):
    global_dir[vasp.vasp.get_vasp_address().as_str()] = vasp


def start_thread_main(vasp, loop):
    # Initialize the VASP services.
    vasp.start_services(loop)

    # Run this once the loop is running
    loop.create_task(update_dir(vasp))

    try:
        # Start the loop
        loop.run_forever()
    finally:
        # Do clean up
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

    print('VASP loop exit...')


def make_new_VASP(Peer_addr, port):
    VASPx = Vasp(
        Peer_addr,
        host='localhost',
        port=port,
        business_context=BasicBusinessContext(Peer_addr),
        info_context=SimpleVASPInfo(Peer_addr),
        database={})

    loop = asyncio.new_event_loop()
    t = Thread(target=start_thread_main, args=(VASPx, loop))
    t.start()
    print(f'Start Node {port}')
    return (VASPx, loop, t)


async def main_perf(messages_num=10, wait_num=0, verbose=False):
    VASPa, loopA, tA = make_new_VASP(PeerA_addr, port=8091)
    VASPb, loopB, tB = make_new_VASP(PeerB_addr, port=8092)

    await asyncio.sleep(2.0)
    while len(global_dir) != 2:
        await asyncio.sleep(0.1)
    print(global_dir)

    # Get the channel from A -> B
    channelAB = VASPa.vasp.get_channel(PeerB_addr)
    channelBA = VASPb.vasp.get_channel(PeerA_addr)

    # Define a payment command
    commands = []
    payments = []
    for cid in range(messages_num):
        peerA_addr = PeerA_addr.as_str()
        sub_a = LibraSubAddress.encode(b'A'*16, b'a'*8).as_str()
        sub_b = LibraSubAddress.encode(b'B'*16, b'b'*8).as_str()
        sender = PaymentActor(peerA_addr, sub_a, Status.needs_kyc_data, [])
        receiver = PaymentActor(PeerB_addr.as_str(), sub_b, Status.none, [])
        action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
        payment = PaymentObject(
            sender, receiver, f'{peerA_addr}_ref_{cid}', 'orig_ref', 'desc', action
        )
        kyc_data = asyncio.run_coroutine_threadsafe(VASPa.bc.get_extended_kyc(payment), loopA)
        kyc_data = kyc_data.result()
        payment.sender.add_kyc_data(*kyc_data)
        payments += [payment]
        cmd = PaymentCommand(payment)
        commands += [cmd]

    async def send100(nodeA, commands):
        res = await asyncio.gather(
            *[nodeA.new_command_async(VASPb.my_addr, cmd) for cmd in commands],
            return_exceptions=False)
        return res

    async def wait_for_all_payment_outcome(nodeA, payments):
        res = await asyncio.gather(
            *[nodeA.wait_for_payment_outcome_async(p.reference_id) for p in payments],
            return_exceptions=False)
        return res

    # Execute 100 requests
    print('Inject commands')
    s = time.perf_counter()
    res = asyncio.run_coroutine_threadsafe(send100(VASPa, commands), loopA)
    res = res.result()
    elapsed = (time.perf_counter() - s)

    print('Wait for all payments too have an outcome')
    outcomes = asyncio.run_coroutine_threadsafe(
        wait_for_all_payment_outcome(VASPa, payments), loopA)
    outcomes = outcomes.result()
    for out in outcomes:
        print(out.sender.status, out.receiver.status)
    print('All payments done.')

    # Print some statistics
    success_number = sum([1 for r in res if r])
    print(f'Commands executed in {elapsed:0.2f} seconds.')
    print(f'Success #: {success_number}/{len(commands)}')

    # In case you want to wait for other responses to settle
    #
    wait_for = wait_num
    for t in range(wait_for):
        print('waiting', t)
        await asyncio.sleep(1.0)

    # Check that all the payments have been processed and stored.
    for payment in payments:
        ref = payment.reference_id
        _ = VASPa.get_payment_by_ref(ref)
        hist = VASPa.get_payment_history_by_ref(ref)
        if verbose:
            if len(hist) > 1:
                print('--'*40)
                for p in hist:
                    print(p.pretty())

    # Esure they were register as successes on both sides.
    Asucc = len([x for x in channelAB.executor.command_status_sequence if x])
    Atotal = len(channelAB.executor.command_status_sequence)
    print(f'Peer A successes: {Asucc}/{Atotal}')

    Bsucc = len([x for x in channelBA.executor.command_status_sequence if x])
    Btotal = len(channelBA.executor.command_status_sequence)
    print(f'Peer B successes: {Bsucc}/{Btotal}')

    print(f'Estimate throughput #: {len(commands)/elapsed} Tx/s')

    # Close the loops
    VASPa.close()
    VASPb.close()

    # List the command obligations
    oblA = VASPa.pp.list_command_obligations()
    oblB = VASPb.pp.list_command_obligations()
    print(f'Pending processing: VASPa {len(oblA)} VASPb {len(oblB)}')

    # List the remaining retransmits
    rAB = channelAB.pending_retransmit_number()
    rBA = channelBA.pending_retransmit_number()
    print(f'Pending retransmit: VASPa {rAB} VASPb {rBA}')
