""" Define the 'business logic' for the Off-chain protocols """

# ---------------------------------------------------------------------------

''' These interfaces are heavily WIP, as we decide how to best implement the
    above state machines '''

from os import urandom
from base64 import standard_b64encode
from copy import deepcopy
def get_unique_string():
    return standard_b64encode(urandom(16))

# Generic interface to a shared object

class SharedObject:
    def __init__(self):
        ''' All objects have a version number and their commit status '''
        self.version = get_unique_string()
        self.extends = [] # Strores the version of the previous object

        # Flags indicate the state of the object in the store
        self.potentially_live = False   # Pending commands could make it live
        self.actually_live = False   # Successful command made it live

    def new_version(self):
        ''' Make a deep copy of an object with a new version number '''
        clone = deepcopy(self)
        clone.extends = [ self.get_version() ]
        clone.version = get_unique_string()
        return clone

    def get_version(self):
        ''' Return a unique version number to this object and version '''
        return self.version

    def get_potentially_live(self):
        return self.potentially_live

    def set_potentially_live(self, flag):
        self.potentially_live = flag

    def get_actually_live(self):
        return self.actually_live

    def set_actually_live(self, flag):
        self.actually_live = flag


# Interface we need to do commands:
class ProtocolCommand:
    def __init__(self, command):
        self.depend_on = []
        self.creates   = []
        self.command   = command
        self.commit_status = None

    def get_dependencies(self):
        return set(self.depend_on)

    def new_object_versions(self):
        return set(self.creates)

    def validity_checks(self, dependencies, maybe_own=True):
        return True

    def get_object(self, version_number, dependencies):
        assert version_number in self.new_object_versions()
        raise NotImplementedError('You need to subclass and override this method')

    def on_success(self):
        pass

    def on_fail(self):
        pass

class ProtocolExecutor:
    def __init__(self):
        self.seq = []
        self.last_confirmed = 0

        # This is the primary store of shared objects.
        # It maps version numbers -> objects
        self.object_store = { } # TODO: persist this structure

    def next_seq(self):
        return len(self.seq)

    def count_potentially_live(self):
        return sum(1 for obj in self.object_store.values() if obj.get_potentially_live())

    def count_actually_live(self):
        return sum(1 for obj in self.object_store.values() if obj.get_actually_live())

    def all_true(self, versions, predicate):
        for version in versions:
            if version not in self.object_store:
                return False
            obj = self.object_store[version]
            res = predicate(obj)
            if not res:
                return False
        return True

    def sequence_next_command(self, command, do_not_sequence_errors = False, own=True):
        dependencies = command.get_dependencies()

        if own:
            # For our own commands we do speculative execution
            predicate = lambda obj: obj.get_potentially_live()
        else:
            # For the other commands we do actual execution
            predicate = lambda obj: obj.get_actually_live()

        all_good = self.all_true(dependencies, predicate)

        # TODO: Here we need to pass the business logic.
        all_good &= command.validity_checks(self.object_store, own)

        if not all_good and do_not_sequence_errors:
            # TODO: Define proper exception
            raise ExecutorCannotSequence('Cannot sequence')

        pos = len(self.seq)
        self.seq += [ command ]

        if not all_good:
            # TODO: Define proper exception
            raise ExecutorCannotSequence('Invalid ... ')

        if all_good:
            new_versions = command.new_object_versions()
            for version in new_versions:
                obj = command.get_object(version, self.object_store)
                obj.set_potentially_live(True)
                self.object_store[version] = obj

        return pos

    def set_success(self, seq_no):
        # print('start success', self.last_confirmed, seq_no, len(self.seq))
        assert seq_no == self.last_confirmed
        self.last_confirmed += 1

        command = self.seq[seq_no]
        command.commit_status = True
        # Consumes old objects
        dependencies = command.get_dependencies()
        for version in dependencies:
            del self.object_store[version]

        # Creates new objects
        new_versions = command.new_object_versions()
        # print('success', seq_no, new_versions)
        for version in new_versions:
            obj = self.object_store[version]
            obj.set_actually_live(True)

        command.on_success()

    def set_fail(self, seq_no):
        # print('start fail', self.last_confirmed, seq_no, len(self.seq))
        assert seq_no == self.last_confirmed
        self.last_confirmed += 1

        command = self.seq[seq_no]
        command.commit_status = False

        new_versions = command.new_object_versions()
        for version in new_versions:
            if version in self.object_store:
                del self.object_store[version]

        command.on_fail()

class ExecutorCannotSequence(Exception):
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


class BusinessValidationFailure(Exception):
    ''' Indicates a business check that has failed. '''
    pass


class BusinessForceAbort(Exception):
    ''' Indicates protocol must abort the transaction. '''
    pass


class BusinessContext:

    callbacks = {}

    def register_callback(payment, callback):
        if payment not in callbacks:
            callbacks[payment] = callback

    def resume_payment(payment):
        if payment in callbacks:
            callback = callbacks[payment]
            callback()
            del callbacks[payment]

    # ----- Actors -----

    def is_sender(self, payment):
        ''' Returns true is the VASP is the sender '''
        pass

    def is_recipient(self, payment):
        ''' Returns true is the VASP is the recipient '''
        return not self.is_sender()

    def check_account_existence(self, payment):
        ''' Checks that the actor on this VASP exists. This may be either
            the recipient or the sender, since VASPs can initiate payments
            in both directions.

            If not throw a BuninessValidationFailure.'''
        pass


# ----- VASP Signature -----


    def validate_recipient_signature(self, payment):
        ''' Validates the recipient signature is correct. If there is no
            signature or the signature is correct do nothing.

            Throw a BuninessValidationFailure is not. '''
        pass

    def get_recipient_signature(self, payment):
        ''' Gets a recipient signature on the payment ID'''
        pass

# ----- KYC/Compliance checks -----

    def next_kyc_to_provide(self, payment):
        ''' Returns the level of kyc to provide to the other VASP based on its
            status. Can provide more if deemed necessary or less. Can throw a
            BusinessAsyncInterupt if it is not possible to determine the level
            to provide currently (such as when user interaction may be needed).

            Returns a set of status indicating to level of kyc to provide,
            that can include:
                - needs_stable_id
                - needs_kyc_data
            an empty set indicates no KYC should be provided at this moment.

            Can raise:
                BusinessAsyncInterupt
                BusinessForceAbort
        '''
        pass

    def next_kyc_level_to_request(self, payment):
        ''' Returns the next level of KYC to request from the other VASP. Must
            not request a level that is either already requested or provided.

            Returns a status code from:
                - needs_stable_id
                - needs_kyc_data
                - needs_recipient_signature
            or the current status if no new information is required.

            Can raise:
                BusinessAsyncInterupt
                BusinessForceAbort
        '''
        pass

    def validate_kyc_signature(self, payment):
        ''' Validates the kyc signature is correct. If the signature is correct,
            or there is no signature, then do nothing.

            Throw a BuninessValidationFailure if signature verification fails. '''
        pass

    def get_extended_kyc(self, payment):
        ''' Gets the extended KYC information for this payment.

            Can raise:
                   BusinessAsyncInterupt
                   BusinessNotAuthorized.
        '''
        pass

    def get_stable_id(self, payment):
        ''' Provides a stable ID for the payment.

            Returns: a stable ID for the VASP user.

            Can raise:
                BusinessAsyncInterupt,
                BusinessNotAuthorized. '''
        pass

# ----- Settlement -----

    def ready_for_settlement(self, payment):
        ''' Indicates whether a payment is ready for settlement as far as this
            VASP is concerned. Once it returns True it must never return False.

            In particular it MUST check that:
                - Accounts exist and have the funds necessary.
                - Sender of funds intends to perform the payment (VASPs can
                  initiate payments from an account on the other VASP.)
                - KYC information provided ON BOTH SIDES is correct and to the
                  VASPs satisfaction. On payment creation a VASP may suggest KYC
                  information on both sides.

            If all the above are true, then return True.
            If any of the above are untrue throw an BusinessForceAbort.
            If any more KYC is necessary theen return False.
            If there is a need for more time throw BusinessAsyncInterupt.

            In particular BusinessAsyncInterupt supports VASP flows where KYC
            or other business validation checks cannot be performed in real
            time.

            This acts as the finality barrier and last check for this VASP. After
            this call returns True this VASP can no more abort the payment
            (unless the other VASP aborts it).

            Returns bool: True or False

            Can raise:
                BusinessAsyncInterupt
                BusinessForceAbort
            '''
        pass

    def want_single_payment_settlement(self, payment):
        ''' Ask the business logic whether to move this payment
            for settlement on chain (rather than in any other way, eg. batch,
            etc). Returns True to proceed to settle the single payment on
            chain, or False to not do so.

            Can raise:
                BusinessAsyncInterupt

            Must never raise
                BusinessForceAbort
            since it is called when we are ready to settle.

        '''
        pass

    def has_settled(self, payment):
        ''' Returns whether the payment was settled on chain. If the payment can
            be settled also package it and settle it on chain. This function may
            be called multiple times for the same payment, but any on-chain
            operation should be performed only once per payment.

            Returns a bool: True or False

            Can Raise:
                BusinessAsyncInterupt

            Cannot raise:
                BusinessForceAbort
            since this is called past the finality barrier.
        '''
        pass
