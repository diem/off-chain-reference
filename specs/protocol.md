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

* **HTTP end-points**: Each VASP exposes an HTTP POST end point at
`https://hostname:port\localVASPAddress\RemoteVASPAddress\process`. It receives `CommandRequestObject`s in the POST body, and responds with `CommandResponseObjects`s in the HTTP response. Single command requests-responses are supported (HTTP1.0) but also pipelined request-responses are supported (HTTP1.1).
* **Serialization to JSON**: All transmitted structures, nested within `CommandRequestObject` and `CommandResponseObject` are valid JSON serialized objects and can be parsed and serialized using standard JSON libraries.
* **Random strings**: We assume that payment reference IDs and object versions are generated as cryptographically strong random strings. These should be at least 16 bytes long and encoded to string in hexadecimal notation using characters in the range[A-Za-z0-9].

TODO Determine after discussion with partners:

* Transport security: authentication and encryption.
* Signatures

## Interface to Libra

The Off-chain protocol interacts with the Libra Blockchain in a narrow and very specific set of ways:

* **Address Format**. It uses `LibraAddress`: The Hex encoded address of the VASP. Note this may be a sub-address, since a VASP may operate from many addresses on-chain. Using multiple addresses allows two VASPs to open multiple channels between each other, possible from multiple hosts, allowing for higher throughputs. However, care should be taken to either shard customer accounts per on-chain address or carefully synchronize operations on accounts to prevent them becoming inconsistent due to multiple concurrent accesses and unsynchronized updates.
* **VASP End-point discovery & Authentication information**. The Libra Blockchain is used to exchange authentication and addressing information in such a way that a VASP may open a channel to any other VASP and initiate an authenticated and encrypted HTTPs connection. This involves discovering the URLs for the all other VASPs.
* **Settlement Confirmation**. Given a `PaymentObject` that is ready for settlement, a VASP is able to create a payment within the Libra Blockchain to settle the payment, or observe the Libra Blockchain and confirm whether the payment has been settled. The on-chain payment settling an off-chain payment will contain a signed variant of the Reference ID of the off-chain payment.
* **Payment reference ID & Recipient VASP signatures**. The Libra Blockchain value transfer contact is able to verify that a signature on the reference ID of an on-chain payment is valid (and that signature is provided through the off-chain protocol.)

The Off-chain protocol could be adapted to be used with other Blockchains as long as address format, authentication and network endpoint discovery, and settlement confirmation can be done for these other chains. The inclusion of a signed reference identifier is a Libra specific feature, and other chains may or may not use it depending on their own compliance strategy.


## Command Sequencing Protocol

The low-level Off-Chain protocol allows two VASPs to sequence commands originating
from either VASP and responses to those commands, in order to maintain a
consistent database of shared objects. Specifically, the commands sequenced are PaymentCommands, each defining or updating a PaymentObject. Sequencing a command requires both VAPSs to confirm it is valid, as well as its sequence in relation to other commands.

### VASP State

Each VASP state consists of the following information:

* An ordered list of **local requests** it has sent (of type `CommandRequestObject`) to the other VASP.
* An ordered list of **local request responses** (of type `CommandResponseObject`) it has received from the other VASP.
* An ordered list of **remote requests** (`CommandRequestObject`) it has received from the other VASP, along with the **remote request responses** (of type `CommandResponseObject`) it has sent to the other VASP.
* A **joint sequence of commands** (including all fields of `ProtocolCommand`) representing commands that have been sequenced by both VASPs, a `success` flag for each denoting whether they were successful of not.
* A set of **available shared object version** representing the objects that are jointly available and can have future commands applied to them.

### Server and Client role

 In each channel one VASP takes the role of a `server` and the other the role of a `client` for the purposes of sequencing commands into a joint command sequence. Who is the server and who is the client VASP is determined by comparing their binary LibraAddress.

By convention the server always determines the sequence of a request in the joint command sequence. When the server creates a CommandRequestObject it already assigns it a `command_seq` in the joint sequence of commands. When it responds to requests from the client its `CommandResponseObject` contains a `command_seq` for the request into the joint command sequence.

### `CommandRequestObject` messages.

An example `CommandRequestObject` serialized message from a server role VASP to a client role VASP is:

    {
        "_ObjectType": "CommandRequestObject",
        "command_type": "PaymentCommand",
        "seq": 0
        "command": { ... },
        "command_seq": 0,
    }

Such a `CommandRequestObject` contains the following fields.

| Field 	| Type 	| Required? 	| Description 	|
|-------	|------	|-----------	|-------------	|
| _ObjectType| str| Y | Fixed value: `CommandRequestObject`|
|command_type | str| Y |A string representing the type of command contained in the request. |
|seq | int  | Y | The sequence of this request in the sender local sequence. |
| command | `ProtocolCommand` sub-structure | Y | The command to sequence. |
|command_seq    | int | Server   | The sequence of this command in the joint command sequence, only set if the server is the sender. |

### `CommandResponseObject` messages.

    {
        "_ObjectType": "CommandResponseObject",
        "seq": 0,
        "command_seq": 0,
        "status": "success"
    }

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
|_ObjectType    | str   | Y             |The fixed string `CommandResponseObject`. |
|seq            |int    | Y             | The sequence number of the request responded to in the local sender request sequence. |
| command_seq   | int or str=`null`   | Y             | The sequence of the command responded to in the joint command sequence |
|status         | str   | Y             | Either `success` or `failure`. |

When the `CommandRequestObject` status field is `failure`, the `error` field is included in the response to indicate the nature of the failure. The `error` field (type `OffChainError`) is an object with at least two fields. For example:

    {
        "_ObjectType": "CommandResponseObject",
        "command_seq": null,
        "error": {
            "code": "conflict",
            "protocol_error": true
        },
        "seq": 0,
        "status": "failure"
    }

The `OffChainError` fields are:

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| protocol_error| bool  | Y             | Set 'true' for protocol error, and 'false' for command errors |
| code | str |  Y | A code giving more information about the nature of the error |

Protocol errors may result in the command not being sequenced or not being immediately sequenced. Command errors on the other hand indicate that the command was sequenced but an error occurred at a higher abstraction level preventing its successful completion.

Specific protocol errors include by `code`:

- `wait` indicates that the VASP is not
    ready to process the request yet. The `command_seq` may be `null` since no sequencing took place.
- `missing` indicates that the request has arrived out of order and a previous request from the sender has not yet been received or processed. The `command_seq` may be `null` since no sequencing took place.
- `conflict` indicates that a request from the sender has already been received and processed, and that the previous request was different than the one re-submitted. This indicates a bug usually at the sender.

### The `ProtocolCommand` basic information

All commands contained in a `CommandRequestObject` need to contain the following fields at the very least:

    {
        "_ObjectType": "PaymentCommand",
        "_creates_versions": [ "VHHAGGEKKDSHH" ],
        "_dependencies":     [ "JJKEIIBBBFSJJ" ],
        ...
    }

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| _ObjectType   | str  | Y             | A string representing the type of command. Set to `PaymentCommand` for payment commands. |
| _creates_versions | list of str |  Y | A list of strings denoting the versions of all new objects created by this command. For `PaymentCommand` this list only includes a single item which is the version of the new payment or updated payment. |
| _dependencies | list of str | Y | A list of past object versions (can be empty, i.e. `[]`) that are required for this command to succeed. |
| ... | various | Y | Any other fields defined by this command type.

### The sequencing protocol & state machine

Each VASP receives `CommandRequestObjects` on an open server port, in the body of HTTP POST commands, and responds to them through `CommandResponseObjects` in the body of HTTP responses.

A `CommandRequestObjects` can be processed immediately if:

* At a server VASP all local requests have already received a response from the client VASP. (If not a protocol error response with code `wait` may be generated and sent back.)
* The Request is the next request in the remote request sequence. All previous remote requests have already been assigned success or failure responses. (If not a protocol error with code `missing` may be generated and sent back.)
* The Request has the same sequence number and contents with a previous one. In this case the same response must be sent back. (If the sequence number matches but the command is different a `conflict` protocol error must be sent back.)

Once a `CommandRequestObjects` can be processed its sequence number in the joint command sequence can be determined. In case the server is processing a client request it should assign it the next sequence number in the command sequence, and include it in the `command_seq` field of the response. In case the client is processing a server request it will find its sequence number in the `command_seq` field included in the request.

If a protocol error is not generated then the request is sequenced into the joint command sequence, and the VASP needs to determine if it is a success or a command failure. This is done by processing commands in order, and applying checks to
determine the success or failure of a command:

* If any object versions in the `_dependencies` list of the command are not available the command is a failure. If they are all available they become unavailable (successful commands consume the version of the objects on which they depend) and the object versions in the list of `_creates_versions` become available.
* Any custom checks specific to the command type may be applied at this point. We discuss specific checks that should be applied for the `PaymentCommand` type in the next sections. However, those checks are synchronous and delay the execution of subsequent commands, and therefore should be efficient.

Once the success or failure of a request has been established the VASP constructs a CommandResponseObject with the remote sequence number, the joint sequence number and the outcome of the command and sends it back to the other VASP in the body of the HTTP response.

Depending on the nature of the HTTP request, responses may be received out of order by a VASP. They should however be processed in a strict order:

* Protocol failures can be processed in any order. Those indicate either the need for a delay or a conflict.
* Success or Command failure responses must be processed strictly in the order of the included `command_seq` in the final joint sequence. This is indicated in the response.

**Implementation Note:** Both requests and responses need to be processed in a specific order to ensure that the joint objects remain consistent. However, an implementation may chose to buffer out-of-order requests and responses, for later when they become eligible for processing, rather than immediately responding with a protocol error of type `wait` or `missing`. This limits the need for retransmissions saving on bandwidth costs and reducing latency -- and in practice limits the use of the `wait` or `missing` protocol errors to cases when message caches are full.

However, to ensure compatibility with simple implementation as well as crash recovery all implementations should be capable of re-transmitting requests that that returned a `wait` or `missing` protocol error, and also re-issue commands from the local sequence that have received no response after some timeout or upon reconnection with another VASP.

## PaymentCommand Data Structures and Protocol

### The `PaymentCommand` structure

The `PaymentCommand` structure represents the only type of command available in the initial version of the Off-chain protocol, and allows VASPs to create new, as well as modify existing shared `PaymentObject`s. As any `ProtocolCommand` it includes the `_ObjectType`, `_creates_versions`, `_dependencies` fields, and also a `diff` field containing a `PaymentObject` structure.

    {
        "_ObjectType": "PaymentCommand",
        "_creates_versions": [
            "08697804e12212fa1c979283963d5c71"
        ],
        "_dependencies": [],
        "diff": {
            ...
        }
    }

The meaning of those fields for a `PaymentCommand` is as follows:

- `_ObjectType` is the fixed string `PaymentCommand`.
- `_dependencies` can be an empty list or a list containing a single previous version. If the list is empty this payment command defines a new payment. If the list contains one item, then this command updates the shared `PaymentObject` with the given version. It is an error to include more versions, and it results in a command error response.
- `_creates_versions` must be a list containing a single str representing the version of the new or updated `PaymentObject` resulting from the success of this payment command. A list with any other number of items results in a command error.
- `diff` contains a `PaymentObject` that either creates a new payment or updates an existing payment. Note that strict validity check apply when updating payments, that are listed in the section below describing these objects. An invalid update or initial payment object results in a command error.

### The `PaymentObject` Structure.

The `diff` field of a `PaymentCommand` contains a number of fields that define or update a `PaymentObject`. An example `PaymentObject` with all fields understood by the Off-Chain protocol (besides KYC) is illustrated here:

    {
        "action": {
            "action": "charge",
            "amount": 10,
            "currency": "TIK",
            "timestamp": "2020-01-02 18:00:00 UTC"
        },
        "description": "Custom payment description ...",
        "original_payment_reference_id": "Original Payment reference identifier ...",
        "receiver": {
            "address": "42424242424242424242424242424242",
            "kyc_certificate": "42424242424242424242424242424242.ref 9.KYC_CERT",
            "kyc_data": {
                "blob": "{\n  \"payment_reference_id\": \"42424242424242424242424242424242.ref 9.KYC\",\n  \"type\": \"person\"\n}\n"
            },
            "kyc_signature": "42424242424242424242424242424242.ref 9.KYC_SIGN",
            "metadata": [],
            "status": "ready_for_settlement",
            "subaddress": "BobsSubaddress"
        },
        "recipient_signature": "42424242424242424242424242424242.ref 9.SIGNED",
        "reference_id": "HHAYJKDKSUUUSGGH",
        "sender": {
            "address": "41414141414141414141414141414141",
            "kyc_certificate": "41414141414141414141414141414141.ref 9.KYC_CERT",
            "kyc_data": {
                "blob": "{\n  \"payment_reference_id\": \"41414141414141414141414141414141.ref 9.KYC\",\n  \"type\": \"person\"\n}\n"
            },
            "kyc_signature": "41414141414141414141414141414141.ref 9.KYC_SIGN",
            "metadata": [],
            "status": "ready_for_settlement",
            "subaddress": "AlicesSubaddress"
        }
    }

**Allowed state transitions:**

## Example Protocol Flows

# Programing & Integration Interface

# References

[1] FATF Travel Rule.

### Glosary

- VASP
- On-Chain
