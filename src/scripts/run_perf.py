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
    parser.add_argument(
        '-x', '--xprofile', metavar='PROFILE', type=bool, default=False,
        help='Profile this run', dest='xprof')

    args = parser.parse_args()

    # When verbose print all information
    if args.verb:
        print('Full logging...')
        logging.basicConfig(level=logging.DEBUG)
    else:
        print('Error only logging...')
        logging.basicConfig(level=logging.ERROR)

    if args.xprof:
        import yappi
        import time
        yappi.set_clock_type("cpu")
        yappi.start()

    asyncio.run(local_benchmark.main_perf(
        messages_num=args.paym,
        wait_num=args.wait,
        verbose=args.verb))

    if args.xprof:

        columns={
            0: ("name", 100),
            1: ("ncall", 20),
            2: ("tsub", 8),
            3: ("ttot", 8),
            4: ("tavg", 8)
        }

        yappi.get_func_stats().strip_dirs().print_all(columns=columns)
        yappi.get_thread_stats().print_all()
