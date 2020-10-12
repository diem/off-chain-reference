# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..sample.sample_command import SampleCommand
from ..payment_command import PaymentCommand, PaymentLogicError
from ..protocol_messages import CommandRequestObject, make_success_response
from ..utils import JSONFlag, JSONSerializable

import json
import pytest

def test_payment_command_conform(payment):
    cmd = PaymentCommand(payment.new_version())
    data = cmd.get_json_data_dict(JSONFlag.NET)
    cmd2 = PaymentCommand.from_json_data_dict(data, JSONFlag.NET)
    assert cmd == cmd2

    print()
    print('-'*40)
    print('PaymentCommand Example:')
    print(json.dumps(data, indent=4))
    print('-'*40)

def test_request_payment_command_conform(payment):
    cmd = PaymentCommand(payment.new_version())
    req = CommandRequestObject(cmd)
    data = req.get_json_data_dict(JSONFlag.NET)

    print()
    print('-'*40)
    print('CommandRequestObject Example:')
    print(json.dumps(data, indent=4))
    print('-'*40)

    resp = make_success_response(req)
    data = resp.get_json_data_dict(JSONFlag.NET)

    print()
    print('-'*40)
    print('CommandResponseObject Example:')
    print(json.dumps(data, indent=4))
    print('-'*40)
