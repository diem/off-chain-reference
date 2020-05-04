# Off-Chain API Protocol Protocol & Specification

## Introduction

The Calibra Off-Chain protocol supports compliance, privacy and scalability in the Libra eco-system.
The Off-chain protocols is run between pairs of _Virtual Asset Service Providers_ (VASPs),
such as wallets, exchanges or designated dealers. It allows them to privately exchange information
about a payment
before, while or after, settling it in the Libra Blockchain.

This document describes both the rationale
of the Off-Chain protocols and the use-cases they cover today and beyond. It then provides
a technical specification to allow services to interoperate and engineer independent
implementations.

### Protocol Outline

An instance, or _channel_, of the Off-Chain protocol runs between two VASPs. It allows them to define _Shared Objects_, specifically representing _PaymentObjects_, and execute _ProtocolCommands_, and specifically _PaymentCommands_, on those objects to augment them with additional information. One VASP initiate a payment by defining a shared PaymentObject in the channel, and then both VASPs can augment the object by requesting and providing more information until they are ready to settle it on the Libra Blockchain. The VASP sending funds then puts a Libra transaction corresponding to the PaymentObject into the Libra network. Once this transaction is successful, both VASPs can use the Off-chain protocol to indicate the payment is settled.

### High-Level Use Cases

The Off-chain protocol immediately supports a number of use-cases:

**Compliance.** The initial use-case for the Off-Chain protocol relates to _supporting compliance_, and in particular the implementation of the _Travel Rule_ recommendation by the FATF [1]. Those recommendations specify that when money transfers above a certain amount are executed by VASPs, some information about the sender and recipient of funds must become available to both VASPs. The Off-Chain protocols allows VASPs to exchange this information privately.

**Privacy**. A secondary use-case for the Off-Chain protocol is to provide higher levels of privacy than those that can be achieved directly on the Libra Blockchain. The exact details of the customer accounts involved in a payment, as well as any personal information that needs to be exchanged to support compliance, remain off-chain. They are exchanged within a secure, authenticated and encrypted, channel and only made available to the parties that strictly require them.

The Off-Chain protocol has been architected to allow two further use-cases in the near future:

**Scalability**. In the initial version of the Off-chain protocol all off-chain PaymentObjects that are ready for settlement, are then settled individually (gross) through a separate Libra Blockchain transaction. However, the architecture of the Off-chain protocol allows in the future the introduction of netting batches of transactions, and settling all them them through a single Libra Blockchain transaction. This allows costs associated with multiple on-chain transactions to be kept low for VASPs, and allows for a number of user transactions or payment between VASPs that exceed the capacity of the Libra Blockchain.

**Extensibility**. The current Off-Chain protocols accommodate simple payments where a customer of a VASP sends funds to the customer of another VASP over a limit, requiring some additional compliance-related information. However, in the future the Libra eco-system will support more complex flows of funds between customers of VASPs as well as merchants. The Off-chain protocol can be augmented to support the transfer of rich meta-data relating to those flows between VASPs in a compliant, private, scalable and extensible manner.

# Protocols

## Basic Datatypes and Primitives

* Networking: TCP, tolerate OOO Delivery
* JSON & HTTP
* Signatures
* Random strings

## Interface to Libra

* Information and transactions

## Command Sequencing Protocol

* `CommandRequestObject`
* `CommandResponseObject`

## PaymentCommand Data Structures and Protocol

* `PaymentCommand`

# References

[1] FATF Travel Rule.

### Glosary

- VASP
- On-Chain
