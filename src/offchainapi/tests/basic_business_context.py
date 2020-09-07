# Copyright (c) Facebook, Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ..business import BusinessContext, BusinessValidationFailure
from ..payment import KYCData
from ..status_logic import Status


class TestBusinessContext(BusinessContext):
    __test__ = False

    def __init__(self, my_addr, reliable=True):
        self.my_addr = my_addr

        # Option to make the contect unreliable to
        # help test error handling.
        self.reliable = reliable
        self.reliable_count = 0

    def cause_error(self):
        self.reliable_count += 1
        fail = (self.reliable_count % 5 == 0)
        if fail:
            e = BusinessValidationFailure(
                'Artifical error caused for '
                'testing error handling')
            raise e



    def open_channel_to(self, other_vasp_info):
        return True

    async def payment_pre_processing(self, other_address, seq, command, payment):
        ctx = {}
        ctx['settle'] = False
        return ctx

    # ----- Actors -----

    def is_sender(self, payment, ctx=None):
        myself = self.my_addr.as_str()
        return myself == payment.sender.get_onchain_address_encoded_str()

    def is_recipient(self, payment, ctx=None):
        return not self.is_sender(payment)

    async def check_account_existence(self, payment, ctx=None):
        return True

# ----- VASP Signature -----

    def validate_recipient_signature(self, payment, ctx=None):
        assert 'recipient_signature' in payment
        recepient = payment.receiver.get_onchain_address_encoded_str()
        ref_id = payment.reference_id
        expected_signature = f'{recepient}.{ref_id}.SIGNED'

        if not self.reliable:
            self.cause_error()

        return payment.recipient_signature == expected_signature

    async def get_recipient_signature(self, payment, ctx=None):
        myself = self.my_addr.as_str()
        ref_id = payment.reference_id
        return f'{myself}.{ref_id}.SIGNED'

# ----- KYC/Compliance checks -----

    async def next_kyc_to_provide(self, payment, ctx=None):
        role = ['receiver', 'sender'][self.is_sender(payment)]
        other_role = ['receiver', 'sender'][not self.is_sender(payment)]
        own_actor = payment.data[role]
        other_actor = own_actor = payment.data[other_role]
        kyc_data = set()

        if 'kyc_data' not in own_actor:
            kyc_data.add(Status.needs_kyc_data)

        if 'additional_kyc_data' not in own_actor \
                and other_actor.status.as_status() == Status.soft_match:
            kyc_data.add(Status.soft_match)

        if role == 'receiver':
            if 'recipient_signature' not in payment:
                kyc_data.add(Status.needs_recipient_signature)

        return kyc_data

    async def next_kyc_level_to_request(self, payment, ctx=None):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        other_actor = payment.data[other_role]

        if 'kyc_data' not in other_actor:
            return Status.needs_kyc_data

        if self.reliable_count % 3 == 0:
            if 'additional_kyc_data' not in other_actor:
                return Status.soft_match

        if other_role == 'receiver' \
                and 'recipient_signature' not in payment:
            return Status.needs_recipient_signature

        ctx['settle'] = True
        return Status.none


    async def get_extended_kyc(self, payment, ctx=None):
        ''' Returns the extended KYC information for this payment.
            In the format: (kyc_data, kyc_signature, kyc_certificate), where
            all fields are of type str.

            Can raise:
                   BusinessNotAuthorized.
        '''
        return KYCData({
                    "payload_type": "KYC_DATA",
                    "payload_version": 1,
                    "type": "individual",
                })

    async def get_additional_kyc(self, payment, ctx=None):
        ''' Returns the extended KYC information for this payment.
            In the format: (kyc_data, kyc_signature, kyc_certificate), where
            all fields are of type str.

            Can raise:
                   BusinessNotAuthorized.
        '''
        return KYCData({
                    "payload_type": "KYC_DATA",
                    "payload_version": 1,
                    "type": "individual",
                    "given_name": "John",
                    "surname": "Smith",
                    "dob": "1973-07-08"
                })

    # ----- Settlement -----

    async def ready_for_settlement(self, payment, ctx=None):
        if not self.reliable:
            self.cause_error()

        return ctx['settle']
