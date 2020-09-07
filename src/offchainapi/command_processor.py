# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .errors import OffChainErrorCode

class CommandValidationError(Exception):
    def __init__(self, error_code, error_message):
        self.error_code = error_code
        if not isinstance(error_code, OffChainErrorCode):
            raise RuntimeError(f'Error code must be of type OffChainErrorCode, not {type(error_code)}')
        self.error_message = error_message


class CommandProcessor:

    def business_context(self):
        ''' Provides the business context associated with this processor.

            Returns:
                The business context of the VASP
                implementing the BusinessContext interface.
        '''
        raise NotImplementedError()  # pragma: no cover

    def check_command(self, my_address, other_address, command):
        ''' Called when receiving a new payment command to validate it.

            All checks here are blocking subsequent comments, and therefore they
            must be quick to ensure performance. As a result we only do local
            syntactic checks hat require no lookup into the VASP potentially
            remote stores or accounts.

            Args:
                my_address (LibraAddress): own address.
                other_address (LibraAddress): other party address.
                command (PaymentCommand): The current payment.

            Returns:
                None: in case no errors are found.

            Raises:
                CommandValidationError: to indicate an error.
        '''
        raise NotImplementedError()  # pragma: no cover

    def process_command(self, other_addr,
                        command, seq, status, error=None):
        """Processes a command to generate more subsequent commands.
            This schedules a task that will be executed later.

            Args:
                other_addr (LibraAddress): the address of the other party.
                command (PaymentCommand): The current payment command.
                seq (int): The sequence number of the payment command.
                status (bool): Whether the command is a success or failure.
                error (Exception, optional): The exception, if the command is a
                        failure. Defaults to None.

            Returns:
                Future: A task that will be executed later.
        """
        raise NotImplementedError()  # pragma: no cover
