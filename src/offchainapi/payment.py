from .utils import StructureException, StructureChecker, \
    REQUIRED, OPTIONAL, WRITE_ONCE, UPDATABLE, \
    JSONSerializable
from .shared_object import SharedObject
from .status_logic import Status

import json


class KYCData(StructureChecker):
    """ The KYC data that can be attached to payments.

        Args:
            kyc_json_blob (str): blob containing KYC data.
    """

    fields = [
        ('blob', str, REQUIRED, WRITE_ONCE)
    ]

    def __init__(self, kyc_json_blob):
        # Keep as blob since we need to sign / verify byte string.
        StructureChecker.__init__(self)
        self.update({
            'blob': kyc_json_blob
        })

    def parse(self):
        """ Parse the KYC blob and return a data dictionary.

            Returns:
                dict: KYC data as a dictionary.
        """
        return json.loads(self.data['blob'])

    def custom_update_checks(self, diff):
        """ Override StructureChecker. """
        # Tests JSON parsing before accepting blob.
        if 'blob' in diff:
            try:
                data = json.loads(diff['blob'])
            except Exception as e:
                raise StructureException(
                    f'JSON Parsing Exception :'
                    f'ensure KYCData is a valid JSON object ({e})'
                )

            if 'payment_reference_id' not in data:
                raise StructureException('Missing: field payment_reference_id')

            types = ['individual', 'entity']
            if 'type' not in data:
                raise StructureException('Missing: field type')
            if data['type'] not in types:
                raise StructureException(f'Wrong KYC "type": {data["type"]}')



class PaymentActor(StructureChecker):
    """ Represents a payment actor.

        Args:
            address (LibraAddress): The address of the VASP.
            subaddress (str): The subaddress of the account on the VASP.
            status (utils.Status): The payment status for this actor.
            metadata (list): Arbitrary metadata.
    """

    fields = [
        ('address', str, REQUIRED, WRITE_ONCE),
        ('subaddress', str, REQUIRED, WRITE_ONCE),
        ('kyc_data', KYCData, OPTIONAL, WRITE_ONCE),
        ('status', Status, REQUIRED, UPDATABLE),
        ('metadata', list, REQUIRED, UPDATABLE)
    ]

    def __init__(self, address, subaddress, status, metadata):
        StructureChecker.__init__(self)
        self.update({
            'address': address,
            'subaddress': subaddress,
            'status': status,
            'metadata': metadata
        })

    def custom_update_checks(self, diff):
        """ Override StructureChecker. """

        if 'status' in diff and not isinstance(diff['status'], Status):
            raise StructureException('Wrong status: %s' % diff['status'])

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
            kyc_data (str): The KYC data.
            kyc_signature (str): The KYC signature.
            kyc_certificate (str): The KYC certificate.
        """
        self.update({
            'kyc_data': kyc_data,
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
        self.update({
            'sender': sender,
            'receiver': receiver,
            'reference_id': reference_id,
            'original_payment_reference_id': original_payment_reference_id,
            'description': description,
            'action': action
        })

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

    def new_version(self, new_version=None):
        """ Override SharedObject. """
        clone = SharedObject.new_version(self, new_version)
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
