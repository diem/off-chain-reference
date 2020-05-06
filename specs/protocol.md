# Libra Off-Chain Protocol & Specification

## Introduction

The Libra Off-Chain protocol supports compliance, privacy and scalability in the Libra eco-system.
It is executed between pairs of _Virtual Asset Service Providers_ (VASPs),
such as wallets, exchanges or designated dealers and allows them to privately exchange information
about a payment
before, while or after, settling it on the Libra Blockchain.

This document describes the purpose
of the Off-Chain protocol and the use-cases it covers. It also provides
a technical specification so that others may interoperate and build independent
implementations.

An open source implementation of the Off-Chain Protocols is available at: https://github.com/calibra/off-chain-api .

### Protocol Outline

An instance, or _channel_, of the Off-Chain protocol runs between two VASPs. It allows them to define _Shared Objects_, specifically representing _PaymentObjects_, and execute _ProtocolCommands_, and specifically _PaymentCommands_, on those objects to augment them with additional information. Each ProtocolCommand involves the initiating VASP sending a _CommandRequestObject_ to the other VASP, which responds with a _CommandResponseObject_ with a success or failure code.

One VASP initiate a payment by defining through a command a shared PaymentObject in the channel. Then both VASPs augment the object by requesting and providing more information until they are ready to settle it on the Libra Blockchain. The VASP sending funds then puts a Libra transaction corresponding to the PaymentObject into the Libra network. Once this transaction is successful, both VASPs can use the Off-chain protocol to indicate the payment is settled.

### High-Level Use Cases

The Off-chain protocol immediately supports a number of use-cases:

**Compliance.** The initial use-case for the Off-Chain protocol relates to _supporting compliance_, and in particular the implementation of the _Travel Rule_ recommendation by the FATF [1]. Those recommendations specify that when money transfers above a certain amount are executed by VASPs, some information about the sender and recipient of funds must become available to both VASPs. The Off-Chain protocols allows VASPs to exchange this information privately.

**Privacy**. A secondary use-case for the Off-Chain protocol is to provide higher levels of privacy than those that can be achieved directly on the Libra Blockchain. The exact details of the customer accounts involved in a payment, as well as any personal information that needs to be exchanged to support compliance, remain off-chain. They are exchanged within a secure, authenticated and encrypted, channel and only made available to the parties that strictly require them.

The Off-Chain protocol has been architected to allow two further use-cases in the near future:

**Scalability**. In the initial version of the Off-chain protocol all off-chain PaymentObjects that are ready for settlement, are then settled individually (gross) through a separate Libra Blockchain transaction. However, the architecture of the Off-chain protocol allows in the future the introduction of netting batches of transactions, and settling all of them through a single Libra Blockchain transaction. This allows costs associated with multiple on-chain transactions to be kept low for VASPs, and allows for a number of user transactions or payment between VASPs that exceed the capacity of the Libra Blockchain.

**Extensibility**. The current Off-Chain protocols accommodate simple payments where a customer of a VASP sends funds to the customer of another VASP over a limit, requiring some additional compliance-related information. However, in the future the Libra eco-system will support more complex flows of funds between customers of VASPs as well as merchants. The Off-chain protocol can be augmented to support the transfer of rich meta-data relating to those flows between VASPs in a compliant, secure, private, scalable and extensible manner.

**Loose Coupling**. While the Off-Chain protocol is designed to support the Libra Blockchain, and its ecosystem, it makes few and well defined assumptions about the Libra Blockchain environment, which can instead be fulfilled by other Blockchains. The Off-chain protocol can therefore be re-purposed to support compliance, privacy and scalability use-cases between VASPs in other Blockchains, as well as in multiple blockchains simultaneously.

We describe a number of additional lower-level requirements throughout the remaining of the documents, such as ease of deployment through the use of established web technologies (like HTTP and JSON), tolerance to delays and crash-recovery failures of either VASPs, and compatibility with cryptography and serialization within the Libra MOVE language.

# Protocols

## Basic Building Blocks

* **HTTP end-points**: Each VASP exposes an HTTP POST end point at
`https://hostname:port/localVASPAddress/RemoteVASPAddress/process`. It receives `CommandRequestObject`s in the POST body, and responds with `CommandResponseObjects`s in the HTTP response. Single command requests-responses are supported (HTTP1.0) but also pipelined request-responses are supported (HTTP1.1).
* **Serialization to JSON**: All transmitted structures, nested within `CommandRequestObject` and `CommandResponseObject` are valid JSON serialized objects and can be parsed and serialized using standard JSON libraries. The content type for requests and responses is set to `Content-type: application/json; charset=utf-8` indicating all content is JSON encoded.
* **Random strings**: We assume that object versions are generated as cryptographically strong random strings. These should be at least 16 bytes long and encoded to string in hexadecimal notation using characters in the range[A-Za-z0-9]. Payment `reference_id` are special in that they are structured to encode the creator of the payment.

TODO Determine after discussion with partners:

* Canonical serialization
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

The low-level Off-Chain protocol allows two VASPs to sequence request-responses for commands originating from either VASP, in order to maintain a
consistent database of shared objects. Specifically, the commands sequenced are PaymentCommands, defining or updating a PaymentObject. Sequencing a command requires both VAPSs to confirm it is valid, as well as its sequence in relation to other commands.

The basic protocol interaction consists of:

* An initiating VASP creates a `CommandRequestObject` containing a PaymentCommand, and sends it to the other VASP, in the body of an HTTP POST.
* The responding VASP listens for requests, and when received processes them to generate and send `CommandResponseObject` responses, with a success or failure status, through the HTTP response body.
* The initiating VASP receives the response and processes it to assess whether it was successful or not.

Both VASPs in a channel can asynchronously attempt to initiate and execute commands on shared objects. The purpose of the command sequencing protocols is to ensure that such concurrent requests are applied in the same sequence at both VASPs to ensure that the state of shared objects remains consistent.

### VASP State

Each VASP state consists of the following information:

* An ordered list of **local requests** it has initiated and sent (of type `CommandRequestObject`) to the other VASP.
* An ordered list of **local request responses** (of type `CommandResponseObject`) it has received from the other VASP. Each response in the list corresponds to the request in the same position in the **local requests** list.
* An ordered list of **remote requests** (`CommandRequestObject`) it has received from the other VASP, along with the **remote request responses** (of type `CommandResponseObject`) it has sent to the other VASP.
* A **joint sequence of commands** (including all fields of `ProtocolCommand`) representing commands that have been sequenced by both VASPs, a `success` flag for each denoting whether they were successful of not.
* A set of **available shared object version** representing the objects that are jointly available and can have future commands applied to them.

### Protocol Server and Client roles

In each channel one VASP takes the role of a _protocol server_ and the other the role of a _protocol client_ for the purposes of sequencing commands into a joint command sequence. Note that these roles are distinct to the HTTP client/server -- and both VASPs act as an HTTP server and client to listen and respond to requests.

Who is the protcol server and who is the client VASP is determined by comparing their binary LibraAddress. The following rules are used to determine which entity serves as which party: The last bit of VASP A’s parent address in binary _w_ is XOR’d with the last bit in VASP B’s parent address in binary _x_.  This results in either 0 or 1.
If the result is 0, the lower parent address is used as the server side.
If the result is 1, the higher parent address is used as the server side.

By convention the _server_ always determines the sequence of a request in the joint command sequence. When the server creates a `CommandRequestObject` it already assigns it a `command_seq` in the joint sequence of commands. When it responds to requests from the client, its `CommandResponseObject` contains a `command_seq` for the request into the joint command sequence. The protocol client never assigns a `command_seq`, but includes one provided by the protocol server in its responses.

### `CommandRequestObject` messages.

VASPs define and operate on shared objects, and specifically PaymentObjects, through commands. Those commands are sequenced through the request-response protocol. A VASP that initiates a command packages it within a `CommandRequestObject`, sends it to the other VASP, and expects a response.

Multiple requests can be in-flight and pipelined, without the need to wait for previous ones to get a response. However, both requests and responses will be processed by VASPs in a specific order to ensure consistency (see the end of this section for details).

An example `CommandRequestObject` serialized message from a protocol server role VASP to a client role VASP is:

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

Since the initiator of the example request has a server role, for this channel, the `CommandRequestObject` contains a field `command_seq` with the sequence number of this command in the joint sequence of commands. A `CommandRequestObject` initiated by a protocol client role would omit the `command_seq` field, since the sequence number will be determined by the server processing the request and included in the response.

### `CommandResponseObject` messages.

A VASP listens for commands within `CommandRequestObject` structures, processes them in order (see below) and responds to them through `CommandResponseObject` messages.

For example, a successful request may yield the following `CommandResponseObject`:

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
- `parsing` indicates a JSON or higher-level parsing error.

For command errors the `code` field provides a long description of the error.

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

### Ordering or Message Processing

Each VASP receives `CommandRequestObjects` on an open server port, in the body of HTTP POST commands, and responds to them through `CommandResponseObjects` in the body of HTTP responses. Such requests and responses may be received asynchronously with respect to each other, but should be processed in a specific order.

A `CommandRequestObjects` can be processed if:

* At a server VASP all local requests have already received a response from the client VASP. (If not a protocol error response with code `wait` may be generated and sent back.). Otherwise the protocol server waits for all responses to be received first.
* The Request is the next request in the remote request sequence. All previous remote requests have already been assigned success or failure responses. (If not a protocol error with code `missing` may be generated and sent back.)
* The Request has the same sequence number and contents as a previous one. In this case the same response must be sent back. (If the sequence number matches but the command is different a `conflict` protocol error must be sent back.)

Once a `CommandRequestObjects` can be processed its sequence number in the joint command sequence can be determined. In case the protocol server is processing a client request it should assign it the next sequence number in the command sequence, and include it in the `command_seq` field of the response. In case the protocol client is processing a server request it will find its sequence number in the `command_seq` field included in the request.

If a protocol error is not generated then the request is sequenced into the joint command sequence, and the VASP needs to determine if it is a success or a command failure. This is done by processing commands in order, and applying checks to
determine the success or failure of a command:

* Parsing errors result in a protocol failure with code `parsing`.
* If any object versions in the `_dependencies` list of the command are not available the command is a failure. If they are all available they become unavailable (successful commands consume the version of the objects on which they depend) and the object versions in the list of `_creates_versions` become available.
* Any custom checks specific to the command type may be applied at this point. We discuss specific checks that should be applied for the `PaymentCommand` type in the next sections. However, those checks are synchronous and delay the execution of subsequent commands, and therefore should be efficient.

Once the success or failure of a request has been established the VASP constructs a `CommandResponseObject` with the remote sequence number, the joint sequence number and the outcome of the command and sends it back to the other VASP in the body of the HTTP response.

Depending on the nature of the HTTP request, responses may be received out of order by a VASP. They should however be processed in a strict order:

* Protocol failures can be processed in any order. Those indicate either the need for a delay or an unrecoverable error for the command.
* Success or Command failure responses must be processed strictly in the order of the included `command_seq` in the final joint sequence. This is indicated in the response.

**Implementation Note:** Both requests and responses need to be processed in a specific order to ensure that the joint objects remain consistent. However, an implementation may chose to buffer out-of-order requests and responses. It can then process them later when they become eligible, rather than immediately responding with a protocol error of type `wait` or `missing`. This limits the need for retransmissions saving on bandwidth costs and reducing latency -- and in practice limits the use of the `wait` or `missing` protocol errors to cases when message caches are full.

However, to ensure compatibility with simple implementation as well as crash recovery all implementations should be capable of re-transmitting requests that returned a `wait` or `missing` protocol error, and also re-issue commands from the local sequence that have received no response after some timeout or upon reconnection with another VASP.

## PaymentCommand Data Structures and Protocol

The sequencing protocol is concretely used to define shared objects of type `PaymentObject` defining payments, through `PaymentCommands` to create and mutate those objects. We describe in this section the structure of such payment commands and objects.

### The `PaymentCommand` structure

The `PaymentCommand` structure represents the only type of command available in the initial version of the Off-chain protocol, and allows VASPs to create new, as well as modify existing shared `PaymentObject`s. As any `ProtocolCommand` it includes the `_ObjectType`, `_creates_versions`, `_dependencies` fields, and also a `diff` field containing a `PaymentObject` structure.

    {
        "_ObjectType": "PaymentCommand",
        "_creates_versions": [
            "08697804e12212fa1c979283963d5c71"
        ],
        "_dependencies": [],
        "payment": {
            ...
        }
    }

The meaning of those fields for a `PaymentCommand` is as follows:

- `_ObjectType` is the fixed string `PaymentCommand`.
- `_dependencies` can be an empty list or a list containing a single previous version. If the list is empty this payment command defines a new payment. If the list contains one item, then this command updates the shared `PaymentObject` with the given version. It is an error to include more versions, and it results in a command error response.
- `_creates_versions` must be a list containing a single str representing the version of the new or updated `PaymentObject` resulting from the success of this payment command. A list with any other number of items results in a command error.
- `payment` contains a `PaymentObject` that either creates a new payment or updates an existing payment. Note that strict validity check apply when updating payments, that are listed in the section below describing these objects. An invalid update or initial payment object results in a command error.

The structure in the `payment` field can be a full payment of just the fields of an existing payment object that need to be changed. Some fields are immutable after they are defined once (see below). Others can by updated multiple times. Updating immutable fields with a different value results in a command error, but it is acceptable to re-send the same value.

### The `PaymentObject` Structure.

The `payment` field of a `PaymentCommand` contains a number of fields that define or update a `PaymentObject`.

An example `PaymentObject` with all fields understood by the Off-Chain protocol is illustrated here:

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
                "blob": "{\n  \"payment_reference_id\": \"42424242424242424242424242424242.ref 9.KYC\",\n  \"type\": \"individual\"\n ... }\n"
            },
            "kyc_signature": "42424242424242424242424242424242.ref 9.KYC_SIGN",
            "metadata": [],
            "status": "ready_for_settlement",
            "subaddress": "BobsSubaddress"
        },
        "recipient_signature": "42424242424242424242424242424242.ref 9.SIGNED",
        "reference_id": "41414141414141414141414141414141_HHAYJKDKSUUUSGGH",
        "sender": {
            "address": "41414141414141414141414141414141",
            "kyc_certificate": "41414141414141414141414141414141.ref 9.KYC_CERT",
            "kyc_data": {
                "blob": "{\n  \"payment_reference_id\": \"41414141414141414141414141414141.ref 9.KYC\",\n  \"type\": \"individual\"\n ... }\n"
            },
            "kyc_signature": "41414141414141414141414141414141.ref 9.KYC_SIGN",
            "metadata": [],
            "status": "ready_for_settlement",
            "subaddress": "AlicesSubaddress"
        }
    }

In the next sections we discuss each part of the PaymentObject structure, including what checks are necessary when creating new PaymentObjects or updating existing ones.

## Object Definition: Top-level `PaymentObject`

The top-level `PaymentObject` is the root structure defining a payment and consists of the following fields:

    {
        "sender": payment_actor_object(),
        "receiver": payment_actor_object(),
        "reference_id": "123456abcd_12345",
        "original_payment_reference_id": "1234",
        "recipient_signature": "123445667",
        "action": payment_action_object(),
        "description": "",
    }

The `sender`, `receiver`, `reference_id`, and `action` are mandatory. The other fields are optional.

* **sender/receiver (PaymentActorObject)** Information about the sender/receiver in this payment. (Mandatory for a new payment, see `PaymentActorObject`).

* **reference_id (str)** Unique reference ID of this payment on the payment initiator VASP (the VASP which originally created this payment object). This value should be unique, and formatted as “<creator_vasp_address_hex>_<unique_id>”.  For example, ”123456abcd_12345“. This field is mandatory on payment creation and immutable after that.

* **original_payment_reference_id (str)**
Used for updates to a payment after it has been committed on chain. For example, used for refunds. The reference ID of the original payment will be placed into this field. This value is optional on payment creation and can only be written once after that.

* (TODO) **recipient_signature (str)**
Signature of the recipient of this transaction. The signature is over the `reference_id` and is signed with a key that chains up to its VASP CA. This key does not need to be the actual account key.  This is the base64 encoded string of the signature.

* **description (str)** Description of the payment. To be displayed to the user. Unicode utf-8 encoded max length of 255 characters. This field is optional but can only be written once.

* **action (PaymentAction)** Number of Libra + currency type (LibraUSD, LibraEUR, etc.). This field is mandatory and immutable (see `PaymentActionObject`).

### Object Definition: `PaymentActorObject`

A `PaymentActorObject` represents a participant in a payment - either sender or receiver. It also includes the status of the actor, that indicates missing information or willingness to settle or abort the payment, and the Know-Your-Customer information of the customer involved in the payment:

    {
        "address": "abcd1278",
        "subaddress": "1234567",
        "stable_id": "777",
        "kyc_data": kyc_data_object(),
        "kyc_signature": "abcd",
        "kyc_certificate": "deadbeef",
        "status": "ready_for_settlement",
        "metadata": [],
    }

* **address (str)**
Address of the VASP which is sending/receiving the payment. This is the Hex encoded LibraAddress of the VASP. Mandatory and immutable.

* **subaddress (str)** Subaddress of the sender/receiver account. Subaddresses may be single use or valid for a limited time, and therefore VASPs should not rely on them remaining stable across time or different VASP addresses. Mandatory and immutable.

* (TODO) **kyc_signature: string**
Standard base64 encoded signature over the KYC data (plus the ref_id).  Signed by the party who provides the KYC data. Note that the KYC JSON object already includes a field about the payload type and version which can be used for domain separation purposes, so no prefix/salt is required during signing.
**kyc_certificate: string**
Standard base64 encoded bytes of the X509 certificate for the VASP’s KYC public key, along with a signature chaining to the VASP’s CA.  This certificate is a standard X509 certificate, and will include the algorithm of the key.  The consumer of this message should verify that the kyc_certificate chains up to the root Association CA by way of the VASP CA (already have this from mTLS connection), and if successful use the public key and algorithm specified in the certificate to verify the KYC signature.
**kyc_data: KycDataObject**
The KYC data for this account.

* **status (str enum)**
Status of the payment from the perspective of this actor. This field can only be set by the respective sender/receiver VASP and represents the status on the sender/receiver VASP side. This field is mandatory and mutable. Valid values are:
    * `none` - No status is yet set from this actor.
    * `needs_kyc_data` - KYC data about the subaddresses is required by this actor.
    * `needs_recipient_signature` - Can only be associated with the sender actor.  Means that the sender still requires that the recipient VASP provide the signature so that the transaction can be put on-chain.
    * `ready_for_settlement` - Transaction is ready for settlement according to this actor (i.e. the required signatures/KYC data have been provided)
    * `settled` - Payment has been settled on chain and funds delivered to the subaddress
    * `abort` - Indicates the actor wishes to abort this payment, instead of settling it.

* **metadata: list of str** Can be specified by the respective VASP to hold metadata that the sender/receiver VASP wishes to associate with this payment. This is a mandatory field but can be set to an empty list (i.e. `[]`). New string-typed entries can be appended at the end of the list, but not deleted.

### Object Definition: `KYCDataObject`

The `KYCDataObject` is serialized as a string and contained in the `blob` attribute of an object in the `kyc_data` field of a `PaymentObject` (see the example payment at the top of this section). The reason we store KYC data in a serialized manner is that VASPs must check signatures on them, and therefore we need to maintain binary transparency (which is not provided by many HTTP/JSON frameworks). The `blob` field must parse to a valid JSON object of type `KYCDataObject`.

(TODO) A `KYCDataObject` represents the KYC data for a single subaddress. This should be in canonical JSON format to ensure repeatable hashes of JSON-encoded data.

    {
        "payment_reference_id": "ID",
        "payload_type": "KYC_DATA",
        "payload_version": 1,
        "type": "individual",
        "given_name": "ben",
        "surname": "mauer",
        "address": {
            "city": "Sunnyvale",
            "country": "US",
            "line1": "1234 Maple Street",
            "line2": "Apartment 123",
            "postal_code": "12345",
            "state": "California",
        },
        "dob": "1920-03-20",
        "place_of_birth": {
            "city": "Sunnyvale",
            "country": "US",
            "postal_code": "12345",
            "state": "California",
        }
        "national_id": {
        },
        "legal_entity_name": "Superstore",
    }


* **payment_reference_id (string)**
Reference_id of this payment. Used to prevent signature replays.

* **payload_type (string)**
Used to help determine what type of data this will deserialize into.  Always set to KYC_DATA.

* **payload_version (string)**
Version identifier to allow modifications to KYC data object without needing to bump version of entire API set

* **type (string)**
Required field, must be either “individual” or “entity”

* **given_name (string)**
Legal given name of the user for which this KYC data object applies.

* **surname (string)**
Legal surname of the user for which this KYC data object applies.

* **address (Object)**.
Address data for this account

* **dob: string** Date of birth for the holder of this account.  Specified as an ISO 8601 calendar date format: https://en.wikipedia.org/wiki/ISO_8601

* **place_of_birth (object)**
Place of birth for this user.  line1 and line2 fields should not be populated for this usage of the address object.

* **national_id (object)**
National ID information for the holder of this account

* **legal_entity_name (string)**
Name of the legal entity

### Object Definition: `NationalIDObject`

Represents a national ID

    {
        "id_value": "123-45-6789",
        "country": "US",
        "type": "SSN",
    }

* **id_value (string)**
Required field, indicates the national ID value.  For example, a social security number

* **country (string)**
Optional field for two-letter country code (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)

**type (string)**
Optional field to indicate the type of ID

### Object Definition: `AddressObject`

Represents an address

    {
        "city": "Sunnyvale",
        "country": "US",
        "line1": "1234 Maple Street",
        "line2": "Apartment 123",
        "postal_code": "12345",
        "state": "California",
    },

* **city (string)**
Optional field for the city, district, suburb, town, or village

* **country (string)**
Optional field for two-letter country code (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)

* **line1 (string)**
Optional field for address line 1

* **line2 (string)**
Optional field for address line 2 - apartment, unit, etc.

* **postal_code (string)**
Optional field for ZIP or postal code

* **state (string)**
Optional field for state, county, province, region.

### Object Definition: `PaymentActionObject`

Represents a payment action.

    {
        "amount": 100,
        "currency": "LibraUSD",
        "action": "charge",
        "timestamp": 72322,
    }

* **amount (uint)**
Amount of the transfer.  Base units are the same as for on-chain transactions for this currency.  For example, if LibraUSD is represented on-chain where “1” equals 1e-6 dollars, then “1” equals the same amount here.  For any currency, the on-chain mapping must be used for amounts.

* **currency (enum)**
One of the supported on-chain currency types - ex. LibraUSD, LibraEUR, etc.

* **action (enum)**
Populated in the request.  This value indicates the requested action to perform, and the only valid value is `charge`.

* TODO: **timestamp (unix timestamp)**
Unix timestamp indicating the time that the action was completed.

## Allowed state transitions for PaymentObject updates

The creator VASP for a PaymentObject must always set the status of the other side to `none`. In the most common case when a VASP creates a payment with one of its customers as a sender it must set the status of the receiver actor to `none`. Its own initial sender state may be `need_kyc_data` or `ready_for_settlement`.

Commands updating the payment on either side can change their own status but not the status of the other VASP. For example if the receiver VASP for a payment proposes a command it should only modify the status of the receiver actor, but not the sender. Attempting to mutate the status of the other actor will result in a command error. Status updates must proceed in the order `none`, `needs_kyc_data`, `needs_receipient_signature`, and `ready_for_settlement` - although some may be skipped if the information is already provided or not required.

Once a VASP has set its own status as `ready_for_settlement` it may not attempt to move the status of the payment to `abort`. As a result once both VASPs consider that the status of the payment is `ready_for_settlement` the payment is ready to settle on chain, and is considered technically finalized on the off-chain channel. After this 'finality barrier' has been reached the only allowed transition is to `settled` on either or both sides to indicate that an on-chain payment settling the off-chain payment has been executed.

## Example Protocol Flows

    ...

# Programing & Integration Interface

    ...

# References

[1] FATF Travel Rule.

### Glosary

- VASP
- On-Chain
