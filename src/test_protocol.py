import pytest
import types
from copy import deepcopy

from protocol import *
from executor import *
from protocol_messages import *
from business import BusinessContext, VASPInfo
import random

from unittest.mock import MagicMock
import pytest


class FakeAddress(LibraAddress):
    def __init__(self, bit, addr):
        self.bit = bit
        self.addr = addr
        self.encoded_address = str(addr)

    def last_bit(self):
        return self.bit

    def greater_than_or_equal(self, other):
        return self.addr >= other.addr

    def equal(self, other):
        return self.addr >= other.addr

class FakeVASPInfo(VASPInfo):
    def __init__(self, parent_addr, own_address = None):
        self.parent = parent_addr
        self.own_address = own_address

    def get_parent_address(self):
        return self.parent
    
    def get_libra_address(self):
        """ The settlement Libra address for this channel"""
        return self.own_address


def monkey_tap(pair):
    pair.msg = []

    def to_tap(self, msg):
        assert msg is not None
        self.msg += [ deepcopy(msg) ]

    def tap(self):
        msg = self.msg
        self.msg = []
        return msg

    pair.tap = types.MethodType(tap, pair)
    pair.send_request = types.MethodType(to_tap, pair)
    pair.send_response = types.MethodType(to_tap, pair)
    return pair

def monkey_tap_to_list(pair, requests_sent, replies_sent):
    pair.msg = []
    pair.xx_requests_sent = requests_sent
    pair.xx_replies_sent  = replies_sent
    pair.xx_requests_stats = 0
    pair.xx_replies_stats  = 0


    def to_tap_requests(self, msg):
        assert msg is not None
        assert isinstance(msg, CommandRequestObject)
        self.xx_requests_stats += 1
        self.xx_requests_sent += [ deepcopy(msg) ]

    def to_tap_reply(self, msg):
        assert isinstance(msg, CommandResponseObject)
        assert msg is not None
        self.xx_replies_stats += 1
        self.xx_replies_sent += [ deepcopy(msg) ]

    pair.send_request = types.MethodType(to_tap_requests, pair)
    pair.send_response = types.MethodType(to_tap_reply, pair)
    return pair

class RandomRun(object):
    def __init__(self, server, client, commands, seed='fixed seed'):

        # MESSAGE QUEUES
        self.to_server_requests = []
        self.to_client_response = []
        self.to_client_requests  = []
        self.to_server_response = []

        self.server = monkey_tap_to_list(server, self.to_client_requests, self.to_client_response)
        self.client = monkey_tap_to_list(client, self.to_server_requests, self.to_server_response)

        self.commands = commands
        self.number = len(commands)
        random.seed(seed)

        self.DROP = True
        self.VERBOSE = False

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
                            client.sequence_command_local(c)
                        else:
                            server.sequence_command_local(c)
                    except ExecutorException:
                        commands.insert(0, c)

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
                server.handle_request(client_request)

            if Case[1] and len(to_client_requests) > 0:
                server_request = to_client_requests.pop(0)
                client.handle_request(server_request)

            if Case[2] and len(to_client_response) > 0:
                rep = to_client_response.pop(0)
                # assert req.client_sequence_number is not None
                client.handle_response(rep)

            if Case[3] and len(to_server_response) > 0:
                rep = to_server_response.pop(0)
                server.handle_response(rep)

            # Retransmit
            if Case[4] and random.random() > 0.10:
                client.retransmit()
                server.retransmit()

            if self.VERBOSE:
                print([to_server_requests,
                                          to_client_requests,
                                          to_client_response,
                                          to_server_response])

                print([server.would_retransmit(),
                        client.would_retransmit(),
                        server.executor.last_confirmed,
                        client.executor.last_confirmed])

            if not server.would_retransmit() and not client.would_retransmit() \
                and server.executor.last_confirmed == self.number \
                and client.executor.last_confirmed == self.number:
                break

def test_client_server_role_definition():

    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    # Lower address is server (xor bit = 0)
    channel = VASPPairChannel(a0, a1)
    assert channel.is_server()
    assert not channel.is_client()

    channel = VASPPairChannel(a1, a0)
    assert not channel.is_server()
    assert channel.is_client()

    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(1, 30)

    # Lower address is server (xor bit = 1)
    channel = VASPPairChannel(a0, a1)
    assert not channel.is_server()
    assert channel.is_client()

    channel = VASPPairChannel(a1, a0)
    assert channel.is_server()
    assert not channel.is_client()


def test_protocol_server_client_benign():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    # Create a server request for a command
    server.sequence_command_local(SampleCommand('Hello'))
    assert len(server.get_final_sequence()) > 0

    msg_list = server.tap()
    assert len(msg_list) == 1
    request = msg_list.pop()
    assert isinstance(request, CommandRequestObject)
    assert server.my_next_seq == 1

    # Pass the request to the client
    assert client.other_next_seq == 0
    client.handle_request(request)
    msg_list = client.tap()
    assert len(msg_list) == 1
    reply = msg_list.pop()
    assert isinstance(reply, CommandResponseObject)
    assert client.other_next_seq == 1
    assert reply.status == 'success'

    # Pass the reply back to the server
    assert server.get_final_sequence()[0].commit_status is None
    server.handle_response(reply)
    msg_list = server.tap()
    assert len(msg_list) == 0 # No message expected

    assert server.get_final_sequence()[0].commit_status is not None
    assert client.get_final_sequence()[0].commit_status is not None
    assert client.get_final_sequence()[0].item() == 'Hello'


def test_protocol_server_conflicting_sequence():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    # Create a server request for a command
    server.sequence_command_local(SampleCommand('Hello'))
    request = server.tap()[0]

    # Modilfy message to be a conflicting sequence number
    request_conflict = deepcopy(request)
    assert request_conflict.seq == 0
    request_conflict.command = SampleCommand("Conflict")

    # Pass the request to the client
    client.handle_request(request)
    reply = client.tap()[0]
    client.handle_request(request_conflict)
    reply_conflict = client.tap()[0]

    # We only sequence one command.
    assert client.other_next_seq == 1
    assert reply.status == 'success'

    # The response to the second command is a failure
    assert reply_conflict.status == 'failure'
    assert reply_conflict.error.code == 'conflict'

    # Pass the reply back to the server
    assert server.get_final_sequence()[0].commit_status is None
    server.handle_response(reply)
    msg_list = server.tap()
    assert len(msg_list) == 0 # No message expected

    assert server.get_final_sequence()[0].commit_status is not None
    assert client.get_final_sequence()[0].commit_status is not None
    assert client.get_final_sequence()[0].item() == 'Hello'

def test_protocol_client_server_benign():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    # Create a server request for a command
    client.sequence_command_local(SampleCommand('Hello'))
    msg_list = client.tap()
    assert len(msg_list) == 1
    request = msg_list.pop()
    assert isinstance(request, CommandRequestObject)
    assert client.other_next_seq == 0
    assert client.my_next_seq == 1

    # Send to server
    assert server.other_next_seq == 0
    server.handle_request(request)
    msg_list = server.tap()
    assert len(msg_list) == 1
    reply = msg_list.pop()
    assert isinstance(reply, CommandResponseObject)
    assert server.other_next_seq == 1
    assert server.next_final_sequence() == 1
    assert server.get_final_sequence()[0].commit_status is not None
    assert reply.status == 'success'

    # Pass response back to client
    assert client.my_requests[0].response is None
    client.handle_response(reply)
    msg_list = client.tap()
    assert len(msg_list) == 0 # No message expected

    assert client.get_final_sequence()[0].commit_status is not None
    assert client.my_requests[0].response is not None
    assert client.get_final_sequence()[0].item() == 'Hello'
    assert client.next_final_sequence() == 1
    assert client.my_next_seq == 1
    assert server.my_next_seq == 0


def test_protocol_server_client_interleaved_benign():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    client.sequence_command_local(SampleCommand('Hello'))
    client_request = client.tap()[0]
    server.sequence_command_local(SampleCommand('World'))
    server_request = server.tap()[0]

    # The server waits until all own requests are done
    server.handle_request(client_request)
    no_reply = server.tap()
    assert no_reply == []

    client.handle_request(server_request)
    client_reply = client.tap()[0]

    server.handle_response(client_reply)
    server_reply = server.tap()[0]

    client.handle_response(server_reply)

    assert len(client.my_requests) == 1
    assert len(server.other_requests) == 1
    assert len(client.get_final_sequence()) == 2
    assert len(server.get_final_sequence()) == 2
    assert [c.item() for c in client.get_final_sequence()] == ['World', 'Hello']
    assert [c.item() for c in server.get_final_sequence()] == ['World', 'Hello']

def test_protocol_server_client_interleaved_swapped_request():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    client.sequence_command_local(SampleCommand('Hello'))
    client_request = client.tap()[0]
    server.sequence_command_local(SampleCommand('World'))
    server_request = server.tap()[0]

    client.handle_request(server_request)
    client_reply = client.tap()[0]
    server.handle_request(client_request)
    no_reply = server.tap()
    assert no_reply == []

    server.handle_response(client_reply)
    server_reply = server.tap()[0]

    client.handle_response(server_reply)

    assert len(client.my_requests) == 1
    assert len(server.other_requests) == 1
    assert len(client.get_final_sequence()) == 2
    assert len(server.get_final_sequence()) == 2
    assert [c.item() for c in client.get_final_sequence()] == ['World', 'Hello']
    assert [c.item() for c in server.get_final_sequence()] == ['World', 'Hello']

def test_protocol_server_client_interleaved_swapped_reply():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    client.sequence_command_local(SampleCommand('Hello'))
    client_request = client.tap()[0]
    server.sequence_command_local(SampleCommand('World'))
    server_request = server.tap()[0]

    server.handle_request(client_request)
    server_reply = server.tap()
    assert server_reply == []

    client.handle_request(server_request)
    client_reply = client.tap()[0]

    server.handle_response(client_reply)
    server_reply = server.tap()[0]

    client.handle_response(server_reply)

    assert len(client.my_requests) == 1
    assert len(server.other_requests) == 1
    assert len(client.get_final_sequence()) == 2
    assert len(server.get_final_sequence()) == 2
    assert [c.item() for c in client.get_final_sequence()] == ['World', 'Hello']
    assert [c.item() for c in server.get_final_sequence()] == ['World', 'Hello']

def test_random_interleave_no_drop():

    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    NUMBER = 20
    commands = list(range(NUMBER))
    commands = [SampleCommand(c) for c in commands]

    R = RandomRun(server, client, commands, seed='drop')
    R.DROP = False
    R.run()

    client = R.client
    server = R.server

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert client_seq == server_seq
    assert len(client_seq) == NUMBER

    # Print stats:
    print()
    print("Client: Requests #%d  Responses #%d" % (client.xx_requests_stats, client.xx_replies_stats))
    print("Server: Requests #%d  Responses #%d" % (server.xx_requests_stats, server.xx_replies_stats))


def test_random_interleave_and_drop():

    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)


    NUMBER = 20
    commands = list(range(NUMBER))
    commands = [SampleCommand(c) for c in commands]

    R = RandomRun(server, client, commands, seed='drop')
    R.run()

    client = R.client
    server = R.server

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert len(client_seq) == NUMBER
    assert client_seq == server_seq
    assert set(range(NUMBER)) ==  set(client_seq)

    # Print stats:
    print()
    print("Client: Requests #%d  Responses #%d" % (client.xx_requests_stats, client.xx_replies_stats))
    print("Server: Requests #%d  Responses #%d" % (server.xx_requests_stats, server.xx_replies_stats))


    # Now test if executor has the same set
    client_exec_seq = client_seq = [c.item() for c in client.executor.seq]
    server_exec_seq = client_seq = [c.item() for c in server.executor.seq]
    assert set(client_seq) == set(client_exec_seq)
    assert set(server_seq) == set(server_exec_seq)

def test_random_interleave_and_drop_and_invalid():

    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    NUMBER = 20
    commands = list(range(NUMBER))
    commands = [SampleCommand(c) for c in commands]
    for c in commands:
        c.always_happy = False

    R = RandomRun(server, client, commands, seed='drop')
    R.run()

    client = R.client
    server = R.server

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert len(client_seq) == NUMBER
    assert client_seq == server_seq
    assert set(range(NUMBER)) ==  set(client_seq)

    # Print stats:
    print()
    print("Client: Requests #%d  Responses #%d" % (client.xx_requests_stats, client.xx_replies_stats))
    print("Server: Requests #%d  Responses #%d" % (server.xx_requests_stats, server.xx_replies_stats))


    # Now test if executor has the same set
    client_exec_seq = client_seq = [c.item() for c in client.executor.seq]
    server_exec_seq = client_seq = [c.item() for c in server.executor.seq]
    assert set(client_seq) == set(client_exec_seq)
    assert set(server_seq) == set(server_exec_seq)

    assert set(server.executor.object_store.keys()) == set(client.executor.object_store.keys())

def test_dependencies():
    a0 = FakeAddress(0, 10)
    a1 = FakeAddress(0, 20)

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    # Commands with dependencies
    cmd = [ (0, []),
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

    client = R.client
    server = R.server

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert len(client_seq) == NUMBER
    assert client_seq == server_seq
    assert set(range(NUMBER)) ==  set(client_seq)

    client_seq_success = [c.commit_status for c in client.get_final_sequence()]
    server_seq_success = [c.commit_status for c in server.get_final_sequence()]

    assert client_seq_success == server_seq_success

    mapcmd = { c.item():c.commit_status for c in  client.get_final_sequence()}
    # Only one of the items with common dependency commits
    assert sum([mapcmd[1], mapcmd[4]]) == 1
    assert sum([mapcmd[8], mapcmd[9]]) == 1
    # All items commit (except those with common deps)
    assert sum(mapcmd.values()) == 8

def test_json_serlialize():

    # Test Commands (to ensure correct debug)
    cmd = SampleCommand(1, [2, 3])
    cmd2 = SampleCommand(10, [2, 3])
    data = cmd.get_json_data_dict(JSON_NET)
    cmd2 = SampleCommand.from_json_data_dict(data, JSON_NET)
    assert cmd == cmd2

    # First register the SimpleCommand class
    CommandRequestObject.register_command_type(SampleCommand)

    # Test Request, Response
    req0 = CommandRequestObject(cmd)
    req2 = CommandRequestObject(cmd2)
    req0.seq = 10
    req0.command_seq = 15
    req0.status = 'success'

    data = req0.get_json_data_dict(JSON_STORE)
    assert data is not None
    req1 = CommandRequestObject.from_json_data_dict(data, JSON_STORE)
    assert req0 == req1
    assert req1 != req2

    req0.response = make_protocol_error(req0, 'The error code')
    data_err = req0.get_json_data_dict(JSON_STORE)
    assert data_err is not None
    assert data_err['response'] is not None
    req_err = CommandRequestObject.from_json_data_dict(data_err, JSON_STORE)
    assert req0 == req_err

def test_VASProot():
    a0 = LibraAddress.encode_to_Libra_address(b'A'*16)
    a1 = LibraAddress.encode_to_Libra_address(b'B'*16)
    a2 = LibraAddress.encode_to_Libra_address(b'C'*16)
    bcm = MagicMock(spec=BusinessContext)
    vasp = OffChainVASP(a0, bcm)

    # Check our own address is good
    assert vasp.my_vasp_addr() == a0
    # Calling twice gives the same instance (use 'is')
    assert vasp.get_channel(a1) is vasp.get_channel(a1)
    # Different VASPs have different objects
    assert vasp.get_channel(a1) is not vasp.get_channel(a2)
    assert vasp.get_channel(a1).is_client()

def test_real_address():
    from os import urandom
    A = LibraAddress.encode_to_Libra_address(b'A'*16)
    Ap = LibraAddress.encode_to_Libra_address(b'A'*16)
    B = LibraAddress.encode_to_Libra_address(b'B'*16)
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
