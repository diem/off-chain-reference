# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

""" The Payment object status is defined by the status of both actors,
    senders and receivers, namely the tuple (sender_status, recipient_status).
    An actor status may have the following values:

V0 States
---------

    * None  -- denotes the status of an object that does not exist
      for the payment recipient.
    * needs_kyc_data -- requires the other VASP to provide KYC data.
    * pending_review -- indicated the actor is manually reviewing the payment
      and delays are expected.
    * soft_match -- indicates that the actor requires additional KYC information
      to disambiguate the individual involved in the payment.
    * ready_for_settlement -- signals that the party is ready to settle
      the transaction.
    * needs_recipient_signature -- requests the recipient VASP to sign the
      identifier for this transaction to put it on chain.
    * abort - signals that the transactions is to be aborted.

"""

from enum import Enum


class Status(Enum):
    none = 'none',

    needs_kyc_data = 'needs_kyc_data',
    # Sender only

    needs_recipient_signature = 'needs_recipient_signature',
    # Receiver only: this is a virtual flag

    pending_review = 'pending_review'
    soft_match = 'soft_match'

    ready_for_settlement = 'ready_for_settlement',
    abort = 'abort'

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


STATUS_HEIGHTS = {
    Status.none: 100,
    Status.needs_kyc_data: 200,
    Status.needs_recipient_signature: 200,
    Status.soft_match: 200,
    Status.pending_review: 200,
    Status.ready_for_settlement: 400,
    Status.abort: 1000
}
