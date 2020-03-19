from business import BusinessContext, BusinessAsyncInterupt, \
    BusinessNotAuthorized, BusinessValidationFailure, \
    BusinessForceAbort
from executor import ProtocolCommand, CommandProcessor
from payment import Status, PaymentObject
from status_logic import status_heights_MUST
from libra_address import LibraAddress

from storage import StorableFactory
from utils import JSONSerializable

@JSONSerializable.register
class PaymentCommand(ProtocolCommand):
    def __init__(self, payment):
        ''' Creates a new Payment command based on the diff from the given payment'''
        ProtocolCommand.__init__(self)
        self.dependencies = list(payment.extends)
        self.creates_versions = [ payment.get_version() ]
        self.command = payment.get_full_diff_record()

    def __eq__(self, other):
        return ProtocolCommand.__eq__(self, other) \
            and self.dependencies == other.dependencies \
            and self.creates_versions == other.creates_versions \
            and self.command == other.command

    def get_object(self, version_number, dependencies):
        ''' Constructs the new or updated objects '''
        # First find dependencies & created objects
        new_version = self.get_new_version()
        if new_version != version_number:
            raise PaymentLogicError("Unknown object %s (only know %s)" % (version_number, new_version))

        if len(self.dependencies) == 0:
            payment = PaymentObject.create_from_record(self.command)
            payment.set_version(new_version)
            return payment

        elif len(self.dependencies) == 1:
            dep = self.dependencies[0]
            if dep not in dependencies:
                raise PaymentLogicError('Cound not find payment dependency: %s' % dep)
            dep_object = dependencies[dep]

            # Need to get a deepcopy new version
            updated_payment = dep_object.new_version(new_version)
            PaymentObject.from_full_record(self.command, base_instance=updated_payment)
            assert updated_payment.version == new_version
            return updated_payment

        assert False

    def get_json_data_dict(self, flag):
        ''' Get a data disctionary compatible with JSON serilization (json.dumps) '''
        data_dict = ProtocolCommand.get_json_data_dict(self, flag)
        data_dict['diff'] = self.command
        return data_dict

    @classmethod
    def from_json_data_dict(cls, data, flag):
        ''' Construct the object from a serlialized JSON data dictionary (from json.loads). '''
        self = super().from_json_data_dict(data, flag)
        # Thus super() is magic, but do not worry we get the right type:
        assert isinstance(self, PaymentCommand)
        self.command = data['diff']
        return self

    # Helper functions for payment commands specifically
    def get_previous_version(self):
        ''' Returns the version of the previous payment, or None if this 
            command creates a new payment '''
        dep_len = len(self.dependencies)
        if dep_len > 1:
            raise PaymentLogicError("A payment can only depend on a single previous payment")
        if dep_len == 0:
            return None
        else:
            return self.dependencies[0]

    def get_new_version(self):
        ''' Returns the version number of the payment created or updated '''
        if len(self.creates_versions) != 1:
            raise PaymentLogicError("A payment always creates a new payment")
        return self.creates_versions[0]

class PaymentLogicError(Exception):
    pass


# Functions to check incoming diffs

def check_status(role, old_status, new_status, other_status):
    ''' Check that the new status is valid.
        Otherwise raise PaymentLogicError
    '''
    if role == 'receiver' and new_status == Status.needs_recipient_signature:
        raise PaymentLogicError(
            'Receiver cannot be in %s.' % Status.needs_recipient_signature
        )

    if status_heights_MUST[new_status] < status_heights_MUST[old_status]:
        raise PaymentLogicError(
            'Invalid transition: %s: %s -> %s' % (role, old_status, new_status)
        )

    # Prevent unilateral aborts after the finality barrier:
    finality_barrier = status_heights_MUST[Status.ready_for_settlement]
    cond = status_heights_MUST[old_status] >= finality_barrier
    cond &= new_status == Status.abort
    cond &= other_status != Status.abort
    cond &= old_status != Status.abort
    if cond:
        raise PaymentLogicError(
            '%s cannot unilaterally abort after reaching %s.' %
            (role, Status.ready_for_settlement)
        )

# The logic to process a payment from either side.
class PaymentProcessor(CommandProcessor):

    def __init__(self, business, storage_db=None):
        self.business = business

        # TODO: Persit callbacks?
        # Either we persit them, or we have to go through all
        # active payment objects in the executor payment store
        # and ask for re-processing.
        self.callbacks = {}
        self.ready = {}

    
    # -------- Implements CommandProcessor interface ---------
    
    def business_context(self):
        return self.business
    
    def check_command(self, vasp, channel, executor, command):
        context = self.business_context()
        dependencies = executor.object_store

        new_version = command.get_new_version()
        new_payment = command.get_object(new_version, dependencies)

        ## Ensure that the two parties involved are in the VASP channel
        parties = set([new_payment.sender.address, 
                            new_payment.receiver.address ])

        if len(parties) != 2:
            raise PaymentLogicError('Wrong number of parties to payment: ' + str(parties))

        my_addr = channel.myself.plain()
        if my_addr not in parties:
            raise PaymentLogicError('Payment parties does not include own VASP (%s): %s' % (my_addr, str(parties)))

        other_addr = channel.other.plain()
        if other_addr not in parties:
            raise PaymentLogicError('Payment parties does not include other party (%s): %s' % (other_addr, str(parties)))

        origin = command.get_origin().plain()
        if origin not in parties:
            raise PaymentLogicError('Command originates from wrong party')

        if origin == other_addr:
            # Only check the commands we get from others.
            if command.dependencies == []:
                self.check_new_payment(new_payment)
            else:
                old_version = command.get_previous_version()
                old_payment = dependencies[old_version]
                self.check_new_update(old_payment, new_payment)

    def process_command(self, vasp, channel, executor, command, status_success, error=None):
        if status_success:
            dependencies = executor.object_store
            new_version = command.get_new_version()
            payment = command.get_object(new_version, dependencies)
            new_payment = self.payment_process(payment)
            if new_payment.has_changed():
                new_cmd = PaymentCommand(new_payment)
                channel.sequence_command_local(new_cmd)
        else:
            # TODO: Log the error, but do nothing
            if command.origin == channel.myself:
                pass # log failure of our own command :(

    
    def process_command_backlog(self, vasp):
        ''' Sends commands that have been resumed after being interrupted to other
            VASPs.'''
        updated_payments = self.payment_process_ready()
        for payment in updated_payments:
            parties = [payment.sender.address, 
                            payment.receiver.address ]

            # Determine the other address
            my_addr = vasp.get_vasp_address().plain()
            assert my_addr in parties
            parties.remove(my_addr)
            other_addr = LibraAddress(parties[0])

            channel = vasp.get_channel(other_addr)
            new_cmd = PaymentCommand(payment)
            channel.sequence_command_local(new_cmd)


    # ----------- END of CommandProcessor interface ---------

    def check_new_payment(self, new_payment):
        ''' Checks a diff for a new payment from the other VASP, and returns
            a valid payemnt. If a validation error occurs, then an exception
            is thrown.

            NOTE: the VASP may be the RECEIVER of the new payment, for example for
                person to person payment initiated by the sender. The VASP may
                also be the SENDER for the payment, such as in cases where a
                merchant is charging an account, a refund, or a standing order.

                The only real check is that that status for the VASP that has
                not created the payment must be none, to allow for checks and
                potential aborts. However, KYC information on both sides may
                be included by the other party, and should be checked.
            '''
        business = self.business
        # new_payment = PaymentObject.create_from_record(initial_diff)

        role = ['sender', 'receiver'][business.is_recipient(new_payment)]
        other_role = ['sender', 'receiver'][role == 'sender']
        other_status = new_payment.data[other_role].data['status']
        if new_payment.data[role].data['status'] != Status.none:
            raise PaymentLogicError('Sender set receiver status or vice-versa.')

        if other_role == 'receiver' and other_status == Status.needs_recipient_signature:
            raise PaymentLogicError(
                'Receiver cannot be in %s.' % Status.needs_recipient_signature
            )
        # TODO: CHeck status here according to status_logic

        business.validate_kyc_signature(new_payment)
        business.validate_recipient_signature(new_payment)

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

        # Ensure nothing on our side was changed by this update
        if payment.data[role] != new_payment.data[role]:
            raise PaymentLogicError('Cannot change %s information.' % role)

        # Ensure valid transitions
        check_status(other_role, old_other_status, other_status, status)

        business.validate_kyc_signature(new_payment)
        business.validate_recipient_signature(new_payment)

    def notify_callback(self, callback_ID):
        ''' Notify the processor that the callback with a specific ID has returned, and is ready to provide an answer. '''
        assert callback_ID in self.callbacks
        obj = self.callbacks[callback_ID]
        del self.callbacks[callback_ID]
        # TODO: should we retrive here the latest version of the object?
        self.ready[callback_ID] = obj
        self.notify()
        
    def payment_process_ready(self):
        ''' Processes any objects for which the callbacks have returned '''
        updated_objects = []
        for (callback_ID, obj) in list(self.ready.items()):
            new_obj = self.payment_process(obj)
            del self.ready[callback_ID]
            if new_obj.has_changed():
                updated_objects += [new_obj]
        return updated_objects

    def payment_process(self, payment):
        ''' Processes a payment that was just updated, and returns a
            new payment with potential updates. This function may be
            called multiple times for the same payment to support
            async business operations and recovery.
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
            if other_status == Status.abort:
                # We set our status as abort
                # TODO: ensure valid abort from the other side elsewhere
                current_status = Status.abort

            if current_status in {Status.none}:
                business.check_account_existence(new_payment)

            if current_status in {Status.none,
                                  Status.needs_stable_id,
                                  Status.needs_kyc_data,
                                  Status.needs_recipient_signature}:

                # Request KYC -- this may be async in case of need for user input
                current_status = business.next_kyc_level_to_request(new_payment)

                # Provide KYC -- this may be async in case of need for user input
                kyc_to_provide = business.next_kyc_to_provide(new_payment)

                if Status.needs_stable_id in kyc_to_provide:
                    stable_id = business.get_stable_id(new_payment)
                    new_payment.data[role].add_stable_id(stable_id)

                if Status.needs_kyc_data in kyc_to_provide:
                    extended_kyc = business.get_extended_kyc(new_payment)
                    new_payment.data[role].add_kyc_data(*extended_kyc)

                if Status.needs_recipient_signature in kyc_to_provide:
                    signature = business.get_recipient_signature(new_payment)
                    new_payment.add_recipient_signature(signature)

            # Check if we have all the KYC we need
            ready = business.ready_for_settlement(new_payment)
            if ready:
                current_status = Status.ready_for_settlement

            if current_status == Status.ready_for_settlement and business.has_settled(new_payment):
                current_status = Status.settled

        except BusinessAsyncInterupt as e:
            # The business layer needs to do a long duration check.
            # Cannot make quick progress, and must response with current status.
            check_status(role, status, current_status, other_status)
            new_payment.data[role].change_status(current_status)

            # TODO: Should we pass the new or old object here?
            if new_payment.has_changed():
                self.callbacks[e.get_callback_ID()] = new_payment
            else:
                self.callbacks[e.get_callback_ID()] = payment

        except BusinessForceAbort:

            # We cannot abort once we said we are ready_for_settlement or beyond
            # However we will catch a wrong change in the check when we change status.
            current_status = Status.abort

        finally:
            check_status(role, status, current_status, other_status)
            new_payment.data[role].change_status(current_status)

        return new_payment
