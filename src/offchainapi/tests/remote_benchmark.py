# Copyright (c) Facebook, Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ..business import VASPInfo, BusinessContext
from ..protocol import OffChainVASP
from ..libra_address import LibraAddress
from ..payment_logic import PaymentCommand, PaymentProcessor
from ..status_logic import Status
from ..storage import StorableFactory
from ..payment import PaymentAction, PaymentActor, PaymentObject, StatusObject
from ..asyncnet import Aionet
from ..core import Vasp
from ..crypto import ComplianceKey
from .basic_business_context import TestBusinessContext

import logging
import json
from mock import AsyncMock
from unittest.mock import MagicMock
from threading import Thread
import time
import asyncio
from aiohttp import web
import sys
from json import loads, dumps
import aiohttp

logging.basicConfig(
    level=logging.ERROR, format="[%(levelname)s] %(asctime)s: %(message)s"
)


class SimpleVASPInfo(VASPInfo):
    ''' Simple implementation of VASPInfo. '''

    def __init__(self, my_configs, other_configs, port=0):
        self.my_configs = my_configs
        self.other_configs = other_configs
        self.port = port

    def get_peer_base_url(self, other_addr):
        protocol = 'https://' if self.port == 443 else 'http://'
        base_url = self.other_configs['base_url']
        port = self.port if self.port != 0 else self.other_configs['port']
        return f'{protocol}{base_url}:{port}'

    def get_peer_compliance_verification_key(self, other_addr):
        return self.other_configs['key']

    def get_peer_compliance_signature_key(self, my_addr):
        return self.my_configs['key']

    def get_TLS_cert_path(self, other_addr):
        host = self.other_configs['base_url']
        return f'/home/ubuntu/{host}-nginx-selfsigned.crt'


def load_configs(configs_path):
    ''' Loads VASP configs from file. '''
    with open(configs_path, 'r') as f:
        configs = loads(f.read())

    assert 'addr' in configs
    assert 'base_url' in configs
    assert 'port' in configs
    assert 'key' in configs

    bytes_addr = configs['addr'].encode()
    configs['addr'] = LibraAddress.from_bytes(bytes_addr)
    configs['port'] = int(configs['port'])
    configs['key'] = ComplianceKey.from_str(dumps(configs['key']))
    return configs


def run_server(my_configs_path, other_configs_path, num_of_commands=10, loop=None):
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
    my_configs = load_configs(my_configs_path)
    other_configs = load_configs(other_configs_path)
    my_addr = my_configs['addr']
    other_addr = other_configs['addr']

    # Create VASP.
    vasp = Vasp(
        my_addr,
        host='0.0.0.0',
        port=my_configs['port'],
        business_context=AsyncMock(spec=BusinessContext),
        info_context=SimpleVASPInfo(my_configs, other_configs),
        database={}
    )
    logging.info(f'Created VASP {my_addr.as_str()}.')

    # Run VASP services.
    logging.info(f'Running VASP {my_addr.as_str()}.')
    loop = asyncio.get_event_loop() if loop is None else loop

    vasp.set_loop(loop)
    vasp.start_services()
    logging.info(f'VASP services are running on port {vasp.port}.')

    def stop_server(vasp):
        channel = vasp.vasp.get_channel(other_addr)
        requests = len(channel.other_request_index)
        while requests < num_of_commands:
            requests = len(channel.other_request_index)
            time.sleep(0.1)
        vasp.close()
    Thread(target=stop_server, args=(vasp,)).start()

    try:
        loop.run_forever()

    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def run_client(my_configs_path, other_configs_path, num_of_commands=10, port=0):
    ''' Run the VASP's client to send commands to the other VASP.

    The VASP sends <num_of_commands> commands to the other VASP, on port <port>.
    If <port> is 0, the VASP defaults to the port specified in <other_configs>.
    Being able to easily modify the port allows to quickly test performance
    in different situations, such as HTTP, HTTPS, or custom port.

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

    my_configs = load_configs(my_configs_path)
    other_configs = load_configs(other_configs_path)
    my_addr = my_configs['addr']
    other_addr = other_configs['addr']

    # Create VASP.
    vasp = Vasp(
        my_addr,
        host='0.0.0.0',
        port=my_configs['port'],
        business_context=TestBusinessContext(my_addr),
        info_context=SimpleVASPInfo(my_configs, other_configs, port),
        database={}
    )
    logging.info(f'Created VASP {my_addr.as_str()}.')

    # Run VASP services.
    def start_services(vasp, loop):
        vasp.start_services()
        logging.debug('Start main loop.')
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    loop = asyncio.new_event_loop()
    vasp.set_loop(loop)
    t = Thread(target=start_services, args=(vasp, loop), daemon=True)
    t.start()
    logging.info(f'VASP services are running on port {vasp.port}.')

    # Make a payment commands.
    commands = []
    for cid in range(num_of_commands):
        sub_a = LibraAddress.from_bytes(b'A'*16, b'a'*8).as_str()
        sub_b = LibraAddress.from_bytes(b'B'*16, b'b'*8).as_str()
        sender = PaymentActor(sub_b, StatusObject(Status.none), [])
        receiver = PaymentActor(sub_a, StatusObject(Status.none), [])
        action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
        reference = f'{my_addr.as_str()}_{cid}'
        payment = PaymentObject(
            sender, receiver, reference, 'orig_ref', 'desc', action
        )
        cmd = PaymentCommand(payment)
        commands += [cmd]

    # Send commands.
    logging.info(
        'Start measurements: '
        f'sending {num_of_commands} commands to {other_addr.as_str()}.'
    )
    logging.info(
        f'The target URL is {vasp.info_context.get_peer_base_url(other_addr)}'
    )
    start_time = time.perf_counter()

    async def send_commands(vasp, commands):
        return await asyncio.gather(
            *[vasp.new_command_async(other_addr, c) for c in commands],
            return_exceptions=True
        )

    res = asyncio.run_coroutine_threadsafe(send_commands(vasp, commands), loop)
    res = res.result()

    elapsed = (time.perf_counter() - start_time)

    # Display performance and success rate.
    success_number = sum([1 for r in res if r])
    logging.info(f'Commands executed in {elapsed:0.2f} seconds.')
    logging.info(f'Success #: {success_number}/{len(commands)}.')
    logging.info(f'Estimate throughput #: {len(commands)/elapsed} TPS.')
