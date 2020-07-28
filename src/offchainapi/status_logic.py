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
    * ready_for_settlement -- signals that the party is ready to settle
      the transaction.
    * needs_recipient_signature -- requests the recipient VASP to sign the
      identifier for this transaction to put it on chain.
    * settled -- a Libra transaction settles this transaction
    * abort - signals that the transactions is to be aborted.

"""

from enum import Enum


class Status(Enum):
    none = 'none',
    needs_kyc_data = 'needs_kyc_data',
    # Sender only
    needs_recipient_signature = 'needs_recipient_signature',
    # Receiver only: this is a virtual flag
    ready_for_settlement = 'ready_for_settlement',
    settled = 'settled',
    abort = 'abort'

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name
