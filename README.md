# off-chain-reference
[![License](https://img.shields.io/badge/license-Apache-green.svg)](LICENSE)

Off-Chain Reference: Provide a reference implemenation for defining payments, exchanging KYC data and attestation of KYC data between VASPs.

## Installation

To install the API, activate the Python virtual environment you use, and then execute:

    git clone https://github.com/novifinancial/off-chain-api.git
    cd off-chain-api
    pip install .

If you plan to do development for the Off-Chain API consider installing in _develop_ editable mode:

    pip install -e .

You can also use `tox` to run all the tests and build the documentation:

    pip install tox
    tox
    tox -e docs

This should create a number of resources:

* It will run all `pytest` tests and the local benchmark under coverage.
* It will create HTML *source code coverage reports* under `htmlcov/index.html`.
* It will build the documentation under `docs/_build/html/index.html`.

The index of the documentation is a very good place to start to learn more. [Overview](specs/off_chain_protocol.md)

## Status

The specifications and code are shared here to support discussions within the Libra Association and wider community. Neither the specifications nor the code should be considered final. Breaking API changes are likely to occur.

## License

Off-Chain API is licensed as [Apache 2.0](https://github.com/novifinancial/off-chain-api/blob/master/LICENSE).
