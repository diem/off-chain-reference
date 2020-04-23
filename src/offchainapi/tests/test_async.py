from ..payment_logic import *
from ..payment import *
from ..protocol_messages import *
from ..protocol import *
from ..utils import *
from ..libra_address import *
from ..sample_command import *

from unittest.mock import MagicMock
import pytest

# @pytest.fixture
# def payment_processor_context():
#     bcm = MagicMock(spec=BusinessContext)
#     store = StorableFactory({})
#     proc = PaymentProcessor(bcm, store)
#     return (bcm, proc)

# def test_start_stop(payment_processor_context):
#     bcm, proc = payment_processor_context
#     try:
#         proc.start_processor()
#     finally:
#         proc.stop_processor()
