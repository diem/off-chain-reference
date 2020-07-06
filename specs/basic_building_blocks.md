# Basic Off-Chain Building Blocks

* **HTTP end-points**: Each VASP exposes an HTTPS POST end point at
`https://hostname:port/<protocol_version>/<localVASPAddress>/<RemoteVASPAddress>/command`. It receives `CommandRequestObject`s in the POST body, and responds with `CommandResponseObject`s in the HTTP response (See [Travel Rule Data Exchange](travel_rule_data_exchange.md) for more details. Single command requests-responses are supported (HTTP1.0) but also pipelined request-responses are supported (HTTP1.1). The version for the Off-chain protocol is the string `v1`. All HTTP requests and responses contain a header `X-Request-ID` with a unique ID for the request, used for tracking requests and debugging. Responses must have the same string in the `X-Request-ID` header value as the requests they correspond to.
* **Serialization to JSON**: All structures transmitted, nested within `CommandRequestObject` and `CommandResponseObject` are valid JSON serialized objects and can be parsed and serialized using standard JSON libraries. The content type for requests and responses is set to `Content-type: application/json; charset=utf-8` indicating all content is JSON encoded.
* **JWS Signatures**: all transmitted requests/responses are signed by the sending party using the JWS Signature standard (with the Ed25519 / EdDSA ciphersuite, and `compact` encoding).  The party's compliance key shall be used to sign these messages. This ensures all information and meta-data about payments is authenticated and cannot be repudiated.

### Basic Protocol Interaction
The basic protocol interaction consists of:

* An initiating VASP creates a `CommandRequestObject` containing a PaymentCommand, and sends it to the other VASP, in the body of an HTTP POST.
* The responding VASP listens for requests, and when received, processes them to generate and send `CommandResponseObject` responses, with a success or failure status, through the HTTP response body.
* The initiating VASP receives the response and processes it to assess whether it was successful or not.

Both VASPs in a channel can asynchronously attempt to initiate and execute commands on shared objects.

As a reminder, all `CommandRequestObject` and `CommandResponseObject` objects sent are signed using JWS Signatures, using EdDSA and compact encoding. Recipients must verify the signatures when receiving any objects.

## Request/Response Payload
All requests between VASPs are structured as [`CommandRequestObject`s](#commandrequestobject) and all responses are structured as [`CommandResponseObject`s](#commandresponseobject).  The resulting request takes a form of the following:

<details>
<summary> Request Payload Example </summary>
<pre>
{
    "_ObjectType": "CommandRequestObject",
    "command_type": "PaymentCommand", // Command type
    "cid": "VASP1_12345",
    "command": CommandObject(), // Object of type as specified by command_type
}
</pre>
</details>

A response would look like the following:
<details>
<summary> CommandResponseObject example </summary>
<pre>
{
    "_ObjectType": "CommandResponseObject",
    "cid": "VASP1_12345",
    "status": "success",
}
</pre>
</details>

### CommandRequestObject
All requests between VASPs are structured as `CommandRequestObject`s.

| Field 	| Type 	| Required? 	| Description 	|
|-------	|------	|-----------	|-------------	|
| _ObjectType| str| Y | Fixed value: `CommandRequestObject`|
|command_type | str| Y |A string representing the type of command contained in the request. |
|cid | str  | Y | A unique command identifier. |
| command | Command object | Y | The command to sequence. |

<details>
<summary> CommandRequestObject example </summary>
<pre>
{
    "_ObjectType": "CommandRequestObject",
    "cid": "VASP1_12345",
    "command": CommandObject(),
}
</pre>
</details>

### CommandResponseObject
All responses to a CommandRequestObject are in the form of a CommandResponseObject

| Field 	     | Type 	| Required? 	| Description 	|
|-------	     |------	|-----------	|-------------	|
| _ObjectType    | str      | Y             | The fixed string `CommandResponseObject`. |
| cid            | str       | Y             | The unique identifier of the corresponding request. |
| status         | str      | Y             | Either `success` or `failure`. |
| error          | List of [OffChainErrorObject](#offchainerrorobject) | N | Details on errors when status == "failure"

<details>
<summary> CommandResponseObject example </summary>
<pre>
{
    "_ObjectType": "CommandResponseObject",
    "error": [OffChainErrorObject()],
    "cid": "VASP1_12345",
    "status": "failure"
}
</pre>
</details>

When the `CommandResponseObject` status field is `failure`, the `error` field is included in the response to indicate the nature of the failure. The `error` field (type `OffChainError`) is a list of OffChainError objects.

### OffChainErrorObject
Represents an error that occurred in response to a command.

| Field 	     | Type 	| Required? 	| Description 	|
|-------	     |------	|-----------	|-------------	|
| type    | str (enum)     | Y             | Either "command_error" or "protocol_error" |
| field            | str       | N             | The field on which this error occurred|
| code    | str (enum) | Y    | The error code of the corresponding error |
| message         | str      | N             | Additional details about this error |

<details>
<summary> OffChainErrorObject example </summary>
<pre>
{
    "type": "command_error",
    "field": "0.sender.kyc_data.surname",
    "code": "missing_data",
    "message": "",
}

</pre>
</details>


Next: [Command Sequencing](command_sequencing.md)

Previous: [Design Principles](design_principles.md)
