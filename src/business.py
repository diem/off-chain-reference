""" Define the 'business logic' for the Off-chain protocols """

# ---------------------------------------------------------------------------


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

    def __init__(self):
        self.callbacks = {}

    def register_callback(self, payment, callback):
        if payment not in self.callbacks:
            self.callbacks[payment] = callback

    def resume_payment(self, payment):
        if payment in self.callbacks:
            callback = self.callbacks[payment]
            callback()
            del self.callbacks[payment]

    # ----- Actors -----

    def is_sender(self, payment):
        ''' Returns true is the VASP is the sender '''
        pass

    def is_recipient(self, payment):
        ''' Returns true is the VASP is the recipient '''
        return not self.is_sender(payment)

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

print('!!!!!!!!!!!!!!!!!!')
