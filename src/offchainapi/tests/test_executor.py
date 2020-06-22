# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

# from ..executor import ProtocolExecutor, ExecutorException
# from ..command_processor import CommandProcessor
# from ..payment_logic import PaymentCommand, Status
# from ..business import BusinessContext

# from unittest.mock import MagicMock
# import pytest


# def test_handlers(payment, executor):
#     _, channel, _ = executor.get_context()
#     store = channel.storage
#     bcm = MagicMock(spec=BusinessContext)

#     object_store = channel.object_locks # executor.object_liveness

#     bcm = MagicMock(spec=BusinessContext)

#     class Stats(CommandProcessor):
#         def __init__(self, bc):
#             self.success_no = 0
#             self.failure_no = 0
#             self.bc = bc

#         def business_context(self):
#             return self.bc

#         def process_command(
#                 self, other_addr, command, seq,
#                 status_success, error=None):
#             if status_success:
#                 self.success_no += 1
#             else:
#                 self.failure_no += 1

#         def check_command(self, my_address, other_address, command):
#             return True

#     stat = Stats(bcm)
#     pe = ProtocolExecutor(channel, stat)

#     cmd1 = PaymentCommand(payment)
#     cmd1.set_origin(channel.get_my_address())

#     pay2 = payment.new_version()
#     pay2.sender.change_status(Status.needs_kyc_data)
#     cmd2 = PaymentCommand(pay2)
#     cmd2.set_origin(channel.get_my_address())

#     pay3 = payment.new_version()
#     pay3.sender.change_status(Status.needs_kyc_data)
#     cmd3 = PaymentCommand(pay3)
#     cmd3.set_origin(channel.get_my_address())

#     assert cmd1.dependencies == []
#     assert cmd2.dependencies == list(cmd1.creates_versions)
#     assert cmd3.dependencies == list(cmd1.creates_versions)

#     with store as tx_no:
#         pe.sequence_next_command(cmd1)
#         v1 = cmd1.creates_versions[0]
#         assert v1 not in object_store

#         pe.set_success(cmd1)
#         assert v1 in object_store

#     assert v1 in object_store
#     assert len(object_store) == 1

#     with store as tx_no:
#         assert v1 in object_store
#         pe.sequence_next_command(cmd2)
#         object_store._check_invariant()
#         v2 = cmd2.creates_versions[0]
#         assert v2 not in object_store
#         object_store._check_invariant()

#         pe.set_success(cmd2)
#         assert v2 in object_store
#         object_store._check_invariant()

#     object_store._check_invariant()

#     assert v1 != v2
#     assert v1 in object_store
#     assert v2 in object_store
#     assert len(object_store) == 2

#     #print('Store keys:', list(object_store.keys()))
#     #print('deps', cmd3.dependencies)

#     with pytest.raises(ExecutorException):
#         with store as _:
#             pe.sequence_next_command(cmd3)
#             # pe.set_fail(2)

#     assert stat.success_no == 2
#     assert stat.failure_no == 0
