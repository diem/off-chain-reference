from .business import BusinessForceAbort
from .executor import CommandProcessor
from .payment import Status, PaymentObject
from .status_logic import status_heights_MUST
from .payment_command import PaymentCommand, PaymentLogicError
from .asyncnet import NetworkException
from .shared_object import SharedObject

import asyncio
import logging
import json


class PaymentProcessor(CommandProcessor):
    ''' The logic to process a payment from either side.

    The processor checks commands as they are received from the other
    VASP. When a command from the other VASP is successful it is
    passed on to potentially lead to a further command. It is also
    notified of sequenced commands that failed, and the error that
    lead to that failure.

    Crash-recovery strategy: The processor must only process each
    command once. Foor this purpose the Executor passes commands
    in the order they have been sequenced by the lower-level
    protocol on each channel, and does so only once for each command
    in the sequence for each channel.

    The Processor must store those commands, and ensure they have
    all been suitably processed upon a potential crash and recovery.

    '''

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

            # This is the primary store of shared objects.
            # It maps version numbers -> objects
            self.object_store = storage_factory.make_dict(
                'object_store', SharedObject, root=root)

            # TODO: how much of this do we want to persist?
            self.pending_commands = storage_factory.make_dict(
                'command_log', str, root)

        # Storage for debug futures list
        self.futs = []

    def set_network(self, net):
        ''' Assigns a concrete network for this command processor to use. '''
        assert self.net is None
        self.net = net

    # ------ Machinery for crash tolerance.

    def command_unique_id(self, channel, seq):
        ''' Returns a string that uniquerly identifies this
            command for the local VASP.'''
        other_str = channel.get_other_address().as_str()
        data = json.dumps((other_str, seq))
        return f'{other_str}_{seq}', data

    def persist_command_obligation(self, vasp, channel, executor, command,
                                   seq, status_success, error=None):
        ''' Persists the command to ensure its future execution. '''
        uid, data = self.command_unique_id(channel, seq)
        self.pending_commands[uid] = data

    def obligation_exists(self, channel, seq):
        uid, _ = self.command_unique_id(channel, seq)
        return uid in self.pending_commands

    def release_command_obligation(self, channel, seq):
        ''' Once the command is executed, and a potential response stored,
            this function allows us to remove the obligation to process
            the command. '''
        uid, _ = self.command_unique_id(channel, seq)
        del self.pending_commands[uid]

    def list_command_obligations(self):
        ''' Returns a list of (other_address, command sequence) tuples denoting
            the pending commands that need to be re-executed after a crash or
            shutdown. '''
        pending = []
        for uid in self.pending_commands.keys():
            data = self.pending_commands[uid]
            (other_channel, seq) = json.loads(data)
            pending += [(other_channel, seq)]
        return pending

    # ------ Machinery for supporting async Business context ------

    async def process_command_async(self, vasp, channel, executor, command,
                                    seq, status_success, error=None):
        ''' The asyncronous command processing logic.

        Checks all incomming commands from the other VASP, and determines if
        any new commands need to be issued from this VASP in response.
        '''

        other_str = channel.get_other_address().as_str()
        self.logger.debug(f'Process Command {other_str}.#{seq}')

        try:
            if status_success:
                # Only respond to commands by other side.
                if command.origin != channel.myself:
                    payment = command.get_payment()
                    new_payment = await self.payment_process_async(payment)

                    if new_payment is not None and new_payment.has_changed():
                        new_cmd = PaymentCommand(new_payment)

                        if self.net is not None:
                            other_addr = channel.get_other_address()

                            # This context ensure that either we both
                            # write the next request & free th obligation
                            # Or none of the two.
                            with self.storage_factory.atomic_writes():
                                request = self.net.sequence_command(
                                    other_addr, new_cmd
                                )

                                # Crash-recovery: Once a request is ordered to
                                # be sent out we can consider this command
                                # done.
                                if self.obligation_exists(channel, seq):
                                    self.release_command_obligation(
                                        channel, seq)

                            # Attempt to send it to the other VASP.
                            await self.net.send_request(other_addr, request)
            else:
                self.logger.error(f'Command #{seq} Failure: {error}')

            # If we are here we are done with this obligation
            with self.storage_factory.atomic_writes():
                if self.obligation_exists(channel, seq):
                    self.release_command_obligation(channel, seq)

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

            All checks here are blocking subsequent comments, and therefore
            they must be quick to ensure performance. As a result we only
            do local syntactic checks hat require no lookup into the VASP
            potentially remote stores or accounts.
        '''

        dependencies = self.object_store
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
        ''' Processes a command to generate more subsequent commands.
            This schedules a task that will be executed later asynchronously.
        '''

        # Update the payment object index to support retieval by payment index
        if status_success:

            # Creates new objects
            new_versions = command.new_object_versions()
            for version in new_versions:
                obj = command.get_object(version, self.object_store)
                self.object_store[version] = obj

            payment = command.get_payment()

            # Update the Index of Reference ID -> Payment
            ref_id = payment.reference_id

            # NOTE: This is all called by the executor within a write lock
            # all the way from the protocol code, so no need for an extra:
            # with self.storage_factory.atomic_writes():

            # Write the new payment to the index of payments by
            # reference ID to support they GetPaymentAPI.
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

        # We record an obligation to process this command, even
        # after crash recovery.
        self.persist_command_obligation(
            vasp, channel, executor,
            command, seq, status_success, error)

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

    def check_status(self, role, old_status, new_status, other_status):
        ''' Check that the new status is valid.
            Otherwise raise PaymentLogicError.
        '''
        other_role = ['sender', 'receiver'][role == 'sender']

        # The receiver cannot be in state 'needs_recipient_signature'.
        my_state_is_bad = role == 'receiver'
        my_state_is_bad &= new_status == Status.needs_recipient_signature
        other_state_is_bad = other_role == 'receiver'
        other_state_is_bad &= other_status == Status.needs_recipient_signature
        if my_state_is_bad or other_state_is_bad:
            raise PaymentLogicError(
                f'Receiver cannot be in {Status.needs_recipient_signature}.'
            )

        # Ensure progress is mades.
        if status_heights_MUST[new_status] < status_heights_MUST[old_status]:
            raise PaymentLogicError(
                f'Invalid transition: {role}: {old_status} -> {new_status}'
            )

        # Prevent unilateral aborts after the finality barrier.
        finality_barrier = status_heights_MUST[Status.ready_for_settlement]
        break_finality_barrier = status_heights_MUST[old_status] >= finality_barrier
        break_finality_barrier &= new_status == Status.abort
        break_finality_barrier &= other_status != Status.abort
        break_finality_barrier &= old_status != Status.abort
        if break_finality_barrier:
            raise PaymentLogicError(
                f'{role} cannot unilaterally abort after '
                f'reaching {Status.ready_for_settlement}.'
            )

    def check_signatures(self, payment):
        ''' Utility function that checks all signatures present for validity'''
        business = self.business
        is_sender = business.is_sender(payment)
        other_actor = payment.receiver if is_sender else payment.sender

        if 'kyc_signature' in other_actor:
            business.validate_kyc_signature(payment)

        if is_sender and 'recipient_signature' in payment:
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

        role = ['sender', 'receiver'][business.is_recipient(new_payment)]
        other_role = ['sender', 'receiver'][role == 'sender']
        other_status = new_payment.data[other_role].status
        if new_payment.data[role].status != Status.none:
            raise PaymentLogicError(
                'Sender set receiver status or vice-versa.'
            )

        self.check_status(role, Status.none, Status.none, other_status)
        self.check_signatures(new_payment)

    def check_new_update(self, payment, new_payment):
        ''' Checks a diff updating an existing payment.

            On success returns the new payment object. All check are fast to
            ensure a timely response (cannot support async operations).
        '''
        business = self.business

        role = ['sender', 'receiver'][business.is_recipient(new_payment)]
        other_role = ['sender', 'receiver'][role == 'sender']
        myself_actor = payment.data[role]
        myself_actor_new = new_payment.data[role]
        other_actor = payment.data[other_role]

        # Ensure nothing on our side was changed by this update.
        if myself_actor != myself_actor_new:
            raise PaymentLogicError(f'Cannot change {role} information.')

        # Check the status transition is valid.
        status = myself_actor.status
        old_other_status = other_actor.status
        other_status = other_actor.status

        self.check_status(other_role, old_other_status, other_status, status)
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

                myself_new_actor = new_payment.data[role]
                if Status.needs_stable_id in kyc_to_provide:
                    stable_id = await business.get_stable_id(new_payment)
                    myself_new_actor.add_stable_id(stable_id)

                if Status.needs_kyc_data in kyc_to_provide:
                    extended_kyc = await business.get_extended_kyc(new_payment)
                    myself_new_actor.add_kyc_data(*extended_kyc)

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

        self.check_status(role, status, current_status, other_status)
        new_payment.data[role].change_status(current_status)

        return new_payment
