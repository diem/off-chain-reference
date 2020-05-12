""" A simple script that runs a local performance test,
    incl. networking and storage. """

import asyncio
import logging
import argparse

try:
    from offchainapi.tests import local_benchmark
except:
    print('Use Local Version... ')
    import sys
    sys.path += ['src/.']
    from offchainapi.tests import local_benchmark

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Local Benchmarks for offchainapi.')
    parser.add_argument(
        '-p', '--payments', metavar='PAYMENT_NUM', type=int, default=10,
        help='number of payments to process', dest='paym')
    parser.add_argument(
        '-w', '--wait', metavar='WAIT_SEC', type=int, default=0,
        help='number of seconds to wait', dest='wait')
    parser.add_argument(
        '-v', '--verbose', metavar='VERBOSE', type=bool, default=False,
        help='Print all payments', dest='verb')

    args = parser.parse_args()

    # When verbose print all information
    if args.verb:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)

    asyncio.run(local_benchmark.main_perf(
        messages_num=args.paym,
        wait_num=args.wait,
        verbose=args.verb))
