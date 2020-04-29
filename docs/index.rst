Offchainapi Documentation
=========================

The Libra Off-Chain API is a protocol that allows Virtual Asset Service Providers (VASPs)
to coordinate off the main Libra blockchain, to define payments, prior to settling them
on-chain. It supports:

* Compliance, through the ability to  exchange Know-Your-Customer
  (KYC) information about payer and payee.
* Privacy, by allowing VASPs to not expose any information about the subaddresses
  involved in a payment on-chain.
* Scalability, since in the future netting of payments will be supported.

Installation & Testing
----------------------

For development we recommend working in a virtual environment populated
using ``pip install -r requirements.txt``. You can run tests using the ``pytest``
command from the root directory, and execute sample scripts in ``src\scripts``.

To install :py:mod:`offchainapi` follow these steps:

* Execute ``git clone`` to clone the repository (https://github.com/calibra/off-chain-api).
* Execure ``tox`` within the root directory run all tests. This will also run coverage tests and create a ``htmlcov`` directory with line by line coverage results in HTML.
* Execute ``python setup.py install`` from the root directory to install to an environment.
* Execute ``make html`` within the ``docs`` directory to build the Sphinx API docs.

Where to start
--------------

We suggest that you explore the API in the following order:

* :py:mod:`offchainapi.payment` -- defines the PaymentObject and subobjects that allow VASPs to define payments.
* :py:mod:`offchainapi.payment_command` -- Defines the basic PaymentCommand that thinly wraps the PaymentObject.
* :py:mod:`offchainapi.business` -- Allow the VASP to handle the protocol flow by providing an interface to its backend operations.
* :py:mod:`offchainapi.core` -- Defines the core ``VASP`` object that allows a basic VASP to operate using the default network and storage.

Architecture
------------

API Reference
=============

.. toctree::
   :maxdepth: 4
   :caption: Contents:

   _source/modules.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
