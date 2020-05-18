import numpy as np
import matplotlib.pyplot as plt
import re
from glob import glob
import statistics as st
import math

def parse(log_files):
    tps_values, latency_values = {}, {}
    for file in log_files:
        with open(file, 'r') as f:
            data = f.read()

        load = ''.join(re.findall(r'Success #: [0-9]*/[0-9]*.', data))
        load = re.findall(r'\d+', load)
        if len(load) != 2 or load[0] != load[1]:
            print(f'Log file {file} not complete.')
            continue
        load = int(load[0])

        # TPS data.
        tps = ''.join(re.findall(r'Estimate throughput #: [0-9]*.', data))
        tps = re.findall(r'\d+', tps)
        if len(tps) != 1:
            print(f'Log file {file} not complete.')
            continue
        tps = int(tps[0])

        if load in tps_values:
            tps_values[load] += [tps]
        else:
            tps_values[load] = [tps]

        # Latency data.
        latency = ''.join(re.findall(r'Commands executed in [0-9]*', data))
        latency = re.findall(r'\d+', latency)
        if len(latency) != 1:
            print(f'Log file {file} not complete.')
            continue
        latency = int(latency[0])

        if load in latency_values:
            latency_values[load] += [latency]
        else:
            latency_values[load] = [latency]

    return tps_values, latency_values


def plot(values, measure='throughout (tx/sec)'):
    values = list(values.items())
    values.sort(key=lambda tup: tup[0])
    x_values, y_values = list(zip(*values))

    assert all(len(y) > 0 for y in y_values)
    y_err = [st.stdev(y) if len(y) > 1 else 0 for y in y_values]
    y_values = [st.mean(y) for y in y_values]
    plt.errorbar(
        x_values, y_values, yerr=y_err, uplims=True, lolims=True, marker='.'
    )

    def lim(values): return int(math.ceil(max(values) / 100.0)) * 100
    plt.ylim(0, lim(y_values))
    plt.xlabel('System load (tx)')
    plt.ylabel(f'Estimated {measure}')
    name = measure.partition(' ')[0]
    plt.savefig(f'{name}.pdf')
    plt.clf()

    # Print latency for a single request.
    if 1 in values:
        print(f'\nMean latency: {st.mean(values[1])} (s)')
        if len(values[1]) > 1:
             print(f'Std. latency: {st.stdev(values[1])} (s)')


if __name__ == '__main__':
    log_files = glob('logs/*log*')
    tps_values, latency_values = parse(log_files)
    plot(tps_values)
    plot(latency_values, measure='time to process all requests (s)')
