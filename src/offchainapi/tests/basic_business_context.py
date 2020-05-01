from ..business import BusinessContext
from ..payment import KYCData
from ..status_logic import Status


class BasicBusinessContext(BusinessContext):

    def __init__(self, my_addr):
        self.my_addr = my_addr

    def open_channel_to(self, other_vasp_info):
        return True

    # ----- Actors -----

    def is_sender(self, payment):
        myself = self.my_addr.as_str()
        return myself == payment.sender.address

    def is_recipient(self, payment):
        return not self.is_sender(payment)

    async def check_account_existence(self, payment):
        return True

# ----- VASP Signature -----

    def validate_recipient_signature(self, payment):
        assert 'recipient_signature' in payment
        recepient = payment.receiver.address
        ref_id = payment.reference_id
        expected_signature = f'{recepient}.{ref_id}.SIGNED'
        return payment.recipient_signature == expected_signature

    async def get_recipient_signature(self, payment):
        myself = self.my_addr.as_str()
        ref_id = payment.reference_id
        return f'{myself}.{ref_id}.SIGNED'

# ----- KYC/Compliance checks -----

    async def next_kyc_to_provide(self, payment):
        role = ['receiver', 'sender'][self.is_sender(payment)]
        own_actor = payment.data[role]
        kyc_data = set()

        if 'kyc_data' not in own_actor:
            kyc_data.add(Status.needs_kyc_data)

        if role == 'receiver':
            if 'recipient_signature' not in payment:
                kyc_data.add(Status.needs_recipient_signature)

        return kyc_data

    async def next_kyc_level_to_request(self, payment):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        other_actor = payment.data[other_role]

        if 'kyc_data' not in other_actor:
            return Status.needs_kyc_data

        if other_role == 'receiver' \
                and 'recipient_signature' not in payment:
            return Status.needs_recipient_signature

        return None

    def validate_kyc_signature(self, payment):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        other_actor = payment.data[other_role]
        assert 'kyc_data' in other_actor
        return True

    async def get_extended_kyc(self, payment):
        ''' Returns the extended KYC information for this payment.
            In the format: (kyc_data, kyc_signature, kyc_certificate), where
            all fields are of type str.

            Can raise:
                   BusinessNotAuthorized.
        '''
        myself = self.my_addr.as_str()
        ref_id = payment.reference_id
        return (
                KYCData(
                    f'{{\n'
                    f'  "payment_reference_id": "{myself}.{ref_id}.KYC",\n'
                    f'  "type": "person"\n'
                    f'}}\n'),
                f'{myself}.{ref_id}.KYC_SIGN',
                f'{myself}.{ref_id}.KYC_CERT',
            )

    async def get_stable_id(self, payment):
        raise NotImplementedError()  # pragma: no cover

    # ----- Settlement -----

    async def ready_for_settlement(self, payment):
        return (await self.next_kyc_level_to_request(payment)) is None

    async def has_settled(self, payment):
        return True
