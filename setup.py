# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="libra-offchainreference",
    author="Libra Core Contributors",
    author_email="",
    description="A reference implementation of the Off-chain API (LIP-1)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/libra/off-chain-reference",
    packages=setuptools.find_packages(where='src'),
    package_dir={'': 'src'},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        'aiohttp',
        'bech32',
        'jwcrypto',
        'libra-client-sdk',
    ],
    version="0.0.9.dev1",
)
