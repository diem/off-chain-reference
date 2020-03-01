from payment_logic import *
from payment import *

from unittest.mock import MagicMock
import pytest


@pytest.fixture
def basic_payment():
    sender = PaymentActor('AAAA', 'aaaa', Status.none, [])
    receiver = PaymentActor('BBBB', 'bbbb', Status.none, [])
    action = PaymentAction(Decimal('10.00'), 'TIK', 'charge', '2020-01-02 18:00:00 UTC')
    payment = PaymentObject(sender, receiver, 'ref', 'orig_ref', 'desc', action)
    return payment


def xxtest_payment_creation(basic_payment):

    bcm = MagicMock(spec=BusinessContext)
    bcm.sure_is_retail_payment.side_effect=[ False, False ]
    bcm.check_actor_existence.side_effect=[True]
    bcm.last_chance_to_abort.side_effect=[True]
    bcm.want_single_payment_settlement.side_effect=[True]

    new_payment = sender_progress_payment(bcm, basic_payment)
    assert new_payment.data['sender'].data['status'] == Status.needs_stable_id

    # We do not add stable_ID unless the other side asks for it.
    assert len(new_payment.update_record) == 0
