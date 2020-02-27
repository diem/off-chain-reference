""" Define the 'business logic' for the Off-chain protocols """

""" The Payment object status is defined by the status of both actors, senders and
    receivers, namely the tuple (sender_status, recipient_status). An actor status may
    have the following values:


V0 States
---------

        * None                      -- denotes the status of
                                       an object that does not exist
        * needs_stable_id           -- requests the other VASP for
                                       a stable identifier for
                                       the payment recipient.
        * needs_kyc_data            -- requires the other VASP
                                       to provide KYC data.
        * ready_for_settlement      -- signals that the party is ready to settle
                                       the transaction.
        * needs_recipient_signature -- requests the recipient VASP to sign the
                                       identifier for this transaction to put
                                       it on chain.
        * signed                    -- The recipient signed the transaction to
                                       settle
        * settled                   -- a Libra transaction settles this
                                       transaction
        * abort                     -- signals that the transactions is to be
                                       aborted.

V1 States
---------

        * in_batch                  -- payment is included in a batch

The allowable state transitions are as follows:

-- CREATE OBJECTS & Inquire for stable ID

Sender Actor
------------
(None, None) -> (needs_stable_id, None)
             -> (ready_for_settlement, None)
             -> (needs_recipient_signature, None)

Recipient Actor
---------------
(needs_stable_id, None) -> (needs_stable_id, needs_stable_id)
                        -> (needs_stable_id, needs_kyc_data)
                        -> (needs_stable_id, ready_for_settlement)

(ready_for_settlement, None) -> (ready_for_settlement, ready_for_settlement)

Sender
------
(needs_stable_id, needs_stable_id)      -> (ready_for_settlement, needs_stable_id)
                                        -> (needs_kyc_data, needs_stable_id)
(needs_stable_id, needs_kyc_data)       -> (needs_kyc_data, needs_kyc_data)
                                        -> (ready_for_settlement, needs_kyc_data)
(needs_stable_id, ready_for_settlement) -> (ready_for_settlement, ready_for_settlement)

Recipient
---------
(ready_for_settlement, needs_stable_id) -> (ready_for_settlement, ready_for_settlement)

-- EXCHANGE KYC FLOWS

Recipient
---------
(needs_kyc_data, needs_stable_id) -> (needs_kyc_data, needs_kyc_data)
                                  -> (needs_kyc_data, ready_for_settlement)

Sender or Recipient
-------------------
(needs_kyc_data, needs_kyc_data) -> (needs_kyc_data, needs_kyc_data)

Sender
------
(needs_kyc_data, needs_kyc_data) -> (ready_for_settlement, needs_kyc_data)
(needs_kyc_data, ready_for_settlement) -> (ready_for_settlement, ready_for_settlement)

Recipient
---------
(needs_kyc_data, needs_kyc_data)       -> (needs_kyc_data, ready_for_settlement)
(ready_for_settlement, needs_kyc_data) -> (ready_for_settlement, ready_for_settlement)

-- ON CHAIN SETTLEMENT FLOWS -- ONE PAYMENT

Sender
------
(ready_for_settlement, ready_for_settlement) -> (needs_recipient_signature, ready_for_settlement)

Recipient
---------
(needs_recipient_signature, None) -> (needs_recipient_signature, signed)
(needs_recipient_signature, ready_for_settlement) -> (needs_recipient_signature, signed)

Sender
------
(needs_recipient_signature, signed) -> (settled, signed)

Recipient
---------
(settled, signed) -> (settled, settled)

#-- PAYMENT BATCH FLOWS (v1)
#
#Sender or Recipient
#-------------------
#(ready_for_settlement, ready_for_settlement) -> in_batch
#in_batch -> (ready_for_settlement, ready_for_settlement)
#
#in_batch -> (settled, settled)

-- ABORT FLOWS

* = all states except { settled }

Sender
------
(*, *) -> (Abort, *)
(*, Abort) -> (Abort, Abort)

Recipient
---------
(*, *) -> (*, Abort)
(Abort, *) -> (Abort, Abort)
"""

# ---------------------------------------------------------------------------

''' These interfaces are heavily WIP, as we decide how to best implement the
    above state machines '''

# Generic interface to a shared object
class SharedObject:

    def get_version(self):
        ''' Return a unique version number to this object and version '''
        pass

    def is_decided(self):
        ''' Denotes the commands leading to this object have been sequenced.
            They could be successes or failures.'''
        pass

    def is_success(self):
        ''' Denotes whether the object has been committed to the sequence'''
        pass

    def commit_success(self):
        ''' Tag this object as a success if all requests leading to it were
            a success '''
        pass

    def commit_failure(self):
        ''' Tag this object as a failure if any command leading to it is a
            failure'''
        pass



# Interface we need to do commands:
class ProtocolCommand:

    def __init__(self, command):
        pass

    def dependent_objects(self):
        ''' Returns a list of object-IDs that need to exist for this command
            to have a chance to succeed '''
        pass

    def creates_objects(self):
        ''' Lists the object-IDs created if this command succeeds '''
        pass

    def try_command(self):
        ''' Called to check the command is acceptable, and return a command
            success or failure code and message.'''
        pass

    def commit_command(self):
        ''' Upon both parties signaling success, commit the command, and objects affected '''
        pass

    def abort_command(self):
        ''' Upon command failure, undo any modification and free resources '''
        pass

    def seriliaze(self):
        # TODO: representation of the command to send over.
        pass

    def persist(self):
        # TODO: define durability model
        pass
