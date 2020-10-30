# A simplified state-machine for the LIP-1 off-chain protocol

## What is the problem?

Currently the off-chain protocol specified in LIP-1 allows payment objects to be a large variety of states, that could be updated concurrently by both Sender and Receiver VASPs. The large number of states and possible commands in response to these states makes compatible implementations difficult to implement, test and ensure they are comformant and interoperable.

## Outline of solution

We propose a simplified protocol in terms of the number of possible states as well as the number of transitions between these states. At each state it is easy to determine which VASP should submit the next command, and what information to include. Exception flows (pending review, soft-match and requiring full kyc exchange) are handled by aborting a payment and creating a new payment referencing it. Therefore all flows are supported while the protocol is simpler.

## Detailed solution

The state machine of the protocol is described int he figure above. A state is determined by the status of the Sender and Recipient Actors of the latest payment object. The states are:

KYC exchange flow

* SINIT: (need_kyc, none)
* RSEND: (need_kyc, ready_for_settlement)
* RABORT1: (need_kyc, abort)
* SABORT: (abort, ready_for_settlement)
* READY: (ready_for_settlement, ready_for_settlement)

Simple flow
* SREADY: (ready_for_settlement, none)
* RABORT2: (ready_for_settlement, abort)
* (READY as above)

![picture](state_machine_simple.png)

## Steps of the protocol: The KYC Exchange Flow

### Start -> SINIT

The sender creates a payment, that they believe requires KYC information exchange. The payment command includes a full payment object including the following fields:

* Sender -> Status = need_kyc_data
* Sender -> kyc_data = { The kyc data object }
* Receiver -> Status = none
* (Optionally) previous_reference_id = The reference id of a previous payment.
* (Optionally) Sender -> additional KYC =  If the payment reference includes a payment that failed due to a soft match, the Sender -> additional KYC field can also be populated.

### SINIT -> RSEND

The receiver VASP examines the Sender -> KYC data object, and is satisfied that given the sender information the payment can proceed. It responds with a command that includes:

* Recipient -> Status = Ready_for_settlement
* Recipient -> kyc_data = {The kyc data object for the recipient }
* recipient_signature
* (Optionally) Recipient -> additional kyc information (if the payment references a previous payment that failed due to a soft match.)

### SINIT -> RABORT1

The receiver VASP examines the sender kyc information and is either no satisfied the payment can proceed, needs more time to process the kyc information, or requires additional information to determine if the payment can proceed. It includes a command to abort the payment with an appropriate error code.

* Recipient -> status: abort (with code: pending, soft-match, no-kyc-needed, or other)

### RSEND -> READY

The Sender VASP examines the KYC information from the recipient and is satisfied the payment can proceed.

* Sender -> Status: ready_for_settlement

The payment can be executed on-chain by the sender (or settled in any other way).

### RSEND -> SABORT

The sender VASP requires more time, has a soft match for the recipient or cannot proceed with the payment. It issues an abort command:

* Sender -> Status: abort (with code pending, soft-match or other).

## Steps of the protocol: The Simple Flow

The simple flow is executed when the sending VASP believes there is no need for the exchange of KYC information. It does not include any sender kyc information, and indicates it is ready to settle.

### Start -> SREADY

The sender sends a payment with all mandatory fields, and:

* Sender -> Status: ready_for_settlement
* Receiver -> Status: none
* (Optional) -> reference_payment_id (of a previous payment with no-kyc-needed abort.)

### SREADY -> RABORT

The recipient examines the payment and determines that either more information is needed or the payment cannot proceed. They issue an abort with the appropriate code.

* Receipient -> Status: abort (with code need-kyc or other).

### SREADY -> READY

The recipient is satisfied that no kyc exchange is needed and is happy to proceed with the payment. They send a command updating the fields:

* Recipient -> Status: ready_for_settlement
* recipient_signature

### READY

The sender upon observing a payment in the ready state can execute it on chain.


## Abort codes and `previous_reference_id`

An abort can lead to the submission of a new payment that tries to make progress past the reasons for abort. The new payment must include a reference to the previous payment.

* Pending: the payment cannot proceed at the moment but should be re-submitted in the future.
* Soft-match: the payment requires additional KYC information to disambiguate a soft match
* Need-kyc: a payment needs the exchnage of full kyc information

All other abort codes are considered terminal, and the payment cannot proceed.
