from ..business import VASPInfo
from ..protocol import OffChainVASP
from ..libra_address import LibraAddress
from ..payment_logic import PaymentCommand, PaymentProcessor
from ..status_logic import Status
from ..storage import StorableFactory
from ..payment import PaymentAction, PaymentActor, PaymentObject
from ..asyncnet import Aionet
from ..core import Vasp

import logging
import json
from unittest.mock import MagicMock
from threading import Thread
import time
import asyncio
from aiohttp import web
import sys
from json import loads
import aiohttp


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
        base_url = self.other_configs['base_url']
        port = self.other_configs['port']
        return f'{base_url}:{port}'

    def is_authorised_VASP(self, certificate, other_addr):
        return True


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


def run_server(my_configs_path, other_configs_path):
    ''' Run the VASP as server (do not send commands).

    The arguments <my_configs_path> and <other_configs_path> are paths to
    files describing the configurations of the current VASP and of the other
    VASP, respectively. Configs are dict taking the following form:
        configs = {
            'addr': <LibraAddress>,
            'base_url': <str>,
            'port': <int>,
        }
    '''
    logging.basicConfig(level=logging.INFO)

    my_configs = load_configs(my_configs_path)
    other_configs = load_configs(other_configs_path)
    my_addr = my_configs['addr']

    # Create VASP.
    vasp = Vasp(
        my_addr,
        host='0.0.0.0',
        port=my_configs['port'],
        business_context=MagicMock(),
        info_context=SimpleVASPInfo(my_configs, other_configs),
        database={}
    )
    logging.info(f'Created VASP {my_addr.as_str()}.')

    # Run VASP services.
    logging.info(f'Running VASP {my_addr.as_str()}.')
    loop = asyncio.get_event_loop()
    vasp.start_services(loop)
    loop.run_forever()


def run_client(my_configs_path, other_configs_path, num_of_commands=10):
    ''' Run the VASP's client to send commands to the other VASP.

    The VASP sends <num_of_commands> commands to the other VASP.
    The arguments <my_configs_path> and <other_configs_path> are paths to
    files describing the configurations of the current VASP and of the other
    VASP, respectively. Configs are dict taking the following form:
        configs = {
            'addr': <LibraAddress>,
            'base_url': <str>,
            'port': <int>,
        }
    '''
    assert num_of_commands > 0
    logging.basicConfig(level=logging.INFO)

    my_configs = load_configs(my_configs_path)
    other_configs = load_configs(other_configs_path)
    my_addr = my_configs['addr']
    other_addr = other_configs['addr']

    # Create VASP.
    vasp = Vasp(
        my_addr,
        host='0.0.0.0',
        port=my_configs['port'],
        business_context=MagicMock(),
        info_context=SimpleVASPInfo(my_configs, other_configs),
        database={}
    )
    logging.info(f'Created VASP {my_addr.as_str()}.')

    # Run VASP services.
    def start_services(vasp, loop):
        vasp.start_services(loop)
        logging.debug('Start main loop')
        loop.run_forever()

    loop = asyncio.new_event_loop()
    Thread(target=start_services, args=(vasp, loop), daemon=True).start()
    logging.info(f'VASP services are running on port {vasp.port}.')

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
    logging.info(
        ('Start measurements: '
         f'sending {num_of_commands} commands to {other_addr.as_str()}.')
    )
    start_time = time.perf_counter()

    async def send_commands(vasp, commands):
        return await asyncio.gather(
            *[vasp.new_command_async(other_addr, c) for c in commands]
        )

    res = asyncio.run_coroutine_threadsafe(send_commands(vasp, commands), loop)
    res = res.result()

    elapsed = (time.perf_counter() - start_time)

    # Display performance and success rate.
    success_number = sum([1 for r in res if r])
    logging.info(f'Commands executed in {elapsed:0.2f} seconds.')
    logging.info(f'Success #: {success_number}/{len(commands)}.')
    logging.info(f'Estimate throughput #: {len(commands)/elapsed} TPS.')
