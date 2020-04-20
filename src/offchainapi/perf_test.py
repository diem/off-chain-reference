# Sample benchmark to profile performance and observe bottlenecks.
#
# Run as:
# $ python -m cProfile -s tottime src/scripts/run_perf.py > report.txt
#

import logging

from .business import BusinessContext, BusinessForceAbort, \
BusinessValidationFailure, VASPInfo
from .protocol import OffChainVASP
from .libra_address import LibraAddress
from .protocol_messages import CommandRequestObject
from .payment_logic import PaymentCommand, PaymentProcessor
from .status_logic import Status
from .storage import StorableFactory
from .networking import NetworkServer, NetworkClient
from .payment import PaymentAction, PaymentActor, PaymentObject

import json
from unittest.mock import MagicMock
from threading import Thread
import time

# A stand alone performance test.

PeerA_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
PeerB_addr = LibraAddress.encode_to_Libra_address(b'B'*16)
peer_address = {
    PeerA_addr.as_str() : 'http://localhost:8091',
    PeerB_addr.as_str() : 'http://localhost:8092',
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

class SimpleNetworkFactory:

    def make_client(self, my_addr, other_addr, info_context):
        return NetworkClient(my_addr, other_addr)


class PerfVasp:
    def __init__(self, my_addr, port):
        self.my_addr = my_addr
        self.port = port
        self.bc = MagicMock()
        self.store        = StorableFactory({})
        self.info_context = SimpleVASPInfo()
        self.network_factory = SimpleNetworkFactory()

        self.pp = PaymentProcessor(self.bc, self.store)
        self.vasp = OffChainVASP(
            self.my_addr, self.pp, self.store, self.info_context, self.network_factory
        )

        self.server = NetworkServer(self.vasp)
    
    def start(self):
        # Start the processor
        self.pp.start_processor()
        # Start the server
        self.server.run(port=self.port)

global_dir = {}

def start_thread_main(addr, port):
    node = PerfVasp(addr, port)
    global_dir[addr.as_str()] = node
    node.start()

def main_perf():
    logging.basicConfig(level=logging.DEBUG)
    
    tA = Thread(target=start_thread_main, args=(PeerA_addr, 8091, ), daemon=True)
    tA.start()
    print('Start Node A')

    tB = Thread(target=start_thread_main, args=(PeerB_addr, 8092, ), daemon=True)
    tB.start()
    print('Start Node B')

    time.sleep(1.0) # sec
    print('Inject commands')
    time.sleep(1.0)
    while len(global_dir) != 2:
        time.sleep(0.1)
    print(global_dir)

    # Get the channel from A -> B
    nodeA = global_dir[PeerA_addr.as_str()]
    channelAB = nodeA.vasp.get_channel(PeerB_addr)
    nodeB = global_dir[PeerB_addr.as_str()]
    channelBA = nodeB.vasp.get_channel(PeerA_addr)

    # Define a payment command
    commands = []
    for cid in range(100):
        sender = PaymentActor(PeerA_addr.as_str(), 'aaaa', Status.none, [])
        receiver = PaymentActor(PeerB_addr.as_str(), 'bbbb', Status.none, [])
        action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
        payment = PaymentObject(sender, receiver, f'ref {cid}', 'orig_ref', 'desc', action)
        cmd = PaymentCommand(payment)
        commands += [ cmd ]


    start_timer = time.time()

    for cmd in commands:
        channelAB.sequence_command_local(cmd)

    def channel_summary(name, channel):
        localQlen = len(channel.my_requests)
        remoteQlen = len(channel.other_requests)
        commonQlen = len(channel.get_final_sequence())
        logging.debug(f'{name} : L:{localQlen}  R:{remoteQlen}  C:{commonQlen}')

        if commonQlen < 100:
            return False

        channel.processor.stop_processor()
        return True
        
    exit_loop = False
    while not exit_loop:
        exit_loop = True
        time.sleep(0.1)
        exit_loop &= channel_summary('AB', channelAB)
        exit_loop &= channel_summary('BA', channelBA)
    
    end_timer = time.time()
    
    per_command_time = (end_timer - start_timer) / 100
    est_tx_per_sec = 1.0 / per_command_time

    print('Exit loop')

    success_number = 0
    for i in range(len(channelAB.executor.command_status_sequence)):
        if channelAB.executor.command_status_sequence[i]:
            success_number += 1

    print(f'Success #: {success_number}/100')
    print(f'Command time: {1000*per_command_time: 4.2f} ms Estimate throughput: {est_tx_per_sec: 4.2f} Tx/sec')

    import sys
    sys.exit()
