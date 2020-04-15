from .business import BusinessContext, BusinessForceAbort, \
BusinessValidationFailure, VASPInfo
from .protocol import OffChainVASP
from .libra_address import LibraAddress
from .protocol_messages import CommandRequestObject
from .payment_logic import PaymentCommand, PaymentProcessor
from .status_logic import Status
from .storage import StorableFactory
from .networking import NetworkServer, NetworkClient

import json
from unittest.mock import MagicMock
from threading import Thread

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
    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.bc = MagicMock()
        self.store        = StorableFactory({})
        self.info_context = SimpleVASPInfo()
        self.network_factory = SimpleNetworkFactory()

        self.pp = PaymentProcessor(self.bc, self.store)
        self.vasp = OffChainVASP(
            self.my_addr, self.pp, self.store, self.info_context, self.network_factory
        )

def start_thread_main(addr):
    node = PerfVasp(addr)

def main_perf():
    
    tA = Thread(target=start_thread_main, args=(PeerA_addr,))
    tA.start()
    print('Start Node A')

    tB = Thread(target=start_thread_main, args=(PeerB_addr,))
    tB.start()
    print('Start Node B')
