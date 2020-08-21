# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .utils import StructureException, StructureChecker, \
    REQUIRED, OPTIONAL, WRITE_ONCE, UPDATABLE, \
    JSONSerializable, JSONFlag
from .shared_object import SharedObject
from .status_logic import Status
from .libra_address import LibraAddress

import json


class KYCData(StructureChecker):
    """ The KYC data that can be attached to payments.

        Args:
            kyc_json_blob (str): blob containing KYC data.
    """

    fields = [
        ("payload_type", str, REQUIRED, WRITE_ONCE),
        ("payload_version", int, REQUIRED, WRITE_ONCE),
        ("type", str, REQUIRED, WRITE_ONCE),
        ("given_name", str, OPTIONAL, WRITE_ONCE),
        ("surname", str, OPTIONAL, WRITE_ONCE),
        ("address", dict, OPTIONAL, WRITE_ONCE),
        ("dob", str, OPTIONAL, WRITE_ONCE),
        ("place_of_birth", dict, OPTIONAL, WRITE_ONCE),
        ("national_id", dict, OPTIONAL, WRITE_ONCE),
        ("legal_entity_name", str, OPTIONAL, WRITE_ONCE),
        ("other", dict, OPTIONAL, WRITE_ONCE),
    ]

    def __init__(self, kyc_dict):
        # Keep as blob since we need to sign / verify byte string.
        StructureChecker.__init__(self)
        self.update(kyc_dict)

    def parse(self):
        """ Parse the KYC blob and return a data dictionary.

            Returns:
                dict: KYC data as a dictionary.
        """
        return self.data

    def custom_update_checks(self, diff):
        """ Override StructureChecker. """

        # Check all data is JSON serializable
        json.dumps(diff)

        types = ['individual', 'entity']
        if 'type' not in diff:
            raise StructureException('Missing: field type')
        if diff['type'] not in types:
            raise StructureException(f'Wrong KYC "type": {diff["type"]}')


class StatusObject(StructureChecker):
    fields = [
        ('status', str, REQUIRED, UPDATABLE),
        ('abort_code', str, OPTIONAL, UPDATABLE),
        ('abort_message', str, OPTIONAL, UPDATABLE)
    ]

    def __init__(self, status, abort_code=None, abort_message=None):
        StructureChecker.__init__(self)

        if isinstance(status, Status):
            status = str(status)

        if abort_code is None:
            self.update({
                'status': status,
            })
        else:
            self.update({
                'status': status,
                'abort_code': abort_code,
                'abort_message': abort_message
            })

    def as_status(self):
        ''' Returns a Status enum object. '''
        return Status[self.status]

    def custom_update_checks(self, diff):
        """ Override StructureChecker. """

        # Ensure we have a valid status:
        try:
            status = Status[diff['status']]
        except KeyError:
            raise StructureException(f'Unknown status type: {diff["status"]}.')

        if status == Status.abort and not ('abort_code' in diff and 'abort_message' in diff):
            raise StructureException('Abort code and message is required.')

        if status != Status.abort and ('abort_code' in diff or 'abort_message' in diff):
            raise StructureException(f'Status {diff["status"]} cannot have a abort code or message.')

class PaymentActor(StructureChecker):
    """ Represents a payment actor.

        Args:
            address (str): The bech32 encoded str format of LibraAddress
            status (utils.Status): The payment status for this actor.
            metadata (list): Arbitrary metadata.
    """

    fields = [
        ('address', str, REQUIRED, WRITE_ONCE),
        ('kyc_data', KYCData, OPTIONAL, WRITE_ONCE),
        ('additional_kyc_data', KYCData, OPTIONAL, WRITE_ONCE),
        ('status', StatusObject, REQUIRED, UPDATABLE),
        ('metadata', list, REQUIRED, UPDATABLE)
    ]

    def __init__(self, address, status, metadata):
        StructureChecker.__init__(self)
        self.update({
            'address': address,
            'status': status,
            'metadata': metadata
        })

    def get_onchain_address_encoded_str(self):
        """
        Returns an encoded str representation of LibraAddress containing
        only the onchain address
        """
        return LibraAddress.from_encoded_str(self.address).get_onchain_encoded_str()

    def custom_update_checks(self, diff):
        """ Override StructureChecker. """

        # Metadata can only be strings
        if 'metadata' in diff:
            for item in diff['metadata']:
                if not isinstance(item, str):
                    raise StructureException(
                        'Wrong type: metadata item type expected str, got %s' %
                        type(item))

    def add_kyc_data(self, kyc_data):
        """ Add extended KYC information and kyc signature.

        Args:
            kyc_data (str): The KYC data object
        """
        self.update({
            'kyc_data': kyc_data,
        })

    def add_additional_kyc_data(self, additional_kyc_data):
        """ Add extended KYC information and kyc signature.

        Args:
            kyc_data (str): The KYC data object
        """
        self.update({
            'additional_kyc_data': additional_kyc_data,
        })

    def add_metadata(self, item):
        """ Add an item to the metadata

        Args:
            item (*): The item to add to the metadata.
        """
        self.update({
            'metadata': self.data['metadata'] + [item]
        })

    def change_status(self, status):
        """ Change the payment status for this actor>

        Args:
            status (utils.Status): The new status.
        """
        self.update({
            'status': status
        })


class PaymentAction(StructureChecker):
    fields = [
        ('amount', int, REQUIRED, WRITE_ONCE),
        ('currency', str, REQUIRED, WRITE_ONCE),
        ('action', str, REQUIRED, WRITE_ONCE),
        ('timestamp', str, REQUIRED, WRITE_ONCE)
    ]

    def __init__(self, amount, currency, action, timestamp):
        """ Represents a payment account; eg. make a payment.

        Args:
            amount (int): The amount of the payment.
            currency (str): The currency of the payment.
            action (str): The action of the payment; eg. a refund.
            timestamp (str): The timestamp of the payment.
        """
        StructureChecker.__init__(self)
        self.update({
            'amount': amount,
            'currency': currency,
            'action': action,
            'timestamp': timestamp
        })

    def custom_update_checks(self, diff):
        """ Override StructureChecker. """
        if 'amount' in diff and not diff['amount'] > 0:
            raise StructureException('Wrong amount: must be positive')

        # TODO[issue #1]: Check timestamp format?


@JSONSerializable.register
class PaymentObject(SharedObject, StructureChecker, JSONSerializable):
    """ Represents a payment object.

        Args:
            sender (PaymentActor): The sender actor.
            receiver (PaymentActor): The recipient actor.
            reference_id (str): The payment reference.
            original_payment_reference_id (str): Original payment's reference.
            description (str): A string description.
            action (PaymentAction): The payment action.
    """

    fields = [
        ('sender', PaymentActor, REQUIRED, WRITE_ONCE),
        ('receiver', PaymentActor, REQUIRED, WRITE_ONCE),
        ('reference_id', str, REQUIRED, WRITE_ONCE),
        ('original_payment_reference_id', str, OPTIONAL, WRITE_ONCE),
        ('description', str, OPTIONAL, WRITE_ONCE),
        ('action', PaymentAction, REQUIRED, WRITE_ONCE),
        ('recipient_signature', str, OPTIONAL, WRITE_ONCE)
    ]

    def __init__(self, sender, receiver, reference_id,
                 original_payment_reference_id, description, action):
        SharedObject.__init__(self)
        StructureChecker.__init__(self)
        self.notes = {}

        main_state = {
            'sender': sender,
            'receiver': receiver,
            'reference_id': reference_id,
            'action': action
        }

        # Optional fields are only included if not None

        if original_payment_reference_id is not None:
            main_state['original_payment_reference_id'] \
                = original_payment_reference_id

        if description is not None:
            main_state['description'] \
                = description

        self.update(main_state)


    @classmethod
    def create_from_record(cls, diff):
        """ Create a apyment object from a diff.

        Args:
            diff (str): The diff from which to create the payment.

        Returns:
            PaymentObject: The created payment object.
        """
        self = PaymentObject.from_full_record(diff)
        SharedObject.__init__(self)
        return self

    def new_version(self, new_version=None, store=None):
        """ Override SharedObject. """
        clone = SharedObject.new_version(self, new_version, store)
        clone.flatten()
        return clone

    def add_recipient_signature(self, signature):
        """ Update the recipient signature.

        Args:
            signature (str): The recipient's signature.
        """
        self.update({
            'recipient_signature': signature
        })

    def get_json_data_dict(self, flag, update_dict=None):
        ''' Override SharedObject. '''
        json_data = {}
        json_data = SharedObject.get_json_data_dict(self, flag, json_data)
        json_data = self.get_full_diff_record(json_data)
        return json_data

    @classmethod
    def from_json_data_dict(cls, data, flag, self=None):
        ''' Override SharedObject. '''
        self = PaymentObject.from_full_record(data)
        SharedObject.from_json_data_dict(data, flag, self)
        return self

    def __str__(self):
        return json.dumps(self.get_json_data_dict(JSONFlag.STORE), indent=4)
