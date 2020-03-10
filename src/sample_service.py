from business import BusinessContext, BusinessAsyncInterupt, BusinessForceAbort, BusinessValidationFailure
from protocol import OffChainVASP, LibraAddress
from protocol_messages import CommandRequestObject
from payment_logic import PaymentCommand, PaymentProcessor
from status_logic import Status
from utils import JSON_NET

from test_protocol import FakeAddress

import json
import decimal

business_config = """[
    {
        "account": "1",
        "stable_id": "A",
        "balance": 10.0,
        "business": false,
        "kyc_data" : "{ 'name' : 'Alice' }",
        "pending_transactions" : {}
    },
    {
        "account": "2",
        "stable_id": "B",
        "balance": 100.0,
        "business": true,
        "kyc_data" : "{ 'name' : 'Bob' }",
        "pending_transactions" : {}
    }
]"""

class sample_business(BusinessContext):
    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.accounts_db = json.loads(business_config, parse_float=decimal.Decimal)
    
    # Helper functions for the business

    def get_address(self):
        return self.my_addr.encoded_address

    def get_account(self, subaddress):
        for acc in self.accounts_db:
            if acc['account'] ==  subaddress:
                return acc
        raise BusinessValidationFailure('Account %s does not exist' % subaddress)

    def assert_payment_for_vasp(self, payment):
        sender = payment.data['sender']
        receiver = payment.data['receiver']

        if sender.data['address'] == self.get_address() or \
            receiver.data['address'] == self.get_address():
            return
        raise BusinessValidationFailure()

    def has_sig(self, payment):
            # Checks if the payment has the signature necessary
            return 'recipient_signature' in payment.data

    # Implement the business logic interface

    def open_channel_to(self, other_vasp_info):
        return

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
        return payment.data['sender'].data['address'] == self.get_address()
    
    def validate_recipient_signature(self, payment):
        if 'recipient_signature' in payment.data:
            if payment.data['recipient_signature'] == 'VALID':
                return
            raise BusinessValidationFailure('Invalid signature: %s' % payment.data.get('recipient_signature', 'Not present'))

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
                if my_role == 'receiver':
                    to_provide.add(Status.needs_recipient_signature) 
        
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
        
        if 'recipient_signature' not in payment.data and my_role == 'sender':
                return Status.needs_recipient_signature
            
        return payment.data[my_role].data['status']

    def validate_kyc_signature(self, payment):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        if 'kyc_signature' in payment.data[other_role].data:
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
                
                # Reserve the amount for this payment
                reference = payment.data['reference_id']
                if reference not in account['pending_transactions']:
                    account['pending_transactions'][reference] = {
                        "amount": payment.data['action'].data['amount']
                    }
                    account["balance"] -= payment.data['action'].data['amount']

            else:
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
        if payment.data['sender'].data['status'] == Status.settled:
            # In this VASP we consider we are ready to settle when the sender
            # says so (in reality we would check on-chain as well.)
            my_role = ['receiver', 'sender'][self.is_sender(payment)]
            subaddress = payment.data[my_role].data['subaddress']
            account = self.get_account(subaddress)
            reference = payment.data['reference_id']

            if reference not in account['pending_transactions']:
                account['pending_transactions'][reference] = { 'settled':False }

            if not account['pending_transactions'][reference]['settled']:
                account["balance"] += payment.data['action'].data['amount']
                account['pending_transactions'][reference]['settled'] = True

            return True
        else:
            raise BusinessAsyncInterupt(1234)


class sample_vasp:

    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.bc      = sample_business(self.my_addr)

        CommandRequestObject.register_command_type(PaymentCommand)
        self.pp           = PaymentProcessor(self.bc)
        self.vasp         = OffChainVASP(self.my_addr, self.pp)
        
    
    def get_channel(self, other_vasp):
        channel = self.vasp.get_channel(other_vasp)
        channel.executor.set_outcome_handler(self.process_new_command)
        return channel

    def process_new_command(self, payment_command, success):
        if success:
            new_obj = self.pp.payment_process(payment_command.payment)
            if new_obj.has_changed():
                new_cmd = PaymentCommand(new_obj)
                
                potential_addr = {new_obj.data['sender'].data['address'],
                                     new_obj.data['receiver'].data['address']}
                
                assert self.my_addr.encoded_address in potential_addr
                assert len(potential_addr) == 2
                potential_addr.remove(self.my_addr.encoded_address)
                other_vasp = LibraAddress(potential_addr.pop())

                assert other_vasp.encoded_address != self.my_addr.encoded_address
                assert len(new_cmd.depend_on) > 0
                self.insert_local_command(other_vasp, new_cmd)
        else:
            # TODO: log the command failure.
            pass
    
    def process_request(self, other_vasp, request_json):
        # Get the channel 
        channel = self.get_channel(other_vasp)
        channel.parse_handle_request(request_json)
        return channel.net_queue.pop()
    
    def insert_local_command(self, other_vasp, command):
        channel = self.get_channel(other_vasp)
        
        if command.depend_on != []:
            assert len(channel.executor.object_store) > 0
        channel.sequence_command_local(command)
        return channel.net_queue.pop()

    def process_response(self, other_vasp, request_json):
        channel = self.get_channel(other_vasp)
        channel.parse_handle_response(request_json)
