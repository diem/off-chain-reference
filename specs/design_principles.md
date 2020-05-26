# Off-Chain Protocal Design Principles

**Scalability**. In the initial version of the Off-chain protocol all off-chain PaymentObjects that are ready for settlement, are then settled individually (gross) through a separate Blockchain transaction. However, the architecture of the Off-chain protocol allows in the future the introduction of netting batches of transactions, and settling all of them through a single Blockchain transaction. This allows costs associated with multiple on-chain transactions to be kept low for VASPs, and allows for a number of user transactions or payment between VASPs that exceed the capacity of the underlying Blockchain. Additionally, batches enhance privacy via hiding the number of transactions between VASPs and by only placing a single on-chain transaction which hides the individual transaction amounts.

**Extensibility**. The current Off-Chain protocols accommodate simple payments where a customer of a VASP sends funds to the customer of another VASP over a limit, requiring some additional compliance-related information. However, in the future the blockchains may support more complex flows of funds between customers of VASPs as well as merchants. The Off-chain protocol can be augmented to support the transfer of rich meta-data relating to those flows between VASPs in a compliant, secure, private, scalable and extensible manner.

**Generic Communication Framework**. The Off-Chain protocol is designed as a generic communication framework which can be utilized by any Blockchain and requires no ties to any specific blockchain. While the first usage of the Off-Chain protocol is within the Libra Blockchain, the Off-Chain protocol makes few and well defined assumptions about the underlying Blockchain environment, which can be fulfilled by other Blockchains. The Off-chain protocol can therefore be re-purposed to support compliance, privacy and scalability use-cases between VASPs in other Blockchains, as well as in multiple blockchains simultaneously.

We describe a number of additional lower-level requirements throughout the remaining of the documents, such as ease of deployment through the use of established web technologies (like HTTP and JSON), tolerance to delays and crash-recovery failures of either VASPs, and compatibility with common cryptography and serialization schemes.

Next: [Basic Building Blocks](basic_building_blocks.md)

Previous: [Overview](off_chain_protocol.md)
