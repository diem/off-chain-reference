import asyncio
import glob
import sys
sys.path += ['src/.']

from offchainapi import remote_benchmark

assert len(sys.argv) > 1
my_configs_path = sys.argv[1]
num_of_commands = int(sys.argv[2]) if len(sys.argv) > 2 else 0

files = glob('../*.json')
assert len(files) == 2
other_configs_path = files[1] if my_configs_path == files[0] else files[0]
print(other_configs_path, my_configs_path)

# Run performance testing.
asyncio.run(
    remote_benchmark.main_perf(
        my_configs_path, other_configs_path, num_of_commands
    )
)
