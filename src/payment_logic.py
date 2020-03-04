from business import BusinessContext, BusinessAsyncInterupt, \
    BusinessNotAuthorized, BusinessValidationFailure, \
    BusinessForceAbort, ProtocolCommand

from payment import Status, PaymentObject

# Checks on diffs to ensure consistency with logic.


class PaymentCommand(ProtocolCommand):

    def __init__(self, payment):
        self.depend_on = list(payment.extends)
        self.creates = [payment.get_version()]
        self.command = payment.get_full_record()
        self.payment = payment

    def get_object(self, version_number, dependencies):
        if version_number == self.creates[0]:
            return self.payment
        assert False


class PaymentLogicError(Exception):
    pass


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

    if new_payment.data[role].data['status'] != Status.none:
        raise PaymentLogicError('Sender set receiver status or vice-versa.')

    # TODO[issue #2]: Check that other's status is valid

    business.validate_kyc_signature(new_payment)
    business.validate_recipient_signature(new_payment)

    return new_payment


def check_new_update(business, payment, diff):
    ''' Checks a diff updating an existing payment. On success
        returns the new payment object. All check are fast to ensure
        a timely response (cannot support async operations).
    '''

    new_payment = payment.new_version()
    new_payment.flatten()
    new_payment.update(diff)

    # Ensure nothing on our side was changed by this update
    role = ['sender', 'receiver'][business.is_recipient(new_payment)]

    if payment.data[role] != new_payment.data[role]:
        raise PaymentLogicError('Cannot change %s information.' % role)

    # TODO[issue #2]: Check that other's status is valid

    business.validate_kyc_signature(new_payment)
    business.validate_recipient_signature(new_payment)

    return new_payment


# The logic to process a payment from either side.

def payment_process(business, payment):
    ''' Processes a payment that was just updated, and returns a
        new payment with potential updates. This function may be
        called multiple times for the same payment to support
        async business operations and recovery.
    '''

    is_receiver = business.is_recipient()
    role = ['sender', 'receiver'][is_receiver]
    other_role = ['sender', 'receiver'][not is_receiver]

    status = payment.data[role].data['status']
    current_status = status
    other_status = payment.data[other_role].data['status']

    new_payment = payment.new_version()
    new_payment.flatten()

    try:
        if other_status == Status.abort:
            # We set our status as abort
            # TODO: ensure valid abort from the other side elsewhere
            current_status = Status.abort

        if current_status in {Status.none}:
            business.check_account_existence(payment)

        if current_status in {Status.none,
                              Status.needs_stable_id,
                              Status.needs_kyc_data,
                              Status.needs_recipient_signature}:

            # Request KYC -- this may be async in case of need for user input
            current_status = business.next_kyc_level_to_request(payment)

            # Provide KYC -- this may be async in case of need for user input
            kyc_to_provide = business.next_kyc_to_provide(payment)

            if Status.needs_stable_id in kyc_to_provide:
                stable_id = business.provide_stable_id(payment)
                new_payment.data[role].add_stable_id(stable_id)

            if Status.needs_kyc_data in kyc_to_provide:
                extended_kyc = business.get_extended_kyc(payment)
                new_payment.data[role].add_kyc_data(*extended_kyc)

            if role == 'receiver' and other_status == Status.needs_recipient_signature:
                signature = business.get_recipient_signature(payment)
                new_payment.add_recipient_signature(signature)

        # Check if we have all the KYC we need
        ready = business.ready_for_settlement(payment)
        if ready:
            current_status = Status.ready_for_settlement

        if current_status == Status.ready_for_settlement and business.has_settled(payment):
            current_status = Status.settled

    except BusinessAsyncInterupt:
        # The business layer needs to do a long duration check.
        # Cannot make quick progress, and must response with current status.
        new_payment.data[role].change_status(current_status)
        business.register_callback(new_payment, payment_process)

    except BusinessForceAbort:

        # We cannot abort once we said we are ready_for_settlement or beyond
        current_status = Status.abort

    finally:
        # TODO[issue #4]: test is the resulting status is valid
        # TODO[issue #5]: test if there are any changes to the object, to
        #       send to the other side as a command.
        new_payment.data[role].change_status(current_status)

    return new_payment
