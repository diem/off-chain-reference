# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..business import BusinessContext, BusinessForceAbort, \
    BusinessValidationFailure, VASPInfo
from ..protocol import OffChainVASP
from ..libra_address import LibraAddress
from ..protocol_messages import CommandRequestObject, OffChainProtocolError, \
    OffChainException
from ..payment_logic import PaymentCommand, PaymentProcessor
from ..status_logic import Status
from ..storage import StorableFactory
from ..crypto import ComplianceKey

import json

business_config = """[
    {
        "account": "xxxxxxxx",
        "balance": 10.0,
        "entity": false,
        "kyc_data" : "{ 'name' : 'Alice' }",
        "pending_transactions" : {}
    },
    {
        "account": "2",
        "balance": 100.0,
        "entity": true,
        "kyc_data" : "{ 'name' : 'Bob' }",
        "pending_transactions" : {}
    }
]"""


class sample_vasp_info(VASPInfo):
    def __init__(self):
        peerA_addr = LibraAddress.from_bytes(b'A'*16).as_str()
        each_peer_base_url = {
            peerA_addr: 'https://peerA.com',
        }
        self.each_peer_base_url = each_peer_base_url
        self.my_key = ComplianceKey.generate()
        self.other_key = ComplianceKey.from_str(self.my_key.export_pub())

    def get_peer_base_url(self, other_addr):
        assert other_addr.as_str() in self.each_peer_base_url
        return self.each_peer_base_url[other_addr.as_str()]

    def get_peer_compliance_verification_key(self, other_addr):
        assert not self.other_key._key.has_private
        return self.other_key

    def get_peer_compliance_signature_key(self, my_addr):
        return self.my_key


class sample_business(BusinessContext):
    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.accounts_db = json.loads(business_config)

    # Helper functions for the business

    def get_address(self):
        return self.my_addr.as_str()

    def get_account(self, subaddress):
        for acc in self.accounts_db:
            if acc['account'] == subaddress:
                return acc
        raise BusinessValidationFailure(f'Account {subaddress} does not exist')

    def assert_payment_for_vasp(self, payment):
        sender = payment.sender
        receiver = payment.receiver

        if sender.get_onchain_address_encoded_str() == self.get_address() or \
            receiver.get_onchain_address_encoded_str() == self.get_address():
            return
        raise BusinessValidationFailure()

    def has_sig(self, payment):
            # Checks if the payment has the signature necessary
            return 'recipient_signature' in payment.data

    # Implement the business logic interface

    def open_channel_to(self, other_vasp_info):
        return

    def close_channel_to(self, other_vasp_info):
        return

    async def check_account_existence(self, payment, ctx=None):
        self.assert_payment_for_vasp(payment)
        accounts = {acc['account'] for acc in self.accounts_db}

        if self.is_sender(payment):
            sub = LibraAddress.from_encoded_str(payment.sender.address).subaddress_bytes.decode('ascii')
            if sub in accounts:
                return
        else:
            sub = LibraAddress.from_encoded_str(payment.receiver.address).subaddress_bytes.decode('ascii')
            if sub in accounts:
                return
        raise BusinessForceAbort('Subaccount does not exist.')

    def is_sender(self, payment, ctx=None):
        self.assert_payment_for_vasp(payment)
        return payment.sender.get_onchain_address_encoded_str() == self.get_address()


    def validate_recipient_signature(self, payment, ctx=None):
        if 'recipient_signature' in payment.data:
            if payment.recipient_signature == 'VALID':
                return
            sig = payment.data.get('recipient_signature', 'Not present')
            raise BusinessValidationFailure(f'Invalid signature: {sig}')

    async def get_recipient_signature(self, payment, ctx=None):
        return 'VALID'

    def get_my_role(self, payment):
        my_role = ['receiver', 'sender'][self.is_sender(payment)]
        return my_role

    def get_other_role(self, payment):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        return other_role

    async def next_kyc_to_provide(self, payment, ctx=None):
        my_role = self.get_my_role(payment)
        other_role = self.get_other_role(payment)

        subaddress = payment.data[my_role].address

        sub = LibraAddress.from_encoded_str(subaddress).subaddress_bytes.decode('ascii')
        account = self.get_account(sub)

        if account['entity']:
            return { Status.needs_kyc_data }

        to_provide = set()

        if payment.data[other_role].status.as_status() == Status.needs_kyc_data:
                to_provide.add(Status.needs_kyc_data)

        if payment.data[other_role].status.as_status() == Status.needs_recipient_signature:
                if my_role == 'receiver':
                    to_provide.add(Status.needs_recipient_signature)

        return to_provide


    async def next_kyc_level_to_request(self, payment, ctx=None):
        my_role = self.get_my_role(payment)
        other_role = self.get_other_role(payment)
        subaddress = payment.data[my_role].address

        sub = LibraAddress.from_encoded_str(subaddress).subaddress_bytes.decode('ascii')
        account = self.get_account(sub)

        if account['entity']:
            # Put the money aside for this payment ...
            return Status.none

        if 'kyc_data' not in payment.data[other_role].data:
            return Status.needs_kyc_data

        if 'recipient_signature' not in payment.data and my_role == 'sender':
            return Status.needs_recipient_signature

        return payment.data[my_role].status.as_status()

    async def get_extended_kyc(self, payment, ctx=None):
        ''' Gets the extended KYC information for this payment.

            Can raise:
                   BusinessNotAuthorized.
        '''
        my_role = self.get_my_role(payment)
        subaddress = payment.data[my_role].address

        sub = LibraAddress.from_encoded_str(subaddress).subaddress_bytes.decode('ascii')
        account = self.get_account(sub)
        return account["kyc_data"]

    async def ready_for_settlement(self, payment, ctx=None):
        my_role = self.get_my_role(payment)
        other_role = self.get_other_role(payment)
        subaddress = payment.data[my_role].address

        sub = LibraAddress.from_encoded_str(subaddress).subaddress_bytes.decode('ascii')
        account = self.get_account(sub)

        if my_role == 'sender':
            reference = payment.reference_id
            if account["balance"] >= payment.action.amount:

                # Reserve the amount for this payment
                if reference not in account['pending_transactions']:
                    account['pending_transactions'][reference] = {
                        "amount": payment.action.amount
                    }
                    account["balance"] -= payment.action.amount

            else:
                if reference not in account['pending_transactions']:
                    raise BusinessForceAbort('Insufficient Balance')

        # This VASP always settles payments on chain, so we always need
        # a signature to settle on chain.
        if not self.has_sig(payment):
            return False

        # This VASP subaccount is a business
        if account['entity']:
            return True

        # The other VASP subaccount is a business
        if 'kyc_data' in payment.data[other_role].data and \
            payment.data[other_role].data['kyc_data'].parse()['type'] == 'entity':
            return True

        # Simple VASP, always requires kyc data for individuals
        if 'kyc_data' in payment.data[other_role].data and 'kyc_data' in payment.data[my_role].data:
            return True

        # We are not ready to settle yet!
        return False


class sample_vasp:

    def __init__(self, my_addr):
        self.my_addr = my_addr
        self.bc = sample_business(self.my_addr)
        self.store        = StorableFactory({})
        self.info_context = sample_vasp_info()

        self.pp = PaymentProcessor(self.bc, self.store)
        self.vasp = OffChainVASP(
            self.my_addr, self.pp, self.store, self.info_context
        )

    def get_channel(self, other_vasp):
        channel = self.vasp.get_channel(other_vasp)
        return channel

    def process_request(self, other_vasp, request_json):
        # Get the channel
        channel = self.get_channel(other_vasp)
        resp = channel.parse_handle_request(request_json)
        return resp

    def insert_local_command(self, other_vasp, command):
        channel = self.get_channel(other_vasp)
        req = channel.sequence_command_local(command)
        return req

    def process_response(self, other_vasp, response_json):
        channel = self.get_channel(other_vasp)
        try:
            channel.parse_handle_response(response_json)
        except OffChainProtocolError:
            pass
        except OffChainException:
            pass
