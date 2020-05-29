""" Define the 'business logic' for the Off-chain protocols """

# ---------------------------------------------------------------------------


# A model for VASP business environment

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
    """ The interface a VASP should define to drive the Off-chain protocol. """

    async def notify_payment_update(self, other_address, seq, command, payment):
        """ An async method to notify the VASP that a successsful command has
        been sequenced resulting in a new or updated payment. This provides the
        VASP with full visibility into the sequence of payments. The command
        could have originated either from the other VASP or this VASP (see
        `command.origin` to determine this).

        Args:
            other_address (str): the encoded libra address of the other VASP.
            seq (int): the sequence number into the shared command sequence.
            command (ProtocolCommand): the command that lead to the new or updated payment.
            payment (PaymentObject): the payment resulting from this command.

        Returns nothing.
        """
        pass

    def open_channel_to(self, other_vasp_addr):
        """Requests authorization to open a channel to another VASP.
        If it is authorized nothing is returned. If not an exception is
        raised.

        Args:
            other_vasp_info (LibraAddress): The address of the other VASP.

        Raises:
            BusinessNotAuthorized: If the current VASP is not authorised
                    to connect with the other VASP.
        """
        raise NotImplementedError()  # pragma: no cover

    # ----- Actors -----

    def is_sender(self, payment):
        """Returns true if the VASP is the sender of a payment.

        Args:
            payment (PaymentCommand): The concerned payment.

        Returns:
            bool: Whether the VASP is the sender of the payment.
        """
        raise NotImplementedError()  # pragma: no cover

    def is_recipient(self, payment):
        """ Returns true if the VASP is the recipient of a payment.

        Args:
            payment (PaymentCommand): The concerned payment.

        Returns:
            bool: Whether the VASP is the recipient of the payment.
        """
        return not self.is_sender(payment)

    async def check_account_existence(self, payment):
        """ Checks that the actor (sub-account / sub-address) on this VASP
            exists. This may be either the recipient or the sender, since VASPs
            can initiate payments in both directions. If not throw an exception.

        Args:
            payment (PaymentCommand): The payment command containing the actors
                to check.

        Raises:
            BusinessValidationFailure: If the account does not exist.
        """
        raise NotImplementedError()  # pragma: no cover

# ----- VASP Signature -----

    def validate_recipient_signature(self, payment):
        """ Validates the recipient signature is correct. Raise an
            exception if the signature is invalid or not present.
            If the signature is valid do nothing.

        Args:
            payment (PaymentCommand): The payment command containing the
                signature to check.

        Raises:
            BusinessValidationFailure: If the signature is invalid
                    or not present.
        """
        raise NotImplementedError()  # pragma: no cover

    async def get_recipient_signature(self, payment):
        """ Gets a recipient signature on the payment ID.

        Args:
            payment (PaymentCommand): The payment to sign.
        """
        raise NotImplementedError()  # pragma: no cover

# ----- KYC/Compliance checks -----

    async def next_kyc_to_provide(self, payment):
        ''' Returns the level of kyc to provide to the other VASP based on its
            status. Can provide more if deemed necessary or less.

            Args:
                payment (PaymentCommand): The concerned payment.

            Returns:
                Status: A set of status indicating to level of kyc to provide,
                that can include:
                    - `status_logic.Status.needs_kyc_data`
                    - `status_logic.Status.needs_recipient_signature`

            An empty set indicates no KYC should be provided at this moment.

            Raises:
                BusinessForceAbort : To abort the payment.
        '''
        raise NotImplementedError()  # pragma: no cover

    async def next_kyc_level_to_request(self, payment):
        ''' Returns the next level of KYC to request from the other VASP. Must
            not request a level that is either already requested or provided.

            Args:
                payment (PaymentCommand): The concerned payment.

            Returns:
                Status: Returns Status.none or the current status
                if no new information is required, otherwise a status
                code from:
                    - `status_logic.Status.needs_kyc_data`
                    - `status_logic.Status.needs_recipient_signature`

            Raises:
                BusinessForceAbort : To abort the payment.
        '''
        raise NotImplementedError()  # pragma: no cover


    async def get_extended_kyc(self, payment):
        ''' Provides the extended KYC information for this payment.

            Args:
                payment (PaymentCommand): The concerned payment.

            Raises:
                   BusinessNotAuthorized: If the other VASP is not authorized to
                    receive extended KYC data for this payment.

            Returns:
                KYCData: Returns the extended KYC information for
                this payment.
        '''
        raise NotImplementedError()  # pragma: no cover

# ----- Settlement -----

    async def ready_for_settlement(self, payment):
        ''' Indicates whether a payment is ready for settlement as far as this
            VASP is concerned. Once it returns True it must never return False.

            In particular it **must** check that:
                - Accounts exist and have the funds necessary.
                - Sender of funds intends to perform the payment (VASPs can
                  initiate payments from an account on the other VASP.)
                - KYC information provided **on both sides** is correct and to
                  the VASPs satisfaction. On payment creation a VASP may suggest
                  KYC information on both sides.

            If all the above are true, then return `True`.
            If any of the above are untrue throw an BusinessForceAbort.
            If any more KYC is necessary then return `False`.

            This acts as the finality barrier and last check for this VASP.
            After this call returns True this VASP can no more abort the
            payment (unless the other VASP aborts it).

            Args:
                payment (PaymentCommand): The concerned payment.

            Raises:
                BusinessForceAbort: If any of the above condutions are untrue.

            Returns:
                bool: Whether the VASP is ready to settle the payment.
            '''
        raise NotImplementedError()  # pragma: no cover

    async def has_settled(self, payment):
        ''' Returns whether the payment was settled on chain. If the payment can
            be settled also package it and settle it on chain. This function
            may be called multiple times for the same payment, but any on-chain
            operation should be performed only once per payment.

            Cannot raise:
                BusinessForceAbort

            since this is called past the finality barrier.

            Args:
                payment (PaymentCommand): The concerned payment.

            Returns:
                bool: Whether the payment was settled on chain.
        '''
        raise NotImplementedError()  # pragma: no cover


class VASPInfo:
    """Contains information about VASPs"""

    def get_base_url(self):
        """ Get the base URL that manages off-chain communications.

            Returns:
                str: The base url of the VASP.

        """
        raise NotImplementedError()  # pragma: no cover

    def get_peer_base_url(self, other_addr):
        """ Get the base URL that manages off-chain communications of the other
            VASP.

            Args:
                other_addr (LibraAddress): The address of the other VASP.

            Returns:
                str: The base url of the other VASP.
        """
        raise NotImplementedError()  # pragma: no cover

    # --- The functions below are currently unused ---

    def get_libra_address(self):
        """ The settlement Libra address for this channel.

            Returns:
                LibraAddress: The Libra address.

        """
        raise NotImplementedError()  # pragma: no cover

    def get_parent_address(self):
        """ The VASP Parent address for this channel. High level logic is common
        to all Libra addresses under a parent to ensure consistency and
        compliance.

        Returns:
            LibraAddress: The Libra address of the parent VASP.

        """
        raise NotImplementedError()  # pragma: no cover

    def is_unhosted(self, other_addr):
        """ Returns True if the other party is an unhosted wallet.

            Args:
                other_addr (LibraAddress): The address of the other VASP.

            Returns:
                bool: Whether the other VASP is an unhosted wallet.

        """
        raise NotImplementedError()  # pragma: no cover

    def get_peer_compliance_verification_key(self, other_addr):
        """ Returns the compliance verfication key of the other VASP.

        Args:
            other_addr (LibraAddress): The address of the other VASP.

        Returns:
            ComplianceKey: The compliance verification key of the other VASP.
        """
        raise NotImplementedError()  # pragma: no cover

    def get_peer_compliance_signature_key(self, my_addr):
        """ Returns the compliance signature (secret) key of the VASP.

        Args:
            my_addr (LibraAddress): The Libra address of the VASP.

        Returns:
            ComplianceKey: The compliance key of the VASP.
        """
        raise NotImplementedError()  # pragma: no cover
