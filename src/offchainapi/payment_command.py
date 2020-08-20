# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .protocol_command import ProtocolCommand
from .payment import PaymentObject
from .utils import JSONSerializable
from .command_processor import CommandValidationError
from .errors import OffChainErrorCode


# Functions to check incoming diffs
class PaymentLogicError(CommandValidationError):
    """ Indicates a payment processing error. """
    pass


# Note: ProtocolCommand is JSONSerializable, so no need to extend again.
@JSONSerializable.register
class PaymentCommand(ProtocolCommand):
    ''' Creates a new ``PaymentCommand`` based on a given payment.

        The  command creates the object version of the payment given
        and depends on any previous versions of the given payment.

        Args:
            payment (PaymentObject): The payment from which to build the command.
    '''

    def __init__(self, payment):
        ProtocolCommand.__init__(self)
        ref_id = payment.reference_id
        self.dependencies = [(ref_id, payment.previous_version)] if payment.previous_version else []
        self.creates_versions = [(ref_id, payment.get_version())]
        self.command = payment.get_full_diff_record()

    def __eq__(self, other):
        return ProtocolCommand.__eq__(self, other) \
            and self.command == other.command

    def get_request_cid(self):
        """ Suggests the cid that the request with this command should contain.

            Each cid should ideally be unique, and the same command should create a
            request with the same cid. """

        _, new_version = self.creates_versions[0]
        return new_version


    def get_object(self, version_number, dependencies):
        """ Returns the new payment object defined by this command. Since this
        may depend on a previous payment (when it is an update) we need to
        provide a dictionary of its dependencies.

        Args:
            version_number (int): The version number
            dependencies (list): The list of dependencies.

        Raises:
            PaymentLogicError: If the payment depends on more than one other
                               payment.

        Returns:
            PaymentObject: The updated payment.
        """
        # First find dependencies & created objects.
        new_version = self.get_new_version()
        if new_version != version_number:
            raise PaymentLogicError(
                OffChainErrorCode.payment_dependency_error,
                f"Unknown object {version_number} (only know {new_version})"
            )

        # This indicates the command creates a fresh payment.
        if len(self.dependencies) == 0:
            payment = PaymentObject.create_from_record(self.command)
            payment.set_version(new_version)
            return payment

        # This command updates a previous payment.
        elif len(self.dependencies) == 1:
            _, dep = self.dependencies[0]
            if dep not in dependencies:
                raise PaymentLogicError(
                    OffChainErrorCode.payment_wrong_structure,
                    f'Cound not find payment dependency: {dep}'
                )
            dep_object = dependencies[dep]

            # Need to get a deepcopy new version.
            updated_payment = dep_object.new_version(new_version)
            PaymentObject.from_full_record(
                self.command, base_instance=updated_payment)
            return updated_payment

        raise PaymentLogicError(
            OffChainErrorCode.payment_wrong_structure,
            "Can depdend on no or one other payment.")

    def get_payment(self, dependencies):
        version = self.get_new_version()
        return self.get_object(version, dependencies)

    def get_json_data_dict(self, flag):
        ''' Get a data dictionary compatible with JSON serilization
            (json.dumps).

            Args:
                flag (utils.JSONFlag): whether the JSON is intended
                    for network transmission (NET) to another party or local
                    storage (STORE).

            Returns:
                dict: A data dictionary compatible with JSON serilization.
        '''
        data_dict = ProtocolCommand.get_json_data_dict(self, flag)
        data_dict['payment'] = self.command
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        """ Construct the object from a serlialized JSON
            data dictionary (from json.loads).

        Args:
            data (dict): A JSON data dictionary.
            flag (utils.JSONFlag): whether the JSON is intended
                    for network transmission (NET) to another party or local
                    storage (STORE).

        Raises:
            PaymentLogicError: If there is an error while creating the payment.

        Returns:
            PaymentCommand: A PaymentCommand from the input data.
        """
        self = super().from_json_data_dict(data, flag)
        # Thus super() is magic, but do not worry we get the right type:
        assert isinstance(self, PaymentCommand)
        self.command = data['payment']

        if len(self.dependencies) > 1:
            # TODO: Test for such errors within protocol.py tests.
            raise PaymentLogicError(
                OffChainErrorCode.payment_wrong_structure,
                "A payment can only depend on a single previous payment"
            )

        if len(self.creates_versions) != 1:
            # TODO: Test for such errors within protocol.py tests.
            raise PaymentLogicError(
                OffChainErrorCode.payment_wrong_structure,
                "A payment always creates a new payment")

        return self

    # Helper functions for payment commands specifically
    def get_previous_version(self):
        """ Returns the version of the previous payment, or None if this
        command creates a new payment

        Returns:
            The version of the previous payment, or None if this
            command creates a new payment.
        """
        # This is  ensured from the constructors.
        assert len(self.dependencies) in [0, 1]
        if len(self.dependencies) == 0:
            return None
        _, prev_version =  self.dependencies[0]
        return prev_version

    def get_new_version(self):
        ''' Returns the version number of the payment.

            Returns:
                int: The version number of the payment.
        '''
        # Ensured from the constructors.
        assert len(self.creates_versions) == 1
        _, new_version = self.creates_versions[0]
        return new_version
