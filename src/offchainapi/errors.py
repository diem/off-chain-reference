# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

class OffChainErrorCode(Enum):

    # Codes for protocol errors
    # -------------------------
    #
    # (Protocol error are those that discard the request, rather than storing
    # it along a permanent error. Either because the fault is transient or
    # because the request/command is too damaged to have meaning.)


    # Indicates that a request with the same cid has already been received,
    # but the command is different. As a reult the command will not be
    # considered further, and a protocol error with this code is returned.
    conflict = 'conflict'

    # Indicates that some other command has a lock on one or more dependencies
    # necessary for this command to commit. As a result the command should be
    # resent again in a while, once the other command status has been resolved.
    # The command is discarded, with a protocol error, and should be
    # resubmitted later.
    wait = 'wait'

    # Indicates that a parsing error has occured at the level of the JSON parser.
    # The request is therefore discarded with a protocol error, since we may not
    # be able to recover a cid.
    parsing_error = 'parsing_error'

    # Indicates that the signature verification failed, and therefore the
    # command is discarded as it may not be originating from the legitimate
    # other VASP.
    invalid_signature = 'invalid_signature'

    # One of the dependencies is missing -- this is recoverable if it becomes
    # available down the line. Whence it is a protocol error only; the command
    # is ignored and can be re-sent later if the dependency becomes available.
    missing_dependencies = 'missing_dependencies'

    # Codes for command errors
    # ------------------------
    #
    # (Command errors are final: the command is stored alongside the error,
    # and the command with the same cid will always fail with the same error.
    # Therefore a new request)

    # Indicates that one or more dependencies have already been used by another
    # command. As a result committing this command would result in
    # a conflict / inconsistent state. The command is therefore recorded as
    # permanently rejected with an idempotent command error.
    used_dependencies    = 'used_dependencies'


    # Payment command error codes
    # ---------------------------
    #
    # (Error codes specific to validating PaymentCommands. A validaton error
    # as all command errors, results in the request with this cid to alreays
    # fail.)


    # Indicates that the libra subaddress in the payment (either sender or
    # receiver) could not be parsed as a Libra Address. Used when checking
    # all commands creating or updating payments.
    payment_invalid_libra_address = 'payment_invalid_libra_address'

    # Indicates that the subaddress component of the libra payment (either
    # sender or receiver) is empty, which is invalid. Checked for all commands
    # updating a payment.
    payment_invalid_libra_subaddress = 'payment_invalid_libra_subaddress'

    # Indicates that either the initial set of sender and receiver status,
    # or a status transition updating these as part of a command are invalid.
    # This is checked for every command creating or updating a payment.
    payment_wrong_status = 'payment_wrong_status'

    # Indicates that a command updating a payment modifies the actor (sender
    # or receiver) representing the other VASP. After the initial payment
    # definition each VASP may only update the payment actor representing itself.
    # Checked for all commands updating a payment.
    payment_changed_other_actor = 'payment_changed_other_actor'

    # Indicates that the command creates or updates a payment involving VASPs
    # that are different from the VASPs at either ends of the channel on which
    # it was sent.
    payment_wrong_actor = 'payment_wrong_actor'

    # Indicates that the _reads or _writes fields are wrong. They may have
    # two wrong number of elements, or not refer to the same object by reference ID.
    # Or that the reference ID format of the payment has an incorrect format, or
    # is updated by a command.
    payment_wrong_structure = 'payment_wrong_structure'

    # In dicates that an invalid recipient compliance signature
    # on the payment reference ID was included in the payment. Checked
    # for all payment command updates .
    payment_wrong_recipient_signature = 'payment_wrong_recipient_signature'


    ## Abort codes

    # These error codes may be used by VASP business logic to indicate reasons
    # for aborting a payment.

    # Indicates and abort occured due to insufficient funds in the
    # sender account.
    payment_insufficient_funds = 'payment_insufficient_funds'

    # General opaque error indicating that something went wrong in the VASP
    # as part of processing a payment, and an error was logged locally (but
    # not communicated to the other VASP.)
    payment_vasp_error = 'payment_vasp_error'

    # Test codes
    test_error_code = 'test_error_code'


class OffChainException(Exception):
    """ The base exception for exceptions and errors from the off-chain api """
    pass

class OffChainProtocolError(OffChainException):
    ''' This class denotes protocol errors, namely errors at the
        OffChain protocols level rather than the command sequencing level.

        This is an Exception that is thrown within the Python program
        to represent the error, rather than the message type which is
        OffChainErrorObject.
        '''

    @staticmethod
    def make(protocol_error):
        """Make an OffChainProtocolError with a given error.

        Args:
            protocol_error (str): The protocol error representation.

        Returns:
            OffChainProtocolError: The error object.
        """
        self = OffChainProtocolError()
        self.protocol_error = protocol_error
        return self

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'OffChainProtocolError: {str(self.protocol_error)}'
