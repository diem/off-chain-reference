from .business import VASPInfo
from .protocol import OffChainVASP
from .libra_address import LibraAddress
from .payment_logic import PaymentCommand, PaymentProcessor
from .status_logic import Status
from .storage import StorableFactory
from .payment import PaymentAction, PaymentActor, PaymentObject
from .asyncnet import Aionet

import logging
import json
from unittest.mock import MagicMock
from threading import Thread
import time
import asyncio
from aiohttp import web
import sys
from json import loads

class SimpleVASPInfo(VASPInfo):
    ''' Simple implementation of VASPInfo. '''

    def __init__(self, my_configs, other_configs):
        self.my_configs = my_configs
        self.other_configs = other_configs

    def get_TLS_certificate_path(self):
        raise NotImplementedError()

    def get_TLS_key_path(self):
        raise NotImplementedError()

    def get_peer_TLS_certificate_path(self, other_addr):
        raise NotImplementedError()

    def get_all_peers_TLS_certificate_path(self):
        raise NotImplementedError()

    def get_peer_base_url(self, other_addr):
        return self.other_configs['base_url']

    def is_authorised_VASP(self, certificate, other_addr):
        return True


class PerfVasp:
    ''' Minimal VASP for performance testing. '''

    def __init__(self, my_configs, other_configs):
        self.my_addr = my_configs['addr']
        self.port = my_configs['port']
        self.bc = MagicMock()
        self.store = StorableFactory({})
        self.info_context = SimpleVASPInfo(my_configs, other_configs)
        self.pp = PaymentProcessor(self.bc, self.store)
        self.vasp = OffChainVASP(
            self.my_addr, self.pp, self.store, self.info_context
        )
        self.net_handler = Aionet(self.vasp)

    def start(self, loop):
        # Start the processor.
        self.pp.start_processor()

        # Start the server.
        runner = self.net_handler.get_runner()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, 'localhost', self.port)
        loop.run_until_complete(site.start())
        loop.run_forever()


def load_configs(configs_path):
    ''' Loads VASP configs from file. '''
    with open(configs_path, 'r') as f:
        configs = loads(f.read())

    assert 'addr' in configs
    assert 'base_url' in configs
    assert 'port' in configs

    bytes_addr = configs['addr'].encode()
    configs['addr'] = LibraAddress.encode_to_Libra_address(bytes_addr)
    configs['port'] = int(configs['port'])
    return configs


async def main_perf(my_configs_path, other_configs_path, num_of_commands=0):
    ''' Run the VASP's server and commands to the other VASP.

    If <num_of_commands> is positive, the VASP sends as many commands to the
    other VASP. The arguments <my_configs_path> and <other_configs_path> are
    paths to files describing the configurations of the current VASP and of
    the other VASP, respectively. Configs are dict taking the following form:
        configs = {
            'addr': <LibraAddress>,
            'base_url': <str>,
            'port': <int>,
        }
    '''
    assert num_of_commands >= 0
    logging.basicConfig(level=logging.DEBUG)

    my_configs = load_configs(my_configs_path)
    other_configs = load_configs(other_configs_path)

    print(my_configs)
    print(other_configs)
    sys.exit()

    # Create VASP.
    my_addr = my_configs['addr']
    node = PerfVasp(my_configs, other_configs)

    # Start server.
    loop = asyncio.new_event_loop()
    Thread(target=node.start, args=(loop,), daemon=True).start()

    # Stop here if there are no commands to send.
    if num_of_commands == 0:
        sys.exit()

    # Get the channel to the other vasp.
    other_addr = other_configs['addr']
    channel = node.vasp.get_channel(other_addr)

    # Make a payment commands.
    commands = []
    for cid in range(num_of_commands):
        sender = PaymentActor(my_addr.as_str(), 'aaaa', Status.none, [])
        receiver = PaymentActor(other_addr.as_str(), 'bbbb', Status.none, [])
        action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
        payment = PaymentObject(
            sender, receiver, f'ref {cid}', 'orig_ref', 'desc', action
        )
        cmd = PaymentCommand(payment)
        commands += [cmd]

    # Send commands.
    start_time = time.perf_counter()

    async def send(node, commands):
        return await asyncio.gather(
            *[node.net_handler.send_command(other_addr, c) for c in commands]
        )

    res = asyncio.run_coroutine_threadsafe(send(node, commands), loop)
    res = res.result()

    elapsed = (time.perf_counter() - start_time)

    # Display performance and success rate.
    success_number = sum([1 for r in res if r])
    print(f'Commands executed in {elapsed:0.2f} seconds.')
    print(f'Success #: {success_number}/{len(commands)}.')
    print(f'Estimate throughput #: {len(commands)/elapsed} TPS.')

    # Esure they were register as successes on both sides.
    '''
    Asucc = len([x for x in channelAB.executor.command_status_sequence if x])
    Atotal = len(channelAB.executor.command_status_sequence)
    print(f'Peer A successes: {Asucc}/{Atotal}')
    '''

    sys.exit()
