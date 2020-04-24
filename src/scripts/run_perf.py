import sys
sys.path += ['src/.']
import asyncio

from offchainapi.tests import local_benchmark

asyncio.run(local_benchmark.main_perf())
