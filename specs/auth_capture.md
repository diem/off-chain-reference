# Auth/Capture
### *VERSION SUPPORT: Supported only in version 1 of off-chain APIs*

Authorization allows to place holds on funds with the assurance that an amount up to the held amount can be captured at a later time.  An example of this is for delayed fulfillment or pre-authorizing an expected amount to ensure that an amount can be charged after services are rendered.

When an authorization happens, the VASP agreeing to the authorization must lock the funds for the specified amount of time - the VASP is agreeing to a guarantee that the funds will be available if later captured.

Auth/capture is an extension of [PaymentCommand](travel_rule_data_exchange.md#paymentcommand-object).  The extension happens primarily within the [PaymentActionObject](travel_rule_data_exchange.md#paymentaction-object) and the status changes.

### PaymentActionObject

| Field 	    | Type 	| Required? 	| Description 	|
|-------	    |------	|-----------	|-------------	|
| amount | uint | Y | Amount of the transfer.  Base units are the same as for on-chain transactions for this currency.  For example, if LibraUSD is represented on-chain where “1” equals 1e-6 dollars, then “1” equals the same amount here.  For any currency, the on-chain mapping must be used for amounts. |
| currency | enum | Y | One of the supported on-chain currency types - ex. LBR, BTC, USD, EUR, etc. |
| action | enum | Y | Populated in the request.  This value indicates the requested action to perform.  For a normal transfer, "charge" is still used.  For auth and capture, "auth" and "capture" are now available.  "capture" can only be performed after a valid "auth" |
| valid_until | uint | N | Unix timestamp indicating the time period for which this authorization is valid.  Once this time has been reached, the authorization is no longer able to be captured and funds should be unlocked. |
| timestamp | uint | Y | Unix timestamp indicating the time that the payment command was created.

<details>
<summary> PaymentActionObject example </summary>
<pre>
{
    "amount": 100,
    "currency": "USD",
    "action": "auth",
    "valid_until": 74000,
    "timestamp": 72322,
}
</pre>
</details>

### StatusEnum

The auth/capture flow now adds the following to the status enum:

* `authorized` - Payment amount is authorized but not yet captured.

`abort` may still be used to cancel the authorization early.  Once a capture action occurs, the status of the payment will now be updated to `ready_for_settlement`.

**Valid Status Transitions**. `authorized` is now a valid initial value and may be followed by `ready_for_settlement` (upon a successful capture) or `abort` (if one side wishes to cancel the auth).

Previous: [Funds Pre Approval](funds_pre_approval.md)


