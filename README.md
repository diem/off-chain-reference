# off-chain-reference

The Diem Off-Chain API, as proposed in [DIP-1](https://dip.diem.com/dip-1), is a protocol that allows participants on the Diem Payment Network, such as designated dealers or Virtual Asset Service Providers (VASPs)) to support the following business needs when integrating with the Diem blockchain:
* Compliance, by providing the ability to exchange Know-Your-Customer (KYC) information about payer and payee.
* Privacy, by allowing for the private exchange of information that cannot be achieved on-chain.
* Scalability, by facilitating the netting of payments when this is supported in the future.

The following are reference implementations of the off-chain API protocol service built on top of the [Diem Python Client SDK](https://github.com/diem/client-sdk-python):
* [Diem Python Client SDK Wallet Example Service](https://github.com/diem/client-sdk-python/blob/master/examples/vasp/wallet.py): this is a highly simplified example of a wallet backend server implementation (no UI, no database, no un-related APIs) for demonstrating building off-chain API services through the Python SDK off-chain module.
* [Diem Wallet Reference Off-chain Service](https://github.com/diem/reference-wallet/blob/master/backend/wallet/services/offchain.py): this is a reference wallet implementation for the Diem blockchain. This off-chain service module demonstrates how to integrate off-chain service APIs into a wallet application API and database.

The above 2 example implementations demonstrate high-level business APIs and integration with a wallet application; for low level protocol details / implementations, please refer to [Diem Python SDK offchain module API document](https://diem.github.io/client-sdk-python/diem/offchain/index.html).
