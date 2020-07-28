from enum import Enum

class OffChainErrorCode(Enum):

    # Codes for protocol errors
    conflict = 'conflict'
    wait = 'wait'
    parsing_error = 'parsing_error'

    # Codes for command errors
    missing_dependencies = 'missing_dependencies'
    command_validation_error = 'command_validation_error'

    # Payment command error codes
    payment_wrong_status = 'payment_wrong_status'
    payment_changed_other_actor = 'payment_changed_other_actor'
    payment_wrong_actor = 'payment_wrong_actor'
    payment_wrong_structure = 'payment_wrong_structure'
    payment_dependency_error = 'payment_dependency_error'

    # Test codes
    test_error_code = 'test_error_code'
