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

    # Codes for command errors
    # ------------------------
    #
    # (Command errors are final: the command is stored alongside the error,
    # and the command with the same cid will always fail with the same error.
    # Therefore a new request)

    # Indicates that one or more dependencies are missing, or have already been
    # used by another command. As a result committing this command may result in
    # a conflict / inconsistent state. The command is therefore permanantly
    # rejected with an idempotent command error.
    missing_dependencies = 'missing_dependencies'

    # Payment command error codes
    # ---------------------------
    #
    # (Error codes specific to validating PaymentCommands. A validaton error
    # as all command errors, results in the request with this cid to alreays
    # fail.)

    payment_wrong_status = 'payment_wrong_status'
    payment_changed_other_actor = 'payment_changed_other_actor'
    payment_wrong_actor = 'payment_wrong_actor'
    payment_wrong_structure = 'payment_wrong_structure'
    payment_dependency_error = 'payment_dependency_error'

    # Test codes
    test_error_code = 'test_error_code'
