'''
RUN SERVER: python3 -O src/scripts/run_remote_perf.py test_config_A.json

RUN CLIENT: python3 -O src/scripts/run_remote_perf.py test_config_B.json 10
'''
import asyncio
from glob import glob
import sys
sys.path += ['src/.']

from offchainapi.tests import remote_benchmark

assert len(sys.argv) > 1
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
