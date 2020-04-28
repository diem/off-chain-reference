""" A simple script that runs a local performance test,
    incl. networking and storage. """

import asyncio
import logging
import sys
sys.path += ['src/.']

from offchainapi.tests import local_benchmark

if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(local_benchmark.main_perf())
