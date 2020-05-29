# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

'''
A benchmark to measure command throughput between a client and a server.

RUN SERVER: python3 -O src/scripts/run_remote_perf.py test_config_A.json
RUN CLIENT: python3 -O src/scripts/run_remote_perf.py test_config_B.json 10
'''
from threading import Thread
from glob import glob
import time
import asyncio
import sys
sys.path += ['src/.']

from offchainapi.tests import remote_benchmark

if __name__ == '__main__':
    # Run by tox on same machine
    if len(sys.argv) == 1:
        my_configs_path = 'test_config_A.json'
        other_configs_path = 'test_config_B.json'
        num_of_commands = 10
        loop = asyncio.get_event_loop()
        server = Thread(
            target=remote_benchmark.run_server,
            args=(my_configs_path, other_configs_path, num_of_commands, loop)
        )
        client = Thread(
            target=remote_benchmark.run_client,
            args=(other_configs_path, my_configs_path, num_of_commands)
        )
        server.start()
        time.sleep(0.3)
        client.start()

    # Run manually / on different machines
    else:
        my_configs_path = sys.argv[1]
        num_of_commands = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 0

        files = glob('*.json')
        assert len(files) == 2
        other_configs_path = files[1] if my_configs_path == files[0] else files[0]

        if num_of_commands > 0:
            remote_benchmark.run_client(
                my_configs_path, other_configs_path, num_of_commands, port
            )
        else:
            remote_benchmark.run_server(my_configs_path, other_configs_path)
