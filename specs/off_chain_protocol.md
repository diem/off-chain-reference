# Overview: Off-Chain Protocol

The Off-Chain protocol is an API and payload specification to support compliance, privacy and scalability on blockchains.
It is executed between pairs of _Virtual Asset Service Providers_ (VASPs),
such as wallets, exchanges or designated dealers and allows them to privately exchange payment information
before, while, or after settling it on a Blockchain.

The initial use-case for the Off-Chain protocol relates to _supporting compliance_, and in particular the implementation of the _Travel Rule_ recommendation by the FATF [1]. Those recommendations specify that when money transfers above a certain amount are executed by VASPs, some information about the sender and recipient of funds must become available to both VASPs. The Off-Chain protocols allows VASPs to exchange this information privately.

A secondary use-case for the Off-Chain protocol is to provide higher levels of privacy than those that can be achieved directly on a Blockchain. The exact details of the customer accounts involved in a payment, as well as any personal information that needs to be exchanged to support compliance, remain off-chain. They are exchanged within a secure, authenticated and encrypted, channel and only made available to the parties that strictly require them.

Next: [Design Principles](design_principles.md)

