import pytest
import types
from copy import deepcopy

from models import *
from business import *
import random

# Define mock classes

class SampleObject(SharedObject):
    def __init__(self, item):
        SharedObject.__init__(self)
        self.item = item

class SampleCommand(ProtocolCommand):
    def __init__(self, command):
        command = SampleObject(command)
        self.depend_on = []
        self.creates   = [ command.item ]
        self.command   = command
        self.always_happy = True
        self.commit_status = None

    def get_object(self, version_number, dependencies):
        return self.command

    def item(self):
        return self.command.item

    def __eq__(self, other):
        return self.depend_on == other.depend_on \
            and self.creates == other.creates \
            and self.command.item == other.command.item

    def validity_checks(self, dependencies, maybe_own=True):
        return maybe_own or self.always_happy or random.random() > 0.75

    def __str__(self):
        return 'CMD(%s)' % self.item()



class FakeAddress(LibraAddress):
    def __init__(self, bit, addr):
        self.bit = bit
        self.addr = addr

    def last_bit(self):
        return self.bit

    def greater_than_or_equal(self, other):
        return self.addr >= other.addr

    def equal(self, other):
        return self.addr >= other.addr

class FakeVASPInfo(VASPInfo):
    def __init__(self, parent_addr):
        self.parent = parent_addr

    def get_parent_address(self):
        return self.parent


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


def test_client_server_role_definition():

    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

    # Lower address is server (xor bit = 0)
    channel = VASPPairChannel(a0, a1)
    assert channel.is_server()
    assert not channel.is_client()

    channel = VASPPairChannel(a1, a0)
    assert not channel.is_server()
    assert channel.is_client()

    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(1, 30))

    # Lower address is server (xor bit = 1)
    channel = VASPPairChannel(a0, a1)
    assert not channel.is_server()
    assert channel.is_client()

    channel = VASPPairChannel(a1, a0)
    assert channel.is_server()
    assert not channel.is_client()


def test_protocol_server_client_benign():
    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    server = monkey_tap(server)
    client = monkey_tap(client)

    # Create a server request for a command
    server.sequence_command_local(SampleCommand('Hello'))
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
    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

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
    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

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
    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

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
    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

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
    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

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

    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)



    random.seed('Random_interleave')
    NUMBER = 100
    commands = list(range(NUMBER))
    to_server_requests = []
    to_client_response = []

    to_client_requests  = []
    to_server_response = []

    server = monkey_tap_to_list(server, to_client_requests, to_client_response)
    client = monkey_tap_to_list(client, to_server_requests, to_server_response)

    while True:
        # Inject a command every round
        if random.random() > 0.99:
            if len(commands) > 0:
                c = commands.pop(0)
                if random.random() > 0.5:
                    client.sequence_command_local(SampleCommand(c))
                else:
                    server.sequence_command_local(SampleCommand(c))

        # Make progress by delivering a random queue
        if len(to_server_requests) > 0 and random.random() > 0.5:
            client_request = to_server_requests.pop(0)
            server.handle_request(client_request)

        if len(to_client_requests) > 0 and random.random() > 0.5:
            server_request = to_client_requests.pop(0)
            client.handle_request(server_request)

        if len(to_client_response) > 0 and random.random() > 0.5:
            resp = to_client_response.pop(0)
            # assert req.client_sequence_number is not None
            client.handle_response(resp)

        if len(to_server_response) > 0 and random.random() > 0.5:
            resp = to_server_response.pop(0)
            server.handle_response(resp)

        # Retransmit
        if random.random() > 0.99:
            client.retransmit()
            server.retransmit()

        if not server.would_retransmit() and not client.would_retransmit() \
            and server.executor.last_confirmed == NUMBER \
            and client.executor.last_confirmed == NUMBER:
            break

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert client_seq == server_seq
    assert len(client_seq) == NUMBER

    # Print stats:
    print("Client: Requests #%d  Responses #%d" % (client.xx_requests_stats, client.xx_replies_stats))
    print("Server: Requests #%d  Responses #%d" % (server.xx_requests_stats, server.xx_replies_stats))


def test_random_interleave_and_drop():

    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    random.seed('Random_drop')
    NUMBER = 100
    commands = list(range(NUMBER))
    to_server_requests = []
    to_client_response = []

    to_client_requests  = []
    to_server_response = []

    server = monkey_tap_to_list(server, to_client_requests, to_client_response)
    client = monkey_tap_to_list(client, to_server_requests, to_server_response)

    while True:
        # Inject a command every round
        if random.random() > 0.99:
            if len(commands) > 0:
                c = commands.pop(0)
                if random.random() > 0.5:
                    client.sequence_command_local(SampleCommand(c))
                    if random.random() > 0.5:
                        del to_server_requests[-1:]
                else:
                    server.sequence_command_local(SampleCommand(c))
                    if random.random() > 0.5:
                        del to_client_requests[-1:]

        # Make progress by delivering a random queue
        if len(to_server_requests) > 0 and random.random() > 0.5:
            client_request = to_server_requests.pop(0)
            server.handle_request(client_request)

        if len(to_client_requests) > 0 and random.random() > 0.5:
            server_request = to_client_requests.pop(0)
            client.handle_request(server_request)

        if len(to_client_response) > 0 and random.random() > 0.5:
            rep = to_client_response.pop(0)
            # assert req.client_sequence_number is not None
            client.handle_response(rep)

        if len(to_server_response) > 0 and random.random() > 0.5:
            rep = to_server_response.pop(0)
            server.handle_response(rep)

        # Retransmit
        if random.random() > 0.99:
            client.retransmit()
            server.retransmit()

        # print(list(map(len, [commands, to_server_requests, to_client_response, to_client_requests, to_server_response])))

        if not server.would_retransmit() and not client.would_retransmit() \
            and server.executor.last_confirmed == NUMBER \
            and client.executor.last_confirmed == NUMBER:
            break

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert len(client_seq) == NUMBER
    assert client_seq == server_seq
    assert set(range(NUMBER)) ==  set(client_seq)

    # Print stats:
    print("Client: Requests #%d  Responses #%d" % (client.xx_requests_stats, client.xx_replies_stats))
    print("Server: Requests #%d  Responses #%d" % (server.xx_requests_stats, server.xx_replies_stats))


    # Now test if executor has the same set
    client_exec_seq = client_seq = [c.item() for c in client.executor.seq]
    server_exec_seq = client_seq = [c.item() for c in server.executor.seq]
    assert set(client_seq) == set(client_exec_seq)
    assert set(server_seq) == set(server_exec_seq)

def test_random_interleave_and_drop_and_invalid():

    a0 = FakeVASPInfo(FakeAddress(0, 10))
    a1 = FakeVASPInfo(FakeAddress(0, 20))

    server = VASPPairChannel(a0, a1)
    client = VASPPairChannel(a1, a0)

    random.seed('Random_fail')
    NUMBER = 100
    commands = list(range(NUMBER))
    to_server_requests = []
    to_client_response = []

    to_client_requests  = []
    to_server_response = []

    server = monkey_tap_to_list(server, to_client_requests, to_client_response)
    client = monkey_tap_to_list(client, to_server_requests, to_server_response)

    while True:
        # Inject a command every round
        if random.random() > 0.99:
            if len(commands) > 0:
                c = commands.pop(0)
                cmd = SampleCommand(c)
                cmd.always_happy = False
                if random.random() > 0.5:
                    client.sequence_command_local(cmd)
                    if random.random() > 0.5:
                        del to_server_requests[-1:]
                else:
                    server.sequence_command_local(cmd)
                    if random.random() > 0.5:
                        del to_client_requests[-1:]

        # Make progress by delivering a random queue
        if len(to_server_requests) > 0 and random.random() > 0.5:
            client_request = to_server_requests.pop(0)
            server.handle_request(client_request)

        if len(to_client_requests) > 0 and random.random() > 0.5:
            server_request = to_client_requests.pop(0)
            client.handle_request(server_request)

        if len(to_client_response) > 0 and random.random() > 0.5:
            rep = to_client_response.pop(0)
            # assert req.client_sequence_number is not None
            client.handle_response(rep)

        if len(to_server_response) > 0 and random.random() > 0.5:
            rep = to_server_response.pop(0)
            server.handle_response(rep)

        # Retransmit
        if random.random() > 0.99:
            client.retransmit()
            server.retransmit()

        # print(list(map(len, [commands, to_server_requests, to_client_response, to_client_requests, to_server_response])))

        if not server.would_retransmit() and not client.would_retransmit() \
            and server.executor.last_confirmed == NUMBER \
            and client.executor.last_confirmed == NUMBER:
            break

    client_seq = [c.item() for c in client.get_final_sequence()]
    server_seq = [c.item() for c in server.get_final_sequence()]

    assert len(client_seq) == NUMBER
    assert client_seq == server_seq
    assert set(range(NUMBER)) ==  set(client_seq)

    # Print stats:
    print("Client: Requests #%d  Responses #%d" % (client.xx_requests_stats, client.xx_replies_stats))
    print("Server: Requests #%d  Responses #%d" % (server.xx_requests_stats, server.xx_replies_stats))


    # Now test if executor has the same set
    client_exec_seq = client_seq = [c.item() for c in client.executor.seq]
    server_exec_seq = client_seq = [c.item() for c in server.executor.seq]
    assert set(client_seq) == set(client_exec_seq)
    assert set(server_seq) == set(server_exec_seq)

    assert set(server.executor.object_store.keys()) == set(client.executor.object_store.keys())
