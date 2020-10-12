# Travel Rule Data Exchange

In the initial version of the off-chain APIs, the usage is intended as a means of transferring travel-rule information between VASPs.  The following will detail the request and response payloads utilized for this purpose.

## Request/Response Payload
All requests between VASPs are structured as [`CommandRequestObject`s](basic_building_blocks.md#commandrequestobject) and all responses are structured as [`CommandResponseObject`s](basic_building_blocks.md#commandresponseobject).  For a travel-rule data exchange, the resulting request takes a form of the following:

<details>
<summary> Sample Travel Rule Request Payload Example </summary>
<pre>
{
    "_ObjectType": "CommandRequestObject",
    "command_type": "PaymentCommand",
    "seq": 1,
    "command": {
	    "_ObjectType": "PaymentCommand",
	    "_writes": [
	        "08697804e12212fa1c979283963d5c71"
	    ],
	    "_reads": [],
	    "payment": {
		    "sender": {
			    "address": "lbr1pgfpyysjzgfpyysjzgfpyysjzgf3xycnzvf3xycsm957ne",
			    "kyc_data": {
				    "payload_type": "KYC_DATA"
				    "payload_version": 1,
				    "type": "individual",
				    "given_name": "ben",
				    "surname": "maurer",
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
				},
			    "status": {
			    	"status": "ready_for_settlement",
			    }
			},
		    "receiver": {
			    "address": "lbr1pgfpnegv9gfpyysjzgfpyysjzgf3xycnzvf3xycsmxycyy",
			},
		    "reference_id": "lbr1qg9q5zs2pg9q5zs2pg9q5zs2pgy7gvd9u_ref1001",
		    "action": {
			    "amount": 100,
			    "currency": "USD",
			    "action": "charge",
			    "timestamp": 72322,
			},
		    "description": "A free form or structured description of the payment.",
		},
	},
    "command_seq": 1,
}
</pre>
</details>

A response would look like the following:
<details>
<summary> CommandRequestObject example </summary>
<pre>
{
    "_ObjectType": "CommandResponseObject",
    "seq": 1,
    "command_seq": 1,
    "status": "success",
}
</pre>
</details>

### CommandRequestObject
For a travel rule data exchange, the [command_type](basic_building_blocks.md#commandrequestobject) field is set to "PaymentCommand".  The command object is a [`PaymentCommand` object](#paymentcommand-object).

### PaymentCommand object
| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| _ObjectType   | str  | Y             | The fixed string `PaymentCommand` |
| _writes | list of str |  Y | Must be a list containing a single str representing the version of the new or updated `PaymentObject` resulting from the success of this payment command. A list with any other number of items results in a command error.  This string must be a unique random string between this pair of VASPs and is used to represent the version of the item created. These should be at least 16 bytes long and encoded to string in hexadecimal notation |
| _reads | list of str | Y | Can be an empty list or a list containing a single previous version. If the list is empty this payment command defines a new payment. If the list contains one item, then this command updates the shared `PaymentObject` with the given version. It is an error to include more versions, and it results in a command error response.  The value in this field must match a version previously specified by the `_writes` parameter on a prior command. |
| payment| [`PaymentObject`](#paymentobject) | Y | contains a `PaymentObject` that either creates a new payment or updates an existing payment. Note that strict validity check apply when updating payments, that are listed in the section below describing these objects. An invalid update or initial payment object results in a command error

<details>
<summary> PaymentCommand example </summary>
<pre>
{
    "_ObjectType": "PaymentCommand",
    "_writes": [
        "08697804e12212fa1c979283963d5c71"
    ],
    "_reads": [],
    "payment": {
        PaymentObject(),
    }
}
</pre>
</details>

The __reads_ list tracks the object versions that are necessary for a command to succeed. It allows server and client to detect commands that conflict, since they would list the same object version in their __reads_ lists. In such cases only one of the conflicting commands should proceed and be 'successful', and the other one should be a 'failure'. When a command status is successful, the objects with versions in the __writes_ list are created and may be used by subsequent commands. All object versions listed in the __reads_ list of a successful command become unavailable to subsequent commands.

### PaymentObject

The structure in this object can be a full payment of just the fields of an existing payment object that need to be changed. Some fields are immutable after they are defined once (see below). Others can by updated multiple times. Updating immutable fields with a different value results in a command error, but it is acceptable to re-send the same value.

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| sender/receiver | [`PaymentActorObject`](#paymentactorobject) | Required for payment creation | Information about the sender/receiver in this payment |
| reference_id | str | Y | Unique reference ID of this payment on the payment initiator VASP (the VASP which originally created this payment object). This value should be unique, and formatted as “<creator_vasp_onchain_address_bech32>_<unique_id>”.  For example, ”lbr1x23456abcd_seqABCD“. This field is mandatory on payment creation and immutable after that. |
| original_payment_reference_id | str | N | Used for updates to a payment after it has been committed on chain. For example, used for refunds. The reference ID of the original payment will be placed into this field. This value is optional on payment creation and invalid on updates. |
| recipient_signature | str | N | Signature of the recipient of this transaction. The signature is over the LCS serialized representation of `reference_id`, `sender_address`, `amount` and is signed with the compliance key of the recipient VASP.  This is used for on-chain attestation from the recipient party.  This may be omitted on blockchains which do not require on-chain attestation |
| action | [`PaymentActionObject`](#paymentactionobject) | Y | Number of cryptocurrency + currency type (USD, LBR, EUR, BTC, etc.) + type of action to take. This field is mandatory and immutable |
| description | str | N | Description of the payment. To be displayed to the user. Unicode utf-8 encoded max length of 255 characters. This field is optional but can only be written once.

<details>
<summary> PaymentObject example </summary>
<pre>
{
    "sender": payment_actor_object(),
    "receiver": payment_actor_object(),
    "reference_id": "lbr1qg9q5zs2pg9q5zs2pg9q5zs2pgy7gvd9u_ref1001",
    "original_payment_reference_id": "lbr1qg9q5zs2pg9q5zs2pg9q5zs2pgy7gvd9u_ref0987",
    "recipient_signature": "...",
    "action": payment_action_object(),
    "description": "A free form or structured description of the payment.",
}
</pre>
</details>

### PaymentActorObject

A `PaymentActorObject` represents a participant in a payment - either sender or receiver. It also includes the status of the actor, indicates missing information or willingness to settle or abort the payment, and the Know-Your-Customer information of the customer involved in the payment.

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| address | str | Y | Address of the sender/receiver account. Addresses may be single use or valid for a limited time, and therefore VASPs should not rely on them remaining stable across time or different VASP addresses. The addresses are encoded using bech32. The bech32 address encodes both the address of the VASP as well as the specific user's subaddress. They should be no longer than 80 characters. Mandatory and immutable. For Libra addresses, refer to (TODO) for format. |
| kyc_data | [KycDataObject](#kycdataobject) | N | The KYC data for this account. This field is optional but immutable once it is set. |
| status | [StatusObject](#statusobject) | Y | Status of the payment from the perspective of this actor. This field can only be set by the respective sender/receiver VASP and represents the status on the sender/receiver VASP side. This field is mandatory by this respective actor (either sender or receiver side) and mutable. |
| metadata | list of str | Y | Can be specified by the respective VASP to hold metadata that the sender/receiver VASP wishes to associate with this payment. This is a mandatory field but can be set to an empty list (i.e. `[]`). New string-typed entries can be appended at the end of the list, but not deleted.

<details>
<summary> PaymentActorObject example </summary>
<pre>
{
    "address": "lbr1pgfpyysjzgfpyysjzgfpyysjzgf3xycnzvf3xycsm957ne",
    "kyc_data": kyc_data_object(),
    "status": status_object(),
    "metadata": [],
}
</pre>
</details>

### KYCDataObject
A `KYCDataObject` represents the KYC data for a single subaddress.  Proof of non-repudiation is provided by the signatures included in the JWS payloads.  The only mandatory fields are `payload_type`, `payload_version` and `type`. All other fields are optional from the point of view of the protocol -- however they may need to be included for another VASP to be ready to settle the payment.

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| payload_type | str | Y | Used to help determine what type of data this will deserialize into.  Always set to KYC_DATA. |
| payload_version | str | Y | Version identifier to allow modifications to KYC data object without needing to bump version of entire API set.  Set to 1 |
| type | str | Y | Required field, must be either “individual” or “entity” |
| given_name | str | N | Legal given name of the user for which this KYC data object applies. |
| surname | str | N | Legal surname of the user for which this KYC data object applies. |
| address | [AddressObject](#addressobject) | N | Physical address data for this account |
| dob | str | N | Date of birth for the holder of this account.  Specified as an ISO 8601 calendar date format: https://en.wikipedia.org/wiki/ISO_8601 |
| place_of_birth | [AddressObject](#addressobject) | N | Place of birth for this user.  line1 and line2 fields should not be populated for this usage of the address object |
| national_id | [NationalIdObject](#nationalidobject) | N | National ID information for the holder of this account |
| legal_entity_name | str | N | Name of the legal entity.  Used when subaddress represents a legal entity rather than an individual. KYCDataObject should only include one of legal_entity_name OR given_name/surname |
| additional_kyc_data | str | N | Freeform KYC data.  If a soft-match occurs, this field should be used to specify additional KYC data which can be used to clear the soft-match.  It is suggested that this data be JSON, XML, or another human-readable form.

<details>
<summary> KYCDataObject example </summary>
<pre>
{
    "payload_type": "KYC_DATA"
    "payload_version": 1,
    "type": "individual",
    "given_name": "ben",
    "surname": "maurer",
    "address": {
        AddressObject(),
    },
    "dob": "1920-03-20",
    "place_of_birth": {
        AddressObject(),
    }
    "national_id": {
    },
    "legal_entity_name": "Superstore",
}
</pre>
</details>

### AddressObject
Represents a physical address

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| city | str | N | The city, district, suburb, town, or village |
| country | str | N | Two-letter country code (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) |
| line1 | str | N | Address line 1 |
| line2 | str | N | Address line 2 - apartment, unit, etc.|
| postal_code| str | N | ZIP or postal code |
| state | str | N | State, county, province, region.

<details>
<summary> AddressObject example </summary>
<pre>
{
    "city": "Sunnyvale",
    "country": "US",
    "line1": "1234 Maple Street",
    "line2": "Apartment 123",
    "postal_code": "12345",
    "state": "California",
}
</pre>
</details>

### NationalIdObject
Represents a national ID.

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| id_value | str | Y | Indicates the national ID value - for example, a social security number |
| country | str | N | Two-letter country code (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) |
| type | str | N | Indicates the type of the ID |

<details>
<summary> NationalIdObject example </summary>
<pre>
{
    "id_value": "123-45-6789",
    "country": "US",
    "type": "SSN",
}
</pre>
</details>


### PaymentActionObject

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| amount | uint | Y | Amount of the transfer.  Base units are the same as for on-chain transactions for this currency.  For example, if LibraUSD is represented on-chain where “1” equals 1e-6 dollars, then “1” equals the same amount here.  For any currency, the on-chain mapping must be used for amounts. |
| currency | enum | Y | One of the supported on-chain currency types - ex. LBR, BTC, USD, EUR, etc. |
| action | enum | Y | Populated in the request.  This value indicates the requested action to perform, and the only valid value is `charge`. |
| timestamp | uint | Y | Unix timestamp indicating the time that the payment command was created.

<details>
<summary> PaymentActionObject example </summary>
<pre>
{
    "amount": 100,
    "currency": "USD",
    "action": "charge",
    "timestamp": 72322,
}
</pre>
</details>

### StatusObject

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| status | str enum | Y | Status of the payment from the perspective of this actor. This field can only be set by the respective sender/receiver VASP and represents the status on the sender/receiver VASP side. This field is mandatory by this respective actor (either sender or receiver side) and mutable. Valid values are specified in [ StatusEnum ](#statusenum)  |
| abort_code    | str (enum) | N    | In the case of an `abort` status, this field may be used to describe the reason for the abort. Represents the error code of the corresponding error |
| abort_message         | str      | N             | Additional details about this error.  To be used only when `code` is populated |

<details>
<summary> StatusObject example </summary>
<pre>
{
    "status": "needs_kyc_data",
}
</pre>
</details>


### StatusEnum
Valid values are:
* `none` - No status is yet set from this actor.
* `needs_kyc_data` - KYC data about the subaddresses is required by this actor.
* `needs_recipient_signature` - Can only be associated with the sender actor.  Means that the sender still requires that the recipient VASP provide the signature so that the transaction can be put on-chain.
* `ready_for_settlement` - Transaction is ready for settlement according to this actor (i.e. the required signatures/KYC data have been provided)
* `abort` - Indicates the actor wishes to abort this payment, instead of settling it.
* `pending_review` - Payment is pending review.
* `soft_match` - Actor's KYC data resulted in a soft-match.  The VASP associated with this actor should send any available KYC information which may clear the soft-match via the KYCObject field of `additional_kyc_data`.  If not sent within SLA window, this transaction will be aborted.

**Valid Status Transitions**. Each side of the transaction is only allowed to mutate their own status (sender or receiver), and upon payment creation may only set the status of the other party to `none`. Subsequently, each party may only modify their own state to a higher or equal state in the order `none`, (`needs_kyc_data`, `needs_recipient_signature`, `abort`, `pending_review`), (`soft_match`, `ready_for_settlement`, `abort`). Once a party sets their own status to `abort` they must not modify the payment any more by issuing new commands (but can accept commands from the other party). A party may only modify a state of `ready_for_settlement` to `abort` if the other side sets their status to `abort`.

A payment with status of `abort` or `ready_for_settlement` on both sender and receiver sides has reached a terminal state and must not be changed. As a consequence once a transaction is in a `ready_for_settlement` state by both parties it cannot be aborted any more and can be considered final from the point of view of the off-chain protocol. It is therefore safe for a VASP sending funds to initiate an On-Chain payment to settle an Off-chain payment after it observed the other party setting their status to `ready_for_settlement` and it is also willing to go past this state.

A state of `pending_review` may exist due to manual review. This state may result in any of `soft_match`, `ready_for_settlement`, or `abort`.

A state of `soft_match` requires that the VASP associated with this actor must send all available KYC data via `additional_kyc_data`.  After human review of this data, this state may result in any of `ready_for_settlement` or `abort` (`abort` if the soft-match was unable to be cleared).  If data is not received within a reasonable SLA (suggested to be 24 hours), this state will result in `abort`.  The party who needs to provide KYC data is also allowed to `abort` the transaction at any point if they do not have additional KYC data or do not wish to supply it.


Previous: [Command Sequencing](command_sequencing.md)

Next: [Open source implementation of off-chain APIs](https://github.com/calibra/off-chain-api)
