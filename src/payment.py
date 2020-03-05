from decimal import Decimal

from executor import SharedObject
from utils import StructureException, StructureChecker, \
    REQUIRED, OPTIONAL, WRITE_ONCE, UPDATABLE

from status_logic import Status
import json

class KYCData(StructureChecker):
    fields = [
        ('blob', str, REQUIRED, WRITE_ONCE)
    ]

    def __init__(self, kyc_json_blob):
        # Keep as blob since we need to sign / verify byte string
        StructureChecker.__init__(self)
        self.update({
            'blob': kyc_json_blob
        })

    def parse(self):
        """ Parse the KYC blob and return a data dictionary. """
        json.loads(self.data['blob'])

    def custom_update_checks(self, diff):
        # Tests JSON parsing before accepting blob
        if 'blob' in diff:
            data = json.loads(diff['blob'])
            if not 'payment_reference_id' in data:
                raise StructureException('Missing: field payment_reference_id')
            if not 'type' in data:
                raise StructureException('Missing: field type')


class PaymentActor(StructureChecker):
    fields = [
        ('address', str, REQUIRED, WRITE_ONCE),
        ('subaddress', str, REQUIRED, WRITE_ONCE),
        ('stable_id', str, OPTIONAL, WRITE_ONCE),
        ('kyc_data', KYCData, OPTIONAL, WRITE_ONCE),
        ('kyc_signature', str, OPTIONAL, WRITE_ONCE),
        ('kyc_certificate', str, OPTIONAL, WRITE_ONCE),
        ('status', str, REQUIRED, UPDATABLE),
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
        # If any of kyc data, signarure or certificate is provided, we expect
        # all the other fields as well
        if 'kyc_data' in diff and 'kyc_signature' not in diff \
                or 'kyc_certificate' in diff and 'kyc_signature' not in diff:
            raise StructureException('Missing: field kyc_signature')
        if 'kyc_data' in diff and 'kyc_certificate' not in diff \
                or 'kyc_signature' in diff and 'kyc_certificate' not in diff:
            raise StructureException('Missing: field kyc_certificate')
        if 'kyc_signature' in diff and 'kyc_data' not in diff \
                or 'kyc_certificate' in diff and 'kyc_data' not in diff:
            raise StructureException('Missing: field kyc_data')

        if 'status' in diff and not diff['status'] in Status:
            raise StructureException('Wrong status: %s' % diff['status'])

        # Metadata can only be strings
        if 'metadata' in diff:
            for item in diff['metadata']:
                if not isinstance(item, str):
                    raise StructureException(
                        'Wrong type: metadata item type expected str, got %s' %
                        type(item))

    def add_kyc_data(self, kyc_data, kyc_signature, kyc_certificate):
        ''' Add extended KYC information and kyc signature '''
        self.update({
            'kyc_data': kyc_data,
            'kyc_signature': kyc_signature,
            'kyc_certificate': kyc_certificate
        })

    def add_metadata(self, item):
        ''' Add an item to the metadata '''
        self.update({
            'metadata': self.data['metadata'] + [item]
        })

    def change_status(self, status):
        ''' Change the payment status for this actor '''
        self.update({
            'status': status
        })

    def add_stable_id(self, stable_id):
        ''' Add a stable id for this actor '''
        self.update({
            'stable_id': stable_id
        })


class PaymentAction(StructureChecker):
    fields = [
        ('amount', Decimal, REQUIRED, WRITE_ONCE),
        ('currency', str, REQUIRED, WRITE_ONCE),
        ('action', str, REQUIRED, WRITE_ONCE),
        ('timestamp', str, REQUIRED, WRITE_ONCE)
    ]

    def __init__(self, amount, currency, action, timestamp):
        StructureChecker.__init__(self)
        self.update({
            'amount': amount,
            'currency': currency,
            'action': action,
            'timestamp': timestamp
        })

    def custom_update_checks(self, diff):
        if 'amount' in diff and not diff['amount'] > 0:
            raise StructureException('Wrong amount: must be positive')

        # TODO[issue #1]: Check timestamp format?


class PaymentObject(SharedObject, StructureChecker):

    fields = [
        ('sender', PaymentActor, REQUIRED, WRITE_ONCE),
        ('receiver', PaymentActor, REQUIRED, WRITE_ONCE),
        ('reference_id', str, REQUIRED, WRITE_ONCE),
        ('original_payment_reference_id', str, REQUIRED, WRITE_ONCE),
        ('description', str, REQUIRED, WRITE_ONCE),
        ('action', PaymentAction, REQUIRED, WRITE_ONCE),
        ('recipient_signature', str, OPTIONAL, WRITE_ONCE)
    ]

    def __init__(self, sender, receiver, reference_id,
                 original_payment_reference_id, description, action):
        SharedObject.__init__(self)
        StructureChecker.__init__(self)
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
        self = PaymentObject.from_full_record(diff)
        SharedObject.__init__(self)
        return self

    def new_version(self, new_version = None):
        ''' Also flatten object with a new version '''
        clone = SharedObject.new_version(self, new_version)
        clone.flatten()
        return clone

    def add_recipient_signature(self, signature):
        ''' Update the recipient signature '''
        self.update({
            'recipient_signature': signature
        })
