# Calibra Off-Chain Protocol & Specification

## Introduction

The Calibra Off-Chain protocol supports compliance, privacy and scalability in the Libra eco-system.
It is executed between pairs of _Virtual Asset Service Providers_ (VASPs),
such as wallets, exchanges or designated dealers and allows them to privately exchange information
about a payment
before, while or after, settling it in the Libra Blockchain.

This document describes both the rationale
of the Off-Chain protocol and the use-cases covered. It then provides
a technical specification for other services to interoperate and build independent
implementations.

An open source implementation of the Off-Chain Protocols is available at: https://github.com/calibra/off-chain-api .

### Protocol Outline

An instance, or _channel_, of the Off-Chain protocol runs between two VASPs. It allows them to define _Shared Objects_, specifically representing _PaymentObjects_, and execute _ProtocolCommands_, and specifically _PaymentCommands_, on those objects to augment them with additional information. One VASP initiate a payment by defining a shared PaymentObject in the channel, and then both VASPs can augment the object by requesting and providing more information until they are ready to settle it on the Libra Blockchain. The VASP sending funds then puts a Libra transaction corresponding to the PaymentObject into the Libra network. Once this transaction is successful, both VASPs can use the Off-chain protocol to indicate the payment is settled.

### High-Level Use Cases

The Off-chain protocol immediately supports a number of use-cases:

**Compliance.** The initial use-case for the Off-Chain protocol relates to _supporting compliance_, and in particular the implementation of the _Travel Rule_ recommendation by the FATF [1]. Those recommendations specify that when money transfers above a certain amount are executed by VASPs, some information about the sender and recipient of funds must become available to both VASPs. The Off-Chain protocols allows VASPs to exchange this information privately.

**Privacy**. A secondary use-case for the Off-Chain protocol is to provide higher levels of privacy than those that can be achieved directly on the Libra Blockchain. The exact details of the customer accounts involved in a payment, as well as any personal information that needs to be exchanged to support compliance, remain off-chain. They are exchanged within a secure, authenticated and encrypted, channel and only made available to the parties that strictly require them.

**Loose Coupling**. While the Off-Chain protocol is designed to support the Libra Blockchain and its ecosystem it makes few and well defined assumptions about the Libra Blockchain environment, which can instead be fulfilled by other Blockchains. The protocol can therefore be re-purposed to support compliance, privacy and scalability use-cases between VASPs in other Blockchains, as well as in multiple blockchains simultaneously.

The Off-Chain protocol has been architected to allow two further use-cases in the near future:

**Scalability**. In the initial version of the Off-chain protocol all off-chain PaymentObjects that are ready for settlement, are then settled individually (gross) through a separate Libra Blockchain transaction. However, the architecture of the Off-chain protocol allows in the future the introduction of netting batches of transactions, and settling all them them through a single Libra Blockchain transaction. This allows costs associated with multiple on-chain transactions to be kept low for VASPs, and allows for a number of user transactions or payment between VASPs that exceed the capacity of the Libra Blockchain.

**Extensibility**. The current Off-Chain protocols accommodate simple payments where a customer of a VASP sends funds to the customer of another VASP over a limit, requiring some additional compliance-related information. However, in the future the Libra eco-system will support more complex flows of funds between customers of VASPs as well as merchants. The Off-chain protocol can be augmented to support the transfer of rich meta-data relating to those flows between VASPs in a compliant, secure, private, scalable and extensible manner.

We describe a number of additional lower-level requirements throughout the remaining of the documents, such as ease of deployment through the use of established web technologies (like HTTP and JSON), tolerance to delays and crash-recovery failures of either VASPs, and compatibility with cryptography and serialization within the Libra MOVE language.

# Protocols

## Basic Building Blocks

* Networking: TCP, tolerate OOO Delivery
* HTTP end-points.
* Transport security: authentication and encryption.
* Signatures
* Random strings
* Serialization to JSON

## Interface to Libra

* `LibraAddress`: VASP account and parent VASP.
* Authentication data.
* Settlement Confirmation.
* Recipient VASP signatures.

## Command Sequencing Protocol

* `CommandRequestObject` messages.
* `CommandResponseObject` messages.
* `SharedObject` structures.
* The sequencing protocol & state machine.

## PaymentCommand Data Structures and Protocol

* `PaymentObject` Structure.
* The `PaymentCommand` structure.
* Allowed state transitions.

## Example Protocol Flows

# Programing & Integration Interface

# References

[1] FATF Travel Rule.

### Glosary

- VASP
- On-Chain
