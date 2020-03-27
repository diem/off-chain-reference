""" Define the 'business logic' for the Off-chain protocols """

# ---------------------------------------------------------------------------


# A model for VASP business environment

class BusinessAsyncInterupt(Exception):
    ''' Indicates that the result cannot be produced immediately,
        and the call must be done again once the result is ready. '''

    def __init__(self, callback_ID):
        ''' Set a callback ID to signal which call was interupted '''
        self.callback_ID = callback_ID

    def get_callback_ID(self):
        ''' Return the callback ID associated with the interrupted call '''
        return self.callback_ID


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
        self.info_context = VASPInfo()

    def open_channel_to(self, other_vasp_info):
        ''' Requests authorization to open a channel to another VASP.
            If it is authorized nothing is returned. If not an exception is raised.

            Can raise:
                BusinessNotAuthorized
        '''
        raise NotImplementedError()

    def get_vasp_info_by_libra_address(self, libra_address):
        ''' Returns a VASPInfo instance for the other VASP. This requires
            reading the latest authoritative information from the chain.
        '''
        raise NotImplementedError()

    # ----- Actors -----

    def is_sender(self, payment):
        ''' Returns true if the VASP is the sender of a payment.'''
        raise NotImplementedError()

    def is_recipient(self, payment):
        ''' Returns true if the VASP is the recipient of a payment.'''
        return not self.is_sender(payment)

    def check_account_existence(self, payment):
        ''' Checks that the actor (sub-account / sub-address) on this VASP exists. This may be either
            the recipient or the sender, since VASPs can initiate payments
            in both directions. If not throw a BusinessValidationFailure.

            Can raise:
                BusinessValidationFailure'''

        raise NotImplementedError()


# ----- VASP Signature -----


    def validate_recipient_signature(self, payment):
        ''' Validates the recipient signature is correct. Raise a
            BusinessValidationFailure is the signature is invalid
            or not present. If the signature is valid do nothing.

            Can raise:
                BusinessValidationFailure'''
        raise NotImplementedError()

    def get_recipient_signature(self, payment):
        ''' Gets a recipient signature on the payment ID. '''
        raise NotImplementedError()

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
                - needs_recipient_signature
            an empty set indicates no KYC should be provided at this moment.

            Can raise:
                BusinessAsyncInterupt
                BusinessForceAbort
        '''
        raise NotImplementedError()

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
        raise NotImplementedError()

    def validate_kyc_signature(self, payment):
        ''' Validates the kyc signature is correct. Raise a
            BusinessValidationFailure is the signature is invalid
            or not present. If the signature is valid do nothing.

            Can raise:
                BusinessValidationFailure
        '''
        raise NotImplementedError()

    def get_extended_kyc(self, payment):
        ''' Returns the extended KYC information for this payment.
            In the format: (kyc_data, kyc_signature, kyc_certificate), where
            all fields are of type str.

            Can raise:
                   BusinessAsyncInterupt
                   BusinessNotAuthorized.
        '''
        raise NotImplementedError()

    def get_stable_id(self, payment):
        ''' Provides a stable ID for the payment.
            Returns: a stable ID for the VASP user.

            Can raise:
                BusinessAsyncInterupt,
                BusinessNotAuthorized. '''
        raise NotImplementedError()

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
            If any more KYC is necessary then return False.
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
        raise NotImplementedError()

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
        raise NotImplementedError()

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
        raise NotImplementedError()


class VASPInfo:
    """Contains information about VASPs"""

    def get_base_url(self):
        """ Get the base URL that manages off-chain communications.

            Returns a str: The base url of the VASP.

        """
        raise NotImplementedError()

    def get_peer_base_url(self, other_addr):
        """ Get the base URL that manages off-chain communications of an other
            VASP (identified by `other_addr`).

            Returns a str: The base url of the other VASP.
        """
        raise NotImplementedError()

    def is_authorised_VASP(self, certificate, other_addr):
        """ Check wether an incoming network request is authorised or not.
            This function checks (i) if the certificate comes from one
            of the authorised VASPS (ie. a that VASP has the authorised bit
            set on chains), and (ii) if the certificate belongs to the sender
            of the request (ie. the network client). Check (ii) ensure that a
            VASP is not impersonating one of the other authorised VASPs.

            The certificate is a pyOpenSSL X509 object:
            http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-x509.html

            Returns a bool: True or False
        """
        raise NotImplementedError()

    def get_TLS_certificate(self):
        """ Get the on-chain TLS certificate of the VASP to authenticate channels.

            Returns a str: path to the file containing the TLS certificatre.
        """
        raise NotImplementedError()

    def get_TLS_key(self):
        """ Get the on-chain TLS key of the VASP to authenticate channels.

            Returns a str: path to the file containing the TLS key.
        """
        raise NotImplementedError()

    def get_peer_TLS_certificate(self, other_addr):
        """ Get the on-chain TLS certificate of a peer VASP, identified by
            `other_addr`.

            Returns a str: path to the file containing the TLS certificate.
        """
        raise NotImplementedError()

    def get_all_peers_TLS_certificate(self):
        """ Get the on-chain TLS certificate of all authorised peer VASPs.

            Returns a str: path to a single file containing all TLS certificates.
        """
        raise NotImplementedError()


    # --- The functions below are currently unused ---


    def get_libra_address(self):
        """ The settlement Libra address for this channel"""
        raise NotImplementedError()

    def get_parent_address(self):
        """ The VASP Parent address for this channel. High level logic is common
        to all Libra addresses under a parent to ensure consistency and compliance."""
        raise NotImplementedError()

    def is_unhosted(self):
        """ Returns True if the other party is an unhosted wallet """
        raise NotImplementedError()
