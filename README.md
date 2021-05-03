# off-chain-reference

The Diem Off-Chain API, as proposed in [DIP-1](https://dip.diem.com/dip-1), is a protocol that allows participants on the Diem Payment Network, such as designated dealers or Virtual Asset Service Providers (VASPs)) to support the following business needs when integrating with the Diem blockchain:
* Compliance, by providing the ability to exchange Know-Your-Customer (KYC) information about payer and payee.
* Privacy, by allowing for the private exchange of information that cannot be achieved on-chain.
* Scalability, by facilitating the netting of payments when this is supported in the future.

Please refer to [Diem Mini-Wallet application](https://diem.github.io/client-sdk-python/diem/testing/miniwallet/app/app.html#diem.testing.miniwallet.app.app.OffChainAPI) for implementation example.

For trying out Mini-wallet, please refer to [this doc](https://github.com/diem/client-sdk-python/blob/master/mini-wallet.md).

For low level protocol details / implementations, please refer to [Diem Python SDK offchain module API document](https://diem.github.io/client-sdk-python/diem/offchain/index.html).
