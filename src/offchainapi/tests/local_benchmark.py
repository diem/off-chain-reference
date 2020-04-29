# Sample benchmark to profile performance and observe bottlenecks.
#
# Run as:
# $ python -m cProfile -s tottime src/scripts/run_perf.py > report.txt
#
from ..business import VASPInfo, BusinessContext
from ..libra_address import LibraAddress
from ..payment_logic import PaymentCommand
from ..status_logic import Status
from ..payment import PaymentAction, PaymentActor, PaymentObject, KYCData
from ..core import Vasp

import logging
from mock import AsyncMock
from threading import Thread
import time
import asyncio

# A stand alone performance test.

PeerA_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
PeerB_addr = LibraAddress.encode_to_Libra_address(b'B'*16)
peer_address = {
    PeerA_addr.as_str(): 'http://localhost:8091',
    PeerB_addr.as_str(): 'http://localhost:8092',
}


class SimpleVASPInfo(VASPInfo):

    def __init__(self):
        return

    def get_peer_base_url(self, other_addr):
        assert other_addr.as_str() in peer_address
        return peer_address[other_addr.as_str()]

    def is_authorised_VASP(self, certificate, other_addr):
        return True


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
        if 'recipient_signature' in payment.data:
            recepient = payment.receiver.address
            ref_id = payment.reference_id
            expected_signature = f'{recepient}.{ref_id}.SIGNED'
            return payment.recipient_signature == expected_signature
        else:
            return True

    async def get_recipient_signature(self, payment):
        myself = self.my_addr.as_str()
        ref_id = payment.reference_id
        return f'{myself}.{ref_id}.SIGNED'

# ----- KYC/Compliance checks -----

    async def next_kyc_to_provide(self, payment):
        role = ['receiver', 'sender'][self.is_sender(payment)]
        own_actor = payment.data[role]
        kyc_data = set()

        if 'kyc_data' not in own_actor.data:
            kyc_data.add(Status.needs_kyc_data)

        if role == 'receiver':
            if 'recipient_signature' not in payment.data:
                kyc_data.add(Status.needs_recipient_signature)

        return kyc_data

    async def next_kyc_level_to_request(self, payment):
        other_role = ['sender', 'receiver'][self.is_sender(payment)]
        other_actor = payment.data[other_role]

        if 'kyc_data' not in other_actor.data:
            return Status.needs_kyc_data

        if other_role == 'receiver' \
                and 'recipient_signature' not in payment.data:
            return Status.needs_recipient_signature

        return None

    def validate_kyc_signature(self, payment):
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
                KYCData(f"""{{
                    "payment_reference_id": "{myself}.{ref_id}.KYC",
                    "type": "person"
                    }}"""),
                f'{myself}.{ref_id}.KYC_SIGN',
                f'{myself}.{ref_id}.KYC_CERT',
            )

    async def get_stable_id(self, payment):
        raise NotImplementedError()

# ----- Settlement -----

    async def ready_for_settlement(self, payment):
        return (await self.next_kyc_level_to_request(payment)) is None

    async def has_settled(self, payment):
        return True

global_dir = {}


async def update_dir(vasp):
    global_dir[vasp.vasp.get_vasp_address().as_str()] = vasp


def start_thread_main(vasp, loop):
    # Initialize the VASP services.
    vasp.start_services(loop)

    # Run this once the loop is running
    loop.create_task(update_dir(vasp))

    try:
        # Start the loop
        loop.run_forever()
    finally:
        # Do clean up
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

    logging.debug('VASP loop exit...')


def make_new_VASP(Peer_addr, port):
    VASPx = Vasp(
        Peer_addr,
        host='localhost',
        port=port,
        business_context=BasicBusinessContext(Peer_addr), # AsyncMock(spec=BusinessContext),
        info_context=SimpleVASPInfo(),
        database={})

    loop = asyncio.new_event_loop()
    t = Thread(target=start_thread_main, args=(VASPx, loop))
    t.start()
    print(f'Start Node {port}')
    return (VASPx, loop, t)


async def main_perf():
    VASPa, loopA, tA = make_new_VASP(PeerA_addr, port=8091)
    VASPb, loopB, tB = make_new_VASP(PeerB_addr, port=8092)

    await asyncio.sleep(2.0)
    print('Inject commands')
    await asyncio.sleep(1.0)
    while len(global_dir) != 2:
        await asyncio.sleep(0.1)
    print(global_dir)

    # Get the channel from A -> B
    channelAB = VASPa.vasp.get_channel(PeerB_addr)
    channelBA = VASPb.vasp.get_channel(PeerA_addr)

    # Define a payment command
    commands = []
    payments = []
    for cid in range(1):
        sender = PaymentActor(PeerA_addr.as_str(), 'aaaa', Status.none, [])
        receiver = PaymentActor(PeerB_addr.as_str(), 'bbbb', Status.none, [])
        action = PaymentAction(10, 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
        payment = PaymentObject(
            sender, receiver, f'ref {cid}', 'orig_ref', 'desc', action
        )
        payments += [payment]
        cmd = PaymentCommand(payment)
        commands += [cmd]

    async def send100(nodeA, commands):
        res = await asyncio.gather(
            *[nodeA.new_command_async(VASPb.my_addr, cmd) for cmd in commands],
            return_exceptions=False)
        return res

    # Execute 100 requests
    s = time.perf_counter()
    res = asyncio.run_coroutine_threadsafe(send100(VASPa, commands), loopA)
    res = res.result()
    elapsed = (time.perf_counter() - s)

    # Check that all the payments have been processed and stored.
    for payment in payments:
        ref = payment.reference_id
        payment2 = VASPa.get_payment_by_ref(ref)
        # assert payment2.get_version() == payment.get_version()

    # Print some statistics
    success_number = sum([1 for r in res if r])
    print(f'Commands executed in {elapsed:0.2f} seconds.')
    print(f'Success #: {success_number}/{len(commands)}')

    # In case you want to wait for other responses to settle
    #
    for t in range(10):
        print('waiting', t)
        await asyncio.sleep(1.0)

    # Esure they were register as successes on both sides.
    Asucc = len([x for x in channelAB.executor.command_status_sequence if x])
    Atotal = len(channelAB.executor.command_status_sequence)
    print(f'Peer A successes: {Asucc}/{Atotal}')

    Bsucc = len([x for x in channelBA.executor.command_status_sequence if x])
    Btotal = len(channelBA.executor.command_status_sequence)
    print(f'Peer B successes: {Bsucc}/{Btotal}')

    print(f'Estimate throughput #: {len(commands)/elapsed} Tx/s')

    # Close the loops
    VASPa.close()
    VASPb.close()
