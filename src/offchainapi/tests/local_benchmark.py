# Sample benchmark to profile performance and observe bottlenecks.
#
# Run as:
# $ python -m cProfile -s tottime src/scripts/run_perf.py > report.txt
#
from ..business import VASPInfo, BusinessContext
from ..libra_address import LibraAddress
from ..payment_logic import PaymentCommand
from ..status_logic import Status
from ..payment import PaymentAction, PaymentActor, PaymentObject
from ..core import Vasp

import logging
from mock import AsyncMock
from threading import Thread
import time
import asyncio

# A stand alone performance test.

PeerA_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
PeerB_addr = LibraAddress.encode_to_Libra_address(b'B'*16)
peer_address = {
    PeerA_addr.as_str(): 'http://localhost:8091',
    PeerB_addr.as_str(): 'http://localhost:8092',
}


class SimpleVASPInfo(VASPInfo):

    def __init__(self):
        return

    def get_TLS_certificate_path(self):
        raise NotImplementedError()

    def get_TLS_key_path(self):
        raise NotImplementedError()

    def get_peer_TLS_certificate_path(self, other_addr):
        raise NotImplementedError()

    def get_all_peers_TLS_certificate_path(self):
        raise NotImplementedError()

    def get_peer_base_url(self, other_addr):
        assert other_addr.as_str() in peer_address
        return peer_address[other_addr.as_str()]

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
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

    logging.debug('VASP loop exit')

def make_new_VASP(Peer_addr, port):
    VASPx = Vasp(
        Peer_addr,
        host='localhost',
        port=port,
        business_context=AsyncMock(spec=BusinessContext),
        info_context=SimpleVASPInfo(),
        database={})

    loop = asyncio.new_event_loop()
    t = Thread(target=start_thread_main, args=(VASPx, loop))
    t.start()
    print(f'Start Node {port}')
    return (VASPx, loop, t)

async def main_perf():
    VASPa, loopA, tA = make_new_VASP(PeerA_addr, port=8091)
    VASPb, loopB, tB = make_new_VASP(PeerB_addr, port=8092)

    await asyncio.sleep(2.0)
    print('Inject commands')
    await asyncio.sleep(1.0)
    while len(global_dir) != 2:
        await asyncio.sleep(0.1)
    print(global_dir)

    # Get the channel from A -> B
    channelAB = VASPa.vasp.get_channel(PeerB_addr)
    channelBA = VASPb.vasp.get_channel(PeerA_addr)

    # Define a payment command
    commands = []
    for cid in range(100):
        sender = PaymentActor(PeerA_addr.as_str(), 'aaaa', Status.none, [])
        receiver = PaymentActor(PeerB_addr.as_str(), 'bbbb', Status.none, [])
        action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
        payment = PaymentObject(
            sender, receiver, f'ref {cid}', 'orig_ref', 'desc', action
        )
        cmd = PaymentCommand(payment)
        commands += [cmd]

    s = time.perf_counter()

    async def send100(nodeA, commands):
        res = await asyncio.gather(
            *[nodeA.new_command_async(VASPb.my_addr, cmd) for cmd in commands], return_exceptions=True)
        return res

    res = asyncio.run_coroutine_threadsafe(send100(VASPa, commands), loopA)
    res = res.result()

    success_number = sum([1 for r in res if r])
    elapsed = (time.perf_counter() - s)
    print(f'Commands executed in {elapsed:0.2f} seconds.')
    print(f'Success #: {success_number}/{len(commands)}')

    # In case you want to wait for other responses to settle
    # for t in range(10):
    #     print('waiting', t)
    #     await asyncio.sleep(1.0)

    # Esure they were register as successes on both sides.
    Asucc = len([x for x in channelAB.executor.command_status_sequence if x])
    Atotal = len(channelAB.executor.command_status_sequence)
    print(f'Peer A successes: {Asucc}/{Atotal}')

    Bsucc = len([x for x in channelBA.executor.command_status_sequence if x])
    Btotal = len(channelBA.executor.command_status_sequence)
    print(f'Peer B successes: {Bsucc}/{Btotal}')

    print(f'Estimate throughput #: {len(commands)/elapsed} Tx/s')

    VASPa.close()
    VASPb.close()

    #import sys
    #sys.exit()
