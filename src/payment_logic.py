from business import BusinessContext, BusinessAsyncInterupt, \
    BusinessNotAuthorized, BusinessValidationFailure, \
    BusinessForceAbort
from executor import ProtocolCommand
from payment import Status, PaymentObject
from status_logic import status_heights_MUST
# Checks on diffs to ensure consistency with logic.


class PaymentCommand(ProtocolCommand):
    def __init__(self, payment):
        ''' Creates a new Payment command based on the diff from the given payment'''
        ProtocolCommand.__init__(self)
        self.depend_on = list(payment.extends)
        self.creates = [payment.get_version()]
        self.command = payment.get_full_record()

    def __eq__(self, other):
        return self.depend_on == other.depend_on \
            and self.creates == other.creates \
            and self.command == other.command

    def get_object(self, version_number, dependencies):
        ''' Constructs the new or updated objects '''
        # First find dependencies & created objects
        if len(self.depend_on) > 1:
            raise PaymentLogicError("A payment can only depend on a single previous payment")
        if len(self.creates) != 1:
            raise PaymentLogicError("A payment always creates a new payment")
        new_version = self.creates[0]

        if len(self.depend_on) == 0:
            payment = PaymentObject.create_from_record(self.command)
            return payment

        elif len(self.depend_on) == 1:
            dep = self.depend_on[0]
            if dep not in dependencies:
                raise PaymentLogicError('Cound not find payment dependency: %s' % dep)
            dep_object = dependencies[dep]
            updated_payment = dep_object.new_version(new_version)
            PaymentObject.from_full_record(self.command, base_instance=updated_payment)
            return updated_payment

        assert False

    def validity_checks(self, context, dependencies, maybe_own=True):
        """ Implements the Validity check interface from executor """
        # Heavy WIP -- clean up the interface with the Executor and errors

        # Ensure that the update to the object is correct
        self.get_object(self.creates[0], dependencies)

        # TODO TODO TODO: Connect with the functions to check new payments
        #                 But those need a business. Hmmm?

        if self.depend_on == []:
            check_new_payment(context, self.command)
        else:
            check_new_update(context, dependencies[self.depend_on[0]], self.command)

        return True

    def on_success(self):
        # TODO: Notify business logic of success and process PaymentCommand
        return

    def on_fail(self):
        # TODO: Notify business logic of failure
        return

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


class PaymentLogicError(Exception):
    pass

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

    # Prevent unilateral aborts after the finality barrier
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

def check_new_payment(business, initial_diff):
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
    new_payment = PaymentObject.create_from_record(initial_diff)

    role = ['sender', 'receiver'][business.is_recipient(new_payment)]
    other_role = ['sender', 'receiver'][role == 'sender']
    other_status = new_payment.data[other_role].data['status']
    if new_payment.data[role].data['status'] != Status.none:
        raise PaymentLogicError('Sender set receiver status or vice-versa.')

    if other_role == 'receiver' and other_status == Status.needs_recipient_signature:
        raise PaymentLogicError(
            'Receiver cannot be in %s.' % Status.needs_recipient_signature
        )

    business.validate_kyc_signature(new_payment)
    business.validate_recipient_signature(new_payment)

    return new_payment


def check_new_update(business, payment, diff):
    ''' Checks a diff updating an existing payment. On success
        returns the new payment object. All check are fast to ensure
        a timely response (cannot support async operations).
    '''

    new_payment = payment.new_version()
    PaymentObject.from_full_record(diff, base_instance=new_payment)

    role = ['sender', 'receiver'][business.is_recipient(new_payment)]
    status = payment.data[role].data['status']
    other_role = ['sender', 'receiver'][role == 'sender']
    old_other_status = payment.data[other_role].data['status']
    other_status = new_payment.data[other_role].data['status']

    # Ensure nothing on our side was changed by this update
    if payment.data[role] != new_payment.data[role]:
        raise PaymentLogicError('Cannot change %s information.' % role)

    # Ensure valid transitions
    check_status(other_role, old_other_status, other_status, status)

    business.validate_kyc_signature(new_payment)
    business.validate_recipient_signature(new_payment)

    return new_payment


# The logic to process a payment from either side.
class PaymentProcessor():

    def __init__(self, business):
        self.business = business

        # TODO: Persit callbacks?
        self.callbacks = {}
        self.ready = {}

    def notify_callback(self, callback_ID):
        ''' Notify the processor that the callback with a specific ID has returned, and is ready to provide an answer. '''
        assert callback_ID in self.callbacks
        obj = self.callbacks[callback_ID]
        del self.callbacks[callback_ID]
        # TODO: should we retrive here the latest version of the object?
        self.ready[callback_ID] = obj

    def payment_process_ready(self):
        ''' Processes any objects for which the callbacks have returned '''
        updated_objects = []
        for (callback_ID, obj) in list(self.ready.items()):
            new_obj = self.payment_process(obj)
            del self.ready[callback_ID]
            if new_obj.has_changed():
                updated_objects += [ new_obj ]
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

        status = payment.data[role].data['status']
        current_status = status
        other_status = payment.data[other_role].data['status']

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
                    stable_id = business.provide_stable_id(new_payment)
                    new_payment.data[role].add_stable_id(stable_id)

                if Status.needs_kyc_data in kyc_to_provide:
                    extended_kyc = business.get_extended_kyc(new_payment)
                    new_payment.data[role].add_kyc_data(*extended_kyc)

                if role == 'receiver' and other_status == Status.needs_recipient_signature:
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
