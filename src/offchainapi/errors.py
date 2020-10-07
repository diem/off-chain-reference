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
    # but the command is different. As a reult the command will not
    # considered further, and a protocol error with this code is returned.
    conflict = 'conflict'

    # Indicates that some other command has a lock on one or more dependencies
    # necessary for this command to commit. As a result the command should be
    # sent again in a while, once the other command status has been resolved.
    # The command is discarded, with a protocol error, and should be
    # resubmitted later.
    wait = 'wait'

    # Indicates that a parsing error has occured. The request is therefore
    # discarded with a protocol error.
    parsing_error = 'parsing_error'

    # Indicates that the signature verification failed
    invalid_signature = 'invalid_signature'

    # One of the dependencies is missing -- this is recoverable if it becomes
    # available down the line. Whence it is a protocol error only.
    missing_dependencies = 'missing_dependencies'

    # Codes for command errors
    # ------------------------
    #
    # (Command errors are final: the command is stored alongside the error,
    # and the command with the same cid will always fail with the same error.
    # Therefore a new request)

    # Indicates that one or more dependencies are missing, or have already been
    # used by another command. As a result committing this command may result in
    # a conflict / inconsistent state. The command is therefore permanently
    # rejected with an idempotent command error.

    used_dependencies    = 'used_dependencies'


    # Payment command error codes
    # ---------------------------
    #
    # (Error codes specific to validating PaymentCommands. A validaton error
    # as all command errors, results in the request with this cid to alreays
    # fail.)

    payment_invalid_libra_address = 'payment_invalid_libra_address'
    payment_invalid_libra_subaddress = 'payment_invalid_libra_subaddress'
    payment_wrong_status = 'payment_wrong_status'
    payment_changed_other_actor = 'payment_changed_other_actor'
    payment_wrong_actor = 'payment_wrong_actor'
    payment_wrong_structure = 'payment_wrong_structure'
    payment_dependency_error = 'payment_dependency_error'
    payment_wrong_recipient_signature = 'payment_wrong_recipient_signature'

    ## Abort codes
    payment_insufficient_funds = 'payment_insufficient_funds'
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
