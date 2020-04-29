from .business import BusinessForceAbort
from .executor import CommandProcessor
from .payment import Status, PaymentObject
from .status_logic import status_heights_MUST
from .payment_command import PaymentCommand, PaymentLogicError
from .asyncnet import NetworkException

import asyncio
import logging


def check_status(role, old_status, new_status, other_status):
    ''' Check that the new status is valid.
        Otherwise raise PaymentLogicError
    '''
    if role == 'receiver' and new_status == Status.needs_recipient_signature:
        raise PaymentLogicError(
            f'Receiver cannot be in {Status.needs_recipient_signature}.'
        )

    if status_heights_MUST[new_status] < status_heights_MUST[old_status]:
        raise PaymentLogicError(
            f'Invalid transition: {role}: {old_status} -> {new_status}'
        )

    # Prevent unilateral aborts after the finality barrier.
    finality_barrier = status_heights_MUST[Status.ready_for_settlement]
    cond = status_heights_MUST[old_status] >= finality_barrier
    cond &= new_status == Status.abort
    cond &= other_status != Status.abort
    cond &= old_status != Status.abort
    if cond:
        raise PaymentLogicError(
            (f'{role} cannot unilaterally abort after'
             f'reaching {Status.ready_for_settlement}.')
        )


class PaymentProcessor(CommandProcessor):
    ''' The logic to process a payment from either side. '''

    def __init__(self, business, storage_factory, loop=None):
        self.business = business

        # Asyncio support
        self.loop = None
        self.net = None
        self.logger = logging.getLogger(name='Processor')

        # The processor state -- only access through event loop to prevent
        # mutlithreading bugs.
        self.storage_factory = storage_factory
        with self.storage_factory.atomic_writes():
            root = storage_factory.make_value('processor', None)
            self.reference_id_index = storage_factory.make_dict(
                'reference_id_index', PaymentObject, root)

        # TODO: how much of this do we want to persist?
        self.command_id = 0
        self.pending_commands = {}
        self.futs = []

    def set_network(self, net):
        ''' Assigns a concrete network for this command processor to use. '''
        assert self.net is None
        self.net = net

    # ------ Machinery for supporting async Business context ------

    async def process_command_async(self, vasp, channel, executor, command,
                                    seq, status_success, error=None):

        self.logger.debug(f'Process cmd {seq}')
        self.command_id += 1
        self.pending_commands[self.command_id] = (vasp, channel, executor,
                                                  command, status_success,
                                                  error)
        try:
            if status_success:
                # Only respond to commands by other side.
                if command.origin != channel.myself:
                    dependencies = executor.object_store
                    new_version = command.get_new_version()
                    payment = command.get_object(new_version, dependencies)
                    new_payment = await self.payment_process_async(payment)

                    if new_payment is not None and new_payment.has_changed():
                        new_cmd = PaymentCommand(new_payment)

                        if self.net is not None:
                            other_addr = channel.get_other_address()
                            request = self.net.sequence_command(
                                other_addr, new_cmd
                            )
                            await self.net.send_request(other_addr, request)
            else:
                self.logger.error(f'Command #{seq} Failure: {error}')

        # Prevent the next catch-all handler from catching canceled exceptions.
        except asyncio.CancelledError as e:
            raise e

        except NetworkException as e:
            self.logger.debug(f'Network error: seq #{seq}: {str(e)}')

        except Exception as e:
            self.logger.error(
                f'Payment processing error: seq #{seq}: {str(e)}')
            self.logger.exception(e)

    # -------- Implements CommandProcessor interface ---------

    def business_context(self):
        return self.business

    def check_command(self, vasp, channel, executor, command):
        ''' Called when receiving a new payment command to validate it.

        All checks here are blocking subsequent comments, and therefore they
        must be quick to ensure performance. As a result we only do local
        syntactic checks hat require no lookup into the VASP potentially
        remote stores or accounts.
        '''

        dependencies = executor.object_store

        new_version = command.get_new_version()
        new_payment = command.get_object(new_version, dependencies)

        # Ensure that the two parties involved are in the VASP channel
        parties = set([
            new_payment.sender.address,
            new_payment.receiver.address
        ])

        needed_parties = set([
            channel.get_my_address().as_str(),
            channel.get_other_address().as_str()
        ])

        if parties != needed_parties:
            raise PaymentLogicError(f'Wrong Parties: expected {needed_parties} \
                but got {str(parties)}')

        other_addr = channel.get_other_address().as_str()

        # Ensure the originator is one of the VASPs in the channel
        origin = command.get_origin().as_str()
        if origin not in parties:
            raise PaymentLogicError('Command originates from wrong party')

        # Only check the commands we get from others.
        if origin == other_addr:
            if command.dependencies == []:

                # Check that the other VASP is the sender?
                # Or allow for fund pull flows here?
                #
                # if new_payment.sender.address != other_addr:
                #    raise PaymentLogicError('Initiator must be \
                #        the sender of funds.')

                self.check_new_payment(new_payment)
            else:
                old_version = command.get_previous_version()
                old_payment = dependencies[old_version]
                self.check_new_update(old_payment, new_payment)

    def process_command(
            self, vasp, channel, executor, command,
            seq, status_success, error=None):
        """ Processes a command to generate more subsequent commands. This schedules a
            talk that will be executed later. """

        # Update the payment object index to support retieval by payment index
        if status_success:
            dependencies_objects = executor.object_store
            new_version = command.get_new_version()
            payment = command.get_object(new_version, dependencies_objects)

            # Update the Index of Reference ID -> Payment
            ref_id = payment.reference_id

            with self.storage_factory.atomic_writes():
                if ref_id in self.reference_id_index:
                    # We get the dependencies of the old payment
                    old_version = self.reference_id_index[ref_id].get_version()

                    # We check that the previous version is present.
                    # If so we update it with the new one.
                    dependencies_versions = command.get_dependencies()
                    if old_version in dependencies_versions:
                        self.reference_id_index[ref_id] = payment
                else:
                    self.reference_id_index[ref_id] = payment

        # Spin further command processing in its own task
        self.logger.debug(f'Schedule cmd {seq}')
        fut = self.loop.create_task(self.process_command_async(
            vasp, channel, executor, command, seq, status_success, error))

        # Log the futures here to execute them inidividually
        # when testing.
        if __debug__:
            self.futs += [fut]

        return fut

    def get_latest_payment_by_ref_id(self, ref_id):
        ''' Returns the latest payment version with
            the reference ID provided.'''
        if ref_id in self.reference_id_index:
            return self.reference_id_index[ref_id]
        else:
            raise KeyError(ref_id)

    # ----------- END of CommandProcessor interface ---------

    def check_signatures(self, payment):
        ''' Utility function that checks all signatures present for validity'''
        business = self.business
        role = ['sender', 'receiver'][business.is_recipient(payment)]
        other_role = ['sender', 'receiver'][role == 'sender']

        if 'kyc_signature' in payment.data[other_role].data:
            business.validate_kyc_signature(payment)

        if role == 'sender' and 'recipient_signature' in payment.data:
            business.validate_recipient_signature(payment)

    def check_new_payment(self, new_payment):
        ''' Checks a diff for a new payment from the other VASP, and returns
            a valid payemnt. If a validation error occurs, then an exception
            is thrown.

            NOTE: the VASP may be the RECEIVER of the new payment, for example
            for person to person payment initiated by the sender. The VASP
            may also be the SENDER for the payment, such as in cases where a
            merchant is charging an account, a refund, or a standing order.`

            The only real check is that that status for the VASP that has
            not created the payment must be none, to allow for checks and
            potential aborts. However, KYC information on both sides may
            be included by the other party, and should be checked.
            '''
        business = self.business
        # new_payment = PaymentObject.create_from_record(initial_diff)

        role = ['sender', 'receiver'][business.is_recipient(new_payment)]
        other_role = ['sender', 'receiver'][role == 'sender']
        other_status = new_payment.data[other_role].status
        if new_payment.data[role].status != Status.none:
            raise PaymentLogicError(
                'Sender set receiver status or vice-versa.')

        if other_role == 'receiver' \
                and other_status == Status.needs_recipient_signature:
            raise PaymentLogicError(
                'Receiver cannot be in %s.' % Status.needs_recipient_signature
            )

        # TODO: Check status here according to status_logic

        self.check_signatures(new_payment)

    def check_new_update(self, payment, new_payment):
        ''' Checks a diff updating an existing payment. On success
            returns the new payment object. All check are fast to ensure
            a timely response (cannot support async operations).
        '''
        business = self.business

        role = ['sender', 'receiver'][business.is_recipient(new_payment)]
        status = payment.data[role].status
        other_role = ['sender', 'receiver'][role == 'sender']
        old_other_status = payment.data[other_role].status
        other_status = new_payment.data[other_role].status

        # Ensure nothing on our side was changed by this update.
        if payment.data[role] != new_payment.data[role]:
            raise PaymentLogicError(f'Cannot change {role} information.')

        # Ensure valid transitions.
        check_status(other_role, old_other_status, other_status, status)

        self.check_signatures(new_payment)

    def payment_process(self, payment):
        ''' A syncronous version of payment processing -- largely
            used for pytests '''
        loop = self.loop
        if self.loop is None:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self.payment_process_async(payment))

    async def payment_process_async(self, payment):
        ''' Processes a payment that was just updated, and returns a
            new payment with potential updates. This function may be
            called multiple times for the same payment to support
            async business operations and recovery.

            If there is no update to the payment simply return None.
        '''
        business = self.business

        is_receiver = business.is_recipient(payment)
        role = ['sender', 'receiver'][is_receiver]
        other_role = ['sender', 'receiver'][not is_receiver]

        status = payment.data[role].status
        current_status = status
        other_status = payment.data[other_role].status

        new_payment = payment.new_version()

        try:

            # We set our status as abort.
            if other_status == Status.abort:
                current_status = Status.abort

            if current_status == Status.none:
                await business.check_account_existence(new_payment)

            if current_status in {Status.none,
                                  Status.needs_stable_id,
                                  Status.needs_kyc_data,
                                  Status.needs_recipient_signature}:

                # Request KYC -- this may be async in case
                # of need for user input
                current_status = await business.next_kyc_level_to_request(
                    new_payment)

                # Provide KYC -- this may be async in case
                # of need for user input
                kyc_to_provide = await business.next_kyc_to_provide(
                    new_payment)

                if Status.needs_stable_id in kyc_to_provide:
                    stable_id = await business.get_stable_id(new_payment)
                    new_payment.data[role].add_stable_id(stable_id)

                if Status.needs_kyc_data in kyc_to_provide:
                    extended_kyc = await business.get_extended_kyc(new_payment)
                    new_payment.data[role].add_kyc_data(*extended_kyc)

                if Status.needs_recipient_signature in kyc_to_provide:
                    signature = await business.get_recipient_signature(
                        new_payment)
                    new_payment.add_recipient_signature(signature)

            # Check if we have all the KYC we need
            if current_status not in {
                    Status.ready_for_settlement,
                    Status.settled}:
                ready = await business.ready_for_settlement(new_payment)
                if ready:
                    current_status = Status.ready_for_settlement

            if current_status == Status.ready_for_settlement \
                    and await business.has_settled(new_payment):
                current_status = Status.settled

        except BusinessForceAbort:

            # We cannot abort once we said we are ready_for_settlement
            # or beyond. However we will catch a wrong change in the
            # check when we change status.
            current_status = Status.abort

        check_status(role, status, current_status, other_status)
        new_payment.data[role].change_status(current_status)

        return new_payment
