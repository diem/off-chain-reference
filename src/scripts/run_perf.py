import sys
sys.path += ['src/.']
import asyncio

from offchainapi import local_benchmark

#perf_test.main_perf()
asyncio.run(local_benchmark.main_perf())
