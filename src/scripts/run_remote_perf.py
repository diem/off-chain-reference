import asyncio
import sys
sys.path += ['src/.']

from offchainapi import remote_benchmark

assert len(sys.argv) > 2
my_configs_path = sys.argv[1]
my_configs_path = sys.argv[2]
num_of_commands = int(sys.argv[3]) if len(sys.argv) > 3 else 0

# Run performance testing.
asyncio.run(
    remote_benchmark.main_perf(
        my_configs_path, other_configs_path, num_of_commands
    )
)
