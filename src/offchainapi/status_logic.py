# Copyright (c) Facebook, Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    abort = 'abort'

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name
