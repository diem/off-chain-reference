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
<<<<<<< HEAD
=======

--------------------------------------------------

VASP sub-commands to implement all transitions:

.create_payment()
    Creates a new payment with all mandatory fields set.

.set_signature()
    Used by receiver to sign the Payment reference ID.

.add_<sender|recipient>_stable_id()
    Used to include the stabe ID for the user at either VASPs.

.add_<sender|recipient>_extended_kyc()
    Used to include the extended KYC information at either VASP.

.change_<sender|recipient>_status()
    Update the status of the payment at either VASP.

.add_<sender|recipient>_metadata()
    Change the metadata field at either VASP.

>>>>>>> [protocol] Porting off-chain prototype files to github
"""

# ---------------------------------------------------------------------------

''' These interfaces are heavily WIP, as we decide how to best implement the
    above state machines '''

from os import urandom
from base64 import standard_b64encode

def get_unique_string():
    return standard_b64encode(urandom(16))

# Generic interface to a shared object
class SharedObject:
    def __init__(self):
        ''' All objects have a version number and their commit status '''
        self.version = get_unique_string()
        self.decided = None

    def new_version(self):
        ''' Make a deep copy of an object with a new version number '''
        clone = deepclone(self)
        clone.version = get_unique_string()
        clone.decided = None
        return clone

    def get_version(self):
        ''' Return a unique version number to this object and version '''
        return self.version

    def is_decided(self):
        ''' Denotes the commands leading to this object have been sequenced.
            They could be successes or failures.'''

    def is_success(self):
        ''' Denotes whether the object has been committed to the sequence'''
        return self.is_decided() and self.decided == True

    def commit_success(self):
        ''' Tag this object as a success if all requests leading to it were
            a success '''
        self.decided = True

    def commit_failure(self):
        ''' Tag this object as a failure if any command leading to it is a
            failure'''
        self.decided = False



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

# A model for VASP business environment

class BusinessAsyncInterupt(Exception):
    ''' Indicates that the result cannot be produced immediately,
        and the call must be done again once the result is ready. '''
    pass

class BusinessNotAuthorized(Exception):
    ''' Indicates that the VASP requesting some information is
        not authorized to receive it. '''
    pass

class BuninessValidationFailure(Exception):
    ''' Indicates a business check that has failed. '''
    pass

class BusinessForceAbort(Exception):
    ''' Indicates protocol must abort the transaction. '''
    pass


class BusinessContext:

    def is_sender(self, payment):
        ''' Returns true is the VASP is the sender '''
        pass

    def is_recipient(self, payment):
        ''' Returns true is the VASP is the recipient '''
        return not self.is_sender()

    def check_actor_existence(self, payment):
        ''' Checks that the actor on this VASP (usually receiver)
            exists. If not throw a BuninessValidationFailure.'''
        pass

    def is_trusted_VASP(self, payment):
        ''' Returns true if the other party is a trusted VASP. '''
        pass

    def provide_stable_id(self, payment):
        ''' Provides a stable ID for the payment.

            Returns: a stable ID for the VASP user.

            Can raise:
                BusinessAsyncInterupt,
                BusinessNotAuthorized. '''
        pass

    def validate_recipient_signature(self, payment):
        ''' Validates the recipient signature is correct.
            Throw a BuninessValidationFailure is not. '''
        pass

    def validate_kyc_signature(self, payment):
        ''' Validates the kyc signature is correct.
            Throw a BuninessValidationFailure is not. '''
        pass

    def compliance_check_on_kyc(self, payment):
        ''' Performs all compliace checks on kyc information
            provided. '''
        pass

    def is_retail_payment(self, payment):
        ''' Returns True if the payment is retail, and
            therefore there is no need for extended KYC information.'''
        pass

    def needs_extended_kyc(self, payment):
        ''' Returns true if the payment requires extended KYC information. '''
        pass

    def get_extended_kyc(self, payment):
        ''' Gets the extended KYC information for this payment.

            Can raise:
                   BusinessAsyncInterupt
                   BusinessNotAuthorized.
        '''
        pass

    def has_settled(self, payment):
        ''' Returns whether the payment was settled on chain '''
        pass

    def do_settle(self, payment):
        ''' Request for the payment to be settled on chain '''
        pass

    def last_chance_to_abort(self, payment):
        ''' This is called when the status is about to change, to one
            where it is no more possible to abort the payment. To give
            the business logic one last chance to abort a payment with
            complete data.

            Can raise:
                BusinessAsyncInterupt
                BusinessForceAbort
                '''
        pass
