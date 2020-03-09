from business import BusinessContext, BusinessAsyncInterupt, BusinessForceAbort, BusinessValidationFailure
from protocol import OffChainVASP
from protocol_messages import CommandRequestObject
from payment_logic import PaymentCommand
from status_logic import Status

from test_protocol import FakeAddress, FakeVASPInfo

import json

business_config = """[
    {
        "account": "1",
        "stable_id": "A",
        "balance": 10.0,
        "business": false,
        "kyc_data" : "{ 'name' : 'Alice' }"
    },
    {
        "account": "2",
        "stable_id": "B",
        "balance": 100.0,
        "business": true,
        "kyc_data" : "{ 'name' : 'Bob' }"
    }
]"""

class sample_business(BusinessContext):
    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.accounts_db = json.loads(business_config)
    
    # Helper functions for the business
    def get_account(self, subaddress):
        for acc in self.accounts_db:
            if acc['account'] ==  subaddress:
                return acc

    def assert_payment_for_vasp(self, payment):
        if payment.data['sender'].data['address'] == str(self.my_addr.own_address.addr) or \
            payment.data['receiver'].data['address'] == str(self.my_addr.own_address.addr):
            return
        raise BusinessValidationFailure()

    def has_sig(self, payment):
            # Checks if the payment has the signature necessary
            return 'recipient_signature' in payment.data

    # Implement the business logic interface

    def check_account_existence(self, payment):
        self.assert_payment_for_vasp(payment)
        accounts = {acc['account'] for acc in self.accounts_db}
        if self.is_sender(payment):
            if payment.data['sender'].data['subaddress'] in accounts:
                return
        else:
            if payment.data['receiver'].data['subaddress'] in accounts:
                return
        raise BusinessForceAbort('Subaccount does not exist.')

    def is_sender(self, payment):
        self.assert_payment_for_vasp(payment)
        return payment.data['sender'].data['address'] == self.my_addr.own_address.addr
    
    def validate_recipient_signature(self, payment):
        if 'recipient_signature' in payment.data:
            if payment.data['recipient_signature'] == 'VALID':
                return
        raise BusinessValidationFailure()

    def get_recipient_signature(self, payment):
        return 'VALID'

    def next_kyc_to_provide(self, payment):
        my_role = ['receiver', 'sender'][self.is_sender(payment)]
        other_role = ['sender', 'receiver'][self.is_sender(payment)]

        subaddress = payment.data[my_role].data['subaddress']
        account = self.get_account(subaddress)

        if account['business']:
            return { Status.needs_kyc_data }

        to_provide = set()
        if payment.data[other_role].data['status'] == Status.needs_stable_id:
                to_provide.add(Status.needs_stable_id) 
        
        if payment.data[other_role].data['status'] == Status.needs_kyc_data:
                to_provide.add(Status.needs_stable_id) 
                to_provide.add(Status.needs_kyc_data) 
        
        if payment.data[other_role].data['status'] == Status.needs_recipient_signature:
                to_provide.add(Status.needs_recipient_signature) 
                payment.notes['added_sig'] = True
        
        return to_provide
        

    def next_kyc_level_to_request(self, payment):
        my_role = ['receiver', 'sender'][self.is_sender(payment)]
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        subaddress = payment.data[my_role].data['subaddress']
        account = self.get_account(subaddress)

        if account['business']:
            # Put the money aside for this payment ... 
            return Status.none
        
        if 'kyc_data' not in payment.data[other_role].data:
            return Status.needs_kyc_data
        else:
            if my_role == 'sender':
                return Status.needs_recipient_signature
            else:
                return Status.none

    def validate_kyc_signature(self, payment):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        if not payment.data[other_role].data['kyc_signature'] == 'KYC_SIG':
            raise BusinessValidationFailure()

    def get_extended_kyc(self, payment):
        ''' Gets the extended KYC information for this payment.

            Can raise:
                   BusinessAsyncInterupt
                   BusinessNotAuthorized.
        '''
        my_role = ['receiver', 'sender'][self.is_sender(payment)]
        subaddress = payment.data[my_role]['subaddress']
        account = self.get_account(subaddress)
        return (account["kyc_data"], 'KYC_SIG', 'KYC_CERT')


    def get_stable_id(self, payment):
        my_role = ['receiver', 'sender'][self.is_sender(payment)]
        subaddress = payment.data[my_role]['subaddress']
        account = self.get_account(subaddress)
        return account["stable_id"]
    
        
    def ready_for_settlement(self, payment):
        my_role = ['receiver', 'sender'][self.is_sender(payment)]
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        subaddress = payment.data[my_role].data['subaddress']
        account = self.get_account(subaddress)

        if my_role == 'sender': 
            if account["balance"] >= payment.data['action'].data['amount']:
                pass
            else:
                print(account['balance'], payment.data['action'].data['amount'])
                raise BusinessForceAbort('Insufficient Balance')

        # This VASP subaccount is a business
        if account['business']:
            # Put the money aside for this payment ... 
            return self.has_sig(payment)
        
        # The other VASP subaccount is a business
        if 'kyc_data' in payment.data[other_role].data and \
            payment.data[other_role].data['kyc_data'].parse()['type'] == 'business':
            # Put the money aside for this payment ... 
            return self.has_sig(payment)
        
        # Simple VASP, always requires kyc data for individuals
        if 'kyc_data' in payment.data[other_role].data and 'kyc_data' in payment.data[my_role].data:
            # Put the money aside for this payment ... 
            return self.has_sig(payment)
        
        return False

    def want_single_payment_settlement(self, payment):
        return True
    
    def has_settled(self, payment):
        raise BusinessAsyncInterupt(1234)


class sample_vasp:

    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.bc      = sample_business(self.my_addr)
        CommandRequestObject.register_command_type(PaymentCommand)

        self.my_vasp_info = FakeVASPInfo(my_addr, my_addr)
        self.vasp         = OffChainVASP(self.my_vasp_info, self.bc)
