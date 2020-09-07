# Copyright (c) Facebook, Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ..sample.sample_command import SampleCommand
from ..payment_command import PaymentCommand, PaymentLogicError
from ..protocol_messages import CommandRequestObject, make_success_response
from ..utils import JSONFlag, JSONSerializable

import pytest

def test_payment_command_serialization_net(payment):
    cmd = PaymentCommand(payment)
    data = cmd.get_json_data_dict(JSONFlag.NET)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.NET)
    assert cmd == cmd2


def test_payment_command_serialization_parse(payment):
    cmd = PaymentCommand(payment)
    data = cmd.get_json_data_dict(JSONFlag.NET)
    obj = JSONSerializable.parse(data, JSONFlag.NET)
    assert obj == cmd

    cmd_s = SampleCommand('Hello', deps=['World'])
    data2 = cmd_s.get_json_data_dict(JSONFlag.NET)
    cmd_s2 = JSONSerializable.parse(data2, JSONFlag.NET)
    assert cmd_s == cmd_s2


def test_payment_command_serialization_store(payment):
    cmd = PaymentCommand(payment)
    data = cmd.get_json_data_dict(JSONFlag.STORE)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.STORE)
    assert cmd == cmd2


def test_payment_end_to_end_serialization(payment):
    # Define a full request/reply with a Payment and test serialization
    cmd = PaymentCommand(payment)
    request = CommandRequestObject(cmd)
    request.cid = '10'
    request.response = make_success_response(request)
    data = request.get_json_data_dict(JSONFlag.STORE)
    request2 = CommandRequestObject.from_json_data_dict(data, JSONFlag.STORE)
    assert request == request2


def test_payment_command_missing_dependency_fail(payment):
    new_payment = payment.new_version('v1')
    cmd = PaymentCommand(new_payment)
    with pytest.raises(PaymentLogicError):
        cmd.get_object(new_payment.get_version(), {})

def test_get_payment(payment):

    # Get a new payment -- no need for any dependency
    cmd = PaymentCommand(payment)
    payment_copy = cmd.get_payment({}) # Empty dependency store
    assert payment_copy == payment

    # A command that updates a payment to new version
    new_payment = payment.new_version()
    new_cmd = PaymentCommand(new_payment)

    with pytest.raises(PaymentLogicError):
        # Fail: offchainapi.payment_command.PaymentLogicError:
        #       Cound not find payment dependency:
        _ = new_cmd.get_payment({})

    object_store = {
            payment.get_version(): payment
        }
    new_payment_copy = new_cmd.get_payment(object_store)
    assert new_payment == new_payment_copy
