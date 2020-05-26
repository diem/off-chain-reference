# Fund Pull Pre-Approval
### *VERSION SUPPORT: Supported only in version 1 of off-chain APIs*

Establishes a relationship between sender and recipient where the recipient can now pull funds from the sender without sender approving each transaction.  This allows recipient to bill the sender without sender approving each payment.  This relationship exists between a subaddress on the biller side and a subaddress on the sender side.  After this request is POSTed, the target VASP can use out-of-band methods to determine if this request should be granted.  If the target VASP chooses to allow the relationship to be established, the biller can create a payment object and POST to the billed party’s VASP to request funds.  The “funds_pull_approval_id” object must then match the ID established by this request.

## Request/Response Payload
All requests between VASPs are structured as [`CommandRequestObject`s](#commandrequestobject) and all responses are structured as [`CommandResponseObject`s](#commandresponseobject).  The resulting request takes a form of the following:

<details>
<summary> Request Payload Example </summary>
<pre>
{
    "_ObjectType": "CommandRequestObject",
    "command_type": "FundPullPreApprovalCommand",
    "seq": 1,
    "command": {
        "_ObjectType": "FundPullPreApprovalCommand",
        "_creates_versions": [
            "08697804e12212fa1c979283963d5c71"
        ],
        "_dependencies": [],
        "fund_pull_pre_approval": {
            "address": "lbr1pgfpnegv9gfpyysjzgfpyysjzgf3xycnzvf3xycsmxycyy",
            "biller_address": "lbr1pgfpyysjzgfpyysjzgfpyysjzgf3xycnzvf3xycsm957ne",
            "funds_pre_approval_id": "lbr1qg9q5zs2pg9q5zs2pg9q5zs2pgy7gvd9u_ref1002"
            "expiration_timestamp": 72322, 
            "max_cumulative_amount": {
                "amount": 100,
                "currency": "USD"
            }
            "description": "Kevin's online shop",
            "status": "pending",
        }
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
All requests between VASPs are structured as `CommandRequestObject`s. For a funds pull pre-approval, the command is a FundPullPreApprovalCommand as follows:

| Field 	| Type 	| Required? 	| Description 	|
|-------	|------	|-----------	|-------------	|
| _ObjectType| str| Y | Fixed value: `CommandRequestObject`|
|command_type | str| Y |A string representing the type of command contained in the request. Set to `FundPullPreApprovalCommand` for funds pull pre-approval |
|seq | int  | Y | The sequence of this request in the sender local sequence. |
| command | [`FundPullPreApprovalCommand` object](#fundpullpreapprovalcommand-object) | Y | The pre-approval command to sequence. |
|command_seq    | int | Server   | The sequence of this command in the joint command sequence. Only set if the server is the sender. See [Command Sequencing](command_sequencing.md) |

<details>
<summary> CommandRequestObject example </summary>
<pre>
{
    "_ObjectType": "CommandRequestObject",
    "command_type": "FundPullPreApprovalCommand",
    "seq": 1,
    "command": FundPullPreApprovalCommand(),
    "command_seq": 1,
}
</pre>
</details>

### FundPullPreApprovalCommand object
| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| _ObjectType   | str  | Y             | The fixed string `FundPullPreApprovalCommand` |
| _creates_versions | list of str |  Y | Must be a list containing a single str representing the version of the new or updated `FundPullPreApprovalObject` resulting from the success of this command. A list with any other number of items results in a command error.  This string must be a unique random string between this pair of VASPs and is used to represent the version of the item created. These should be at least 16 bytes long and encoded to string in hexadecimal notation using characters in the range[A-Za-z0-9] |
| _dependencies | list of str | Y | Can be an empty list or a list containing a single previous version. If the list is empty this command defines a new fund pre-approval. If the list contains one item, then this command updates the shared `FundPullPreApprovalObject` with the given version. It is an error to include more versions, and it results in a command error response.  The value in this field must match a version previously specified by the `_creates_versions` parameter on a prior command. |
| fund_pull_pre_approval| [`FundPullPreApprovalObject`](#fundpullpreapprovalobject) | Y | contains a `FundPullPreApprovalObject` that either creates a new pre-approval or updates an existing pre-approval. Note that strict validity checks apply when updating pre-approvals, that are listed in the section below describing these objects. An invalid update or initial pre-approval object results in a command error

<details>
<summary> FundPullPreApprovalCommand example </summary>
<pre>
{
    "_ObjectType": "FundPullPreApprovalCommand",
    "_creates_versions": [
        "08697804e12212fa1c979283963d5c71"
    ],
    "_dependencies": [],
    "fund_pull_pre_approval": {
        FundPullPreApprovalObject(),
    }
}
</pre>
</details>

### FundPullPreApprovalObject

The structure in this object can be a full pre-approval of just the fields of an existing pre-approval object that need to be changed. Some fields are immutable after they are defined once (see below). Others can by updated multiple times. Updating immutable fields with a different value results in a command error, but it is acceptable to re-send the same value.

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| address | str | Required for creation | Address of account from which the pre-approval is being requested. The addresses are encoded using bech32. The bech32 address encodes both the address of the VASP as well as the specific user's subaddress. They should be no longer than 80 characters. Immutable after creation. |
| biller_address | str | Required for creation | Address of account from which billing will happen. The addresses are encoded using bech32. The bech32 address encodes both the address of the VASP as well as the specific user's subaddress. They should be no longer than 80 characters. Immutable after creation. |
| expiration_timestamp | uint | N | Unix timestamp indicating the time at which this pre-approval will expire - after which no funds pulls can occur.  To expire an existing pre-approval early, this field can be updated with the current unix timestamp. |
| funds_pre_approval_id | str | Y | Unique reference ID of this pre-approval on the pre-approval initiator VASP (the VASP which originally created this pre-approval object). This value should be unique, and formatted as “<creator_vasp_onchain_address_bech32>_<unique_id>”.  For example, ”lbr1x23456abcd_seqABCD“. This field is mandatory on pre-approval creation and immutable after that.  Updates to an existing pre-approval must also include the previously created pre-approval ID. |
| max_cumulative_amount | [CurrencyObject](#currencyobject) | N | Max cumulative amount that is approved for funds pre-approval.  This is the sum across all transactions that occur while utilizing this funds pre-approval. |
| description | str | N | Description of the funds pre-approval.  May be utilized so show the user a description about the request for funds pre-approval |
| status | str enum | N | Status of this pre-approval. See [Pre-Approval Status Enum](#pre-approval-status-enum) for valid statuses. 

<details>
<summary> FundPullPreApprovalObject example </summary>
<pre>
{
    "address": "lbr1pgfpnegv9gfpyysjzgfpyysjzgf3xycnzvf3xycsmxycyy",
    "biller_address": "lbr1pgfpyysjzgfpyysjzgfpyysjzgf3xycnzvf3xycsm957ne",
    "funds_pre_approval_id": "lbr1qg9q5zs2pg9q5zs2pg9q5zs2pgy7gvd9u_ref1002"
    "expiration_timestamp": 72322, 
    "max_cumulative_amount": CurrencyObject(),
    "description": "Kevin's online shop",
    "status": "valid",
}
</pre>
</details>

### CurrencyObject

Represents an amount and the currency type.

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| amount | uint | Y | Base units are the same as for on-chain transactions for this currency.  For example, if LibraUSD is represented on-chain where “1” equals 1e-6 dollars, then “1” equals the same amount here.  For any currency, the on-chain mapping must be used for amounts. |
| currency | str enum | Y | One of the supported on-chain currency types - ex. LBR, BTC, USD, EUR, etc. |

<details>
<summary> CurrencyObject example </summary>
<pre>
{
    "amount": 100,
    "currency": "USD",
}
</pre>
</details>

### Pre Approval Status Enum
Valid values are:
* `pending` - Pending user approval.
* `valid` - Approved by the user and ready for usage.
* `rejected` - User did not approve the pre-approval request.
* `closed` - Approval has been closed by the user and can no longer be used.

**Valid Status Transitions**. Either party in the pre-approval agreement can mutate the status. The status always initially begins as `pending` at which time a user must agree to the pre-approval request.  Once the user has reviewed the request, the billee VASP will update the pre-approval status to `valid` (if the user agreed) or `rejected` (if the user rejected the pre-approval).

At any point, the user can withdraw permission at which point the status will be updated to `closed`.


### CommandResponseObject
All responses to a CommandRequestObject are in the form of a [CommandResponseObject](travel_rule_data_exchange.md#commandresponseobject)


Previous: [Travel Rule Data Exchange](travel_rule_data_exchange.md)

Next: [Auth and Capture](auth_capture.md)


