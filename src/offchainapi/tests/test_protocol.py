# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from ..protocol import VASPPairChannel, make_protocol_error, DependencyException
from ..protocol_messages import CommandRequestObject, CommandResponseObject, \
    OffChainProtocolError, OffChainException, OffChainOutOfOrder
from ..sample.sample_command import SampleCommand
from ..command_processor import CommandProcessor
from ..utils import JSONSerializable, JSONFlag
from ..storage import StorableFactory

import types
from copy import deepcopy
import random
from unittest.mock import MagicMock
import pytest
import asyncio
import json

class RandomRun(object):
    def __init__(self, server, client, commands, seed='fixed seed'):
        # MESSAGE QUEUES
        self.to_server_requests = []
        self.to_client_response = []
        self.to_client_requests = []
        self.to_server_response = []

        self.server = server
        self.client = client

        self.commands = commands
        self.number = len(commands)
        random.seed(seed)

        self.DROP = True
        self.VERBOSE = False

        self.rejected = 0

    def run(self):
        to_server_requests = self.to_server_requests
        to_client_response = self.to_client_response
        to_client_requests = self.to_client_requests
        to_server_response = self.to_server_response
        server = self.server
        client = self.client
        commands = self.commands


        while True:

            # Inject a command every round
            if random.random() > 0.99:
                if len(commands) > 0:
                    c = commands.pop(0)
                    try:
                        if random.random() > 0.5:
                            req = client.sequence_command_local(c)
                            to_server_requests += [req]
                        else:
                            req = server.sequence_command_local(c)
                            to_client_requests += [req]
                    except DependencyException:
                        self.rejected += 1

            # Random drop
            while self.DROP and random.random() > 0.3:
                kill_list = random.choice([to_server_requests,
                                           to_client_requests,
                                           to_client_response,
                                           to_server_response])
                del kill_list[-1:]

            Case = [False, False, False, False, False]
            Case[random.randint(0, len(Case) - 1)] = True
            Case[random.randint(0, len(Case) - 1)] = True

            # Make progress by delivering a random queue
            if Case[0] and len(to_server_requests) > 0:
                client_request = to_server_requests.pop(0)
                resp = server.handle_request(client_request)
                to_client_response += [resp]

            if Case[1] and len(to_client_requests) > 0:
                server_request = to_client_requests.pop(0)
                resp = client.handle_request(server_request)
                to_server_response += [resp]

            if Case[2] and len(to_client_response) > 0:
                rep = to_client_response.pop(0)
                # assert req.client_sequence_number is not None
                try:
                    client.handle_response(rep)
                except OffChainProtocolError:
                    pass
                except OffChainException:
                    raise
                except OffChainOutOfOrder:
                    pass

            if Case[3] and len(to_server_response) > 0:
                rep = to_server_response.pop(0)
                try:
                    server.handle_response(rep)
                except OffChainProtocolError:
                    pass
                except OffChainException:
                    raise
                except OffChainOutOfOrder:
                    pass

            # Retransmit
            if Case[4] and random.random() > 0.10:
                cr = client.get_retransmit()
                to_server_requests += cr
                sr = server.get_retransmit()
                to_client_requests += sr

            if self.VERBOSE:
                print([to_server_requests,
                       to_client_requests,
                       to_client_response,
                       to_server_response])

                print([server.would_retransmit(),
                       client.would_retransmit(),
                       server.next_final_sequence(),
                       client.next_final_sequence()])

            if not server.would_retransmit() and not client.would_retransmit() \
                    and server.next_final_sequence() + self.rejected == self.number \
                    and client.next_final_sequence() + self.rejected == self.number:
                break

    def checks(self, NUMBER):
        client = self.client
        server = self.server

        client_seq = [c.command.item() for c in client.get_final_sequence()]
        server_seq = [c.command.item() for c in server.get_final_sequence()]

        assert len(client_seq) == NUMBER - self.rejected
        assert set(client_seq) == set(server_seq)

        client_exec_seq = [c.command.item() for c in client.command_sequence]
        server_exec_seq = [c.command.item() for c in server.command_sequence]
        assert set(client_seq) == set(client_exec_seq)
        assert set(server_seq) == set(server_exec_seq)


def test_create_channel_to_myself(three_addresses, vasp):
    a0, _, _ = three_addresses
    command_processor = MagicMock(spec=CommandProcessor)
    store = MagicMock()
    with pytest.raises(OffChainException):
        channel = VASPPairChannel(a0, a0, vasp, store, command_processor)


def test_client_server_role_definition(three_addresses, vasp):
    a0, a1, a2 = three_addresses
    command_processor = MagicMock(spec=CommandProcessor)
    store = MagicMock()

    channel = VASPPairChannel(a0, a1, vasp, store, command_processor)
    assert channel.is_server()
    assert not channel.is_client()

    channel = VASPPairChannel(a1, a0, vasp, store, command_processor)
    assert not channel.is_server()
    assert channel.is_client()

    # Lower address is server (xor bit = 1)
    channel = VASPPairChannel(a0, a2, vasp, store, command_processor)
    assert not channel.is_server()
    assert channel.is_client()

    channel = VASPPairChannel(a2, a0, vasp, store, command_processor)
    assert channel.is_server()
    assert not channel.is_client()


def test_protocol_server_client_benign(two_channels):
    server, client = two_channels

    # Create a server request for a command
    request = server.sequence_command_local(SampleCommand('Hello'))
    assert isinstance(request, CommandRequestObject)

    print()
    print(request.pretty(JSONFlag.NET))

    # Pass the request to the client
    assert len(client.other_request_index) == 0
    reply = client.handle_request(request)
    assert isinstance(reply, CommandResponseObject)
    assert len(client.other_request_index) == 1
    assert reply.status == 'success'

    print()
    print(reply.pretty(JSONFlag.NET))

    # Pass the reply back to the server
    assert server.next_final_sequence() == 0
    succ = server.handle_response(reply)
    assert succ

    assert server.next_final_sequence() > 0
    assert client.next_final_sequence() > 0
    assert client.get_final_sequence()[0].command.item() == 'Hello'


def test_protocol_server_conflicting_sequence(two_channels):
    server, client = two_channels

    # Create a server request for a command
    request = server.sequence_command_local(SampleCommand('Hello'))

    # Modilfy message to be a conflicting sequence number
    request_conflict = deepcopy(request)
    request_conflict.command = SampleCommand("Conflict")

    # Pass the request to the client
    reply = client.handle_request(request)
    reply_conflict = client.handle_request(request_conflict)

    # We only sequence one command.
    assert len(client.other_request_index) == 1
    assert reply.status == 'success'

    # The response to the second command is a failure
    assert reply_conflict.status == 'failure'
    assert reply_conflict.error.code == 'conflict'

    # Pass the reply back to the server
    assert server.next_final_sequence() == 0
    succ = server.handle_response(reply)
    assert succ

    assert server.next_final_sequence() > 0
    assert client.next_final_sequence() > 0
    assert client.get_final_sequence()[0].command.item() == 'Hello'


def test_protocol_client_server_benign(two_channels):
    server, client = two_channels

    # Create a server request for a command
    request = client.sequence_command_local(SampleCommand('Hello'))
    assert isinstance(request, CommandRequestObject)
    assert len(client.other_request_index) == 0

    # Send to server
    assert len(client.other_request_index) == 0
    reply = server.handle_request(request)
    assert isinstance(reply, CommandResponseObject)
    assert len(server.other_request_index) == 1
    assert server.next_final_sequence() == 1
    assert server.next_final_sequence() > 0

    # Pass response back to client
    assert client.my_request_index[request.cid].response is None
    succ = client.handle_response(reply)
    assert succ

    assert client.next_final_sequence() > 0
    assert client.my_request_index[request.cid].response is not None
    assert client.get_final_sequence()[0].command.item() == 'Hello'
    assert client.next_final_sequence() == 1


def test_protocol_server_client_interleaved_benign(two_channels):
    server, client = two_channels

    client_request = client.sequence_command_local(SampleCommand('Hello'))
    server_request = server.sequence_command_local(SampleCommand('World'))

    # The server waits until all own requests are done
    server_reply = server.handle_request(client_request)
    assert server_reply.status == 'success'

    client_reply = client.handle_request(server_request)
    server.handle_response(client_reply)
    server_reply = server.handle_request(client_request)

    client.handle_response(server_reply)

    assert len(client.my_request_index) == 1
    assert len(server.other_request_index) == 1
    assert len(client.get_final_sequence()) == 2
    assert len(server.get_final_sequence()) == 2
    assert {c.command.item() for c in client.get_final_sequence()} == {
        'World', 'Hello'}
    assert {c.command.item() for c in server.get_final_sequence()} == {
        'World', 'Hello'}


def test_protocol_server_client_interleaved_swapped_request(two_channels):
    server, client = two_channels

    client_request = client.sequence_command_local(SampleCommand('Hello'))
    server_request = server.sequence_command_local(SampleCommand('World'))

    client_reply = client.handle_request(server_request)
    server_reply = server.handle_request(client_request)
    assert server_reply.status == 'success'

    server.handle_response(client_reply)
    server_reply = server.handle_request(client_request)

    client.handle_response(server_reply)

    assert len(client.my_request_index) == 1
    assert len(server.other_request_index) == 1
    assert len(client.get_final_sequence()) == 2
    assert len(server.get_final_sequence()) == 2
    assert {c.command.item() for c in client.get_final_sequence()} == {
        'World', 'Hello'}
    assert {c.command.item() for c in server.get_final_sequence()} == {
        'World', 'Hello'}

def test_protocol_conflict1(two_channels):
    server, client = two_channels

    msg = client.sequence_command_local(SampleCommand('Hello'))
    msg = client.package_request(msg).content

    msg2 = server.parse_handle_request(msg).content

    # Since this is not yet confirmed, reject the command
    with pytest.raises(DependencyException):
        client.sequence_command_local(SampleCommand('World1', deps=['Hello']))

    msg3 = server.sequence_command_local(SampleCommand('World2', deps=['Hello']))
    msg3 = server.package_request(msg3).content

    # Since this is not yet confirmed, reject the command
    msg4 = client.parse_handle_request(msg3).content
    succ = server.parse_handle_response(msg4)
    assert not succ  # Fails

    # Now add the response that creates 'hello'
    succ = client.parse_handle_response(msg2)
    assert succ  # success


def test_protocol_conflict2(two_channels):
    server, client = two_channels

    msg = client.sequence_command_local(SampleCommand('Hello'))
    msg = client.package_request(msg).content

    msg2 = server.parse_handle_request(msg).content
    succ = client.parse_handle_response(msg2)
    assert succ  # success

    # Two concurrent requests
    creq = client.sequence_command_local(SampleCommand('cW', deps=['Hello']))
    creq = client.package_request(creq).content
    sreq = server.sequence_command_local(SampleCommand('sW', deps=['Hello']))
    sreq = server.package_request(sreq).content

    # Server gets client request
    sresp = server.parse_handle_request(creq).content
    # Client is told to wait
    with pytest.raises(OffChainProtocolError):
        _ = client.parse_handle_response(sresp)

    # Client gets server request
    cresp = client.parse_handle_request(sreq).content
    succ = server.parse_handle_response(cresp)
    assert succ  # Success

    assert 'Hello' in server.object_locks
    assert server.object_locks['Hello'] == 'False'

    # Now try again the client request
    sresp = server.parse_handle_request(creq).content
    succ = client.parse_handle_response(sresp)
    assert not succ



def test_protocol_server_client_interleaved_swapped_reply(two_channels):
    server, client = two_channels

    client_request = client.sequence_command_local(SampleCommand('Hello'))
    server_request = server.sequence_command_local(SampleCommand('World'))

    server_reply = server.handle_request(client_request)
    assert server_reply.status == 'success'

    client_reply = client.handle_request(server_request)

    server.handle_response(client_reply)
    server_reply = server.handle_request(client_request)

    client.handle_response(server_reply)

    assert len(client.my_request_index) == 1
    assert len(server.other_request_index) == 1
    assert len(client.get_final_sequence()) == 2
    assert len(server.get_final_sequence()) == 2
    assert {c.command.item() for c in client.get_final_sequence()} == {
        'World', 'Hello'}
    assert {c.command.item() for c in server.get_final_sequence()} == {
        'World', 'Hello'}


def test_random_interleave_no_drop(two_channels):
    server, client = two_channels

    NUMBER = 20
    commands = list(range(NUMBER))
    commands = [SampleCommand(c) for c in commands]

    R = RandomRun(server, client, commands, seed='drop')
    R.DROP = False
    R.run()

    R.checks(NUMBER)

def test_random_interleave_and_drop(two_channels):
    server, client = two_channels

    NUMBER = 20
    commands = list(range(NUMBER))
    commands = [SampleCommand(c) for c in commands]

    R = RandomRun(server, client, commands, seed='drop')
    R.run()
    R.checks(NUMBER)



def test_random_interleave_and_drop_and_invalid(two_channels):
    server, client = two_channels

    NUMBER = 20
    commands = list(range(NUMBER))
    commands = [SampleCommand(c) for c in commands]
    for c in commands:
        c.always_happy = False

    R = RandomRun(server, client, commands, seed='drop')
    R.run()
    R.checks(NUMBER)

    client = R.client
    server = R.server

    client_seq = [c.command.item() for c in client.get_final_sequence()]
    server_seq = [c.command.item() for c in server.get_final_sequence()]

    server_store_keys = server.object_locks.keys()
    client_store_keys = client.object_locks.keys()
    assert set(server_store_keys) == set(client_store_keys)


def test_dependencies(two_channels):
    server, client = two_channels

    # Commands with dependencies
    cmd = [(0, []),
           (1, [0]),
           (2, []),
           (3, []),
           (4, [0]),
           (5, []),
           (6, [2]),
           (7, []),
           (8, [1]),
           (9, [4]),
           ]

    NUMBER = len(cmd)
    commands = [SampleCommand(c, deps) for c, deps in cmd]

    R = RandomRun(server, client, commands, seed='deps')
    R.run()
    R.checks(NUMBER)

    client = R.client
    server = R.server

    mapcmd = {
        c.command.item() for i, c in enumerate(
            client.get_final_sequence()
        )
    }
    # Only one of the items with common dependency commits
    assert len(mapcmd & {1, 4}) == 1
    assert len(mapcmd & {8, 9}) == 1
    # All items commit (except those with common deps)
    assert len(mapcmd) == 8


def test_json_serlialize():
    # Test Commands (to ensure correct debug)
    cmd = SampleCommand(1, [2, 3])
    cmd2 = SampleCommand(10, [2, 3])
    data = cmd.get_json_data_dict(JSONFlag.NET)
    cmd2 = SampleCommand.from_json_data_dict(data, JSONFlag.NET)
    assert cmd == cmd2

    # Test Request, Response
    req0 = CommandRequestObject(cmd)
    req2 = CommandRequestObject(cmd2)
    req0.cid = '10'
    req0.status = 'success'

    data = req0.get_json_data_dict(JSONFlag.STORE)
    assert data is not None
    req1 = CommandRequestObject.from_json_data_dict(data, JSONFlag.STORE)
    assert req0 == req1
    assert req1 != req2

    req0.response = make_protocol_error(req0, 'The error code')
    data_err = req0.get_json_data_dict(JSONFlag.STORE)
    assert data_err is not None
    assert data_err['response'] is not None
    req_err = CommandRequestObject.from_json_data_dict(
        data_err, JSONFlag.STORE)
    assert req0 == req_err


def test_VASProot(three_addresses, vasp):
    a0, a1, a2 = three_addresses

    # Check our own address is good
    assert vasp.get_vasp_address() == a0
    # Calling twice gives the same instance (use 'is')
    assert vasp.get_channel(a1) is vasp.get_channel(a1)
    # Different VASPs have different objects
    assert vasp.get_channel(a1) is not vasp.get_channel(a2)
    assert vasp.get_channel(a2).is_client()


def test_VASProot_diff_object(vasp, three_addresses):
    a0, _, b1 = three_addresses
    b2 = deepcopy(b1)

    # Check our own address is good
    assert vasp.get_vasp_address() == a0
    # Calling twice gives the same instance (use 'is')
    assert vasp.get_channel(b1) is vasp.get_channel(b2)


def test_real_address(three_addresses):
    from os import urandom
    A, _, B = three_addresses
    Ap = deepcopy(A)
    assert B.greater_than_or_equal(A)
    assert not A.greater_than_or_equal(B)
    assert A.greater_than_or_equal(A)
    assert A.greater_than_or_equal(Ap)
    assert A.equal(A)
    assert A.equal(Ap)
    assert not A.equal(B)
    assert not B.equal(Ap)
    assert A.last_bit() ^ B.last_bit() == 1
    assert A.last_bit() ^ A.last_bit() == 0


def test_sample_command():
    store = {}
    cmd1 = SampleCommand('hello')
    store['hello'] = cmd1.get_object('hello', store)
    cmd2 = SampleCommand('World', deps=['hello'])
    obj = cmd2.get_object('World', store)

    data = obj.get_json_data_dict(JSONFlag.STORE)
    obj2 = JSONSerializable.parse(data, JSONFlag.STORE)
    assert obj2.version == obj.version
    assert obj2.previous_versions == obj.previous_versions


def test_parse_handle_request_to_future(signed_json_request, channel, key):
    fut = channel.parse_handle_request(
        signed_json_request)
    res = fut.content
    res = json.loads(key.verify_message(res))
    assert res['status'] == 'success'


def test_parse_handle_request_to_future_out_of_order(json_request, channel,
                                                     key):
    json_request['cid'] = '100'
    json_request = key.sign_message(json.dumps(json_request))
    fut = channel.parse_handle_request(
        json_request
    )
    res = fut.content
    res = json.loads(key.verify_message(res))
    assert res['status']== 'success'


def test_parse_handle_request_to_future_exception(json_request, channel):
    with pytest.raises(Exception):
        fut = channel.parse_handle_request(
            json_request  # json_request is not signed.
        )


def test_parse_handle_response_to_future_parsing_error(json_response, channel,
                                                       command, key):
    _ = channel.sequence_command_local(command)
    json_response['cid'] = '"'  # Trigger a parsing error.
    json_response = key.sign_message(json.dumps(json_response))
    with pytest.raises(Exception):
        _ = channel.parse_handle_response(json_response)


def test_get_storage_factory(vasp):
    assert isinstance(vasp.get_storage_factory(), StorableFactory)


def test_role(channel):
    assert channel.role() == 'Client'

def test_pending_retransmit_number(channel):
    assert channel.pending_retransmit_number() == 0
