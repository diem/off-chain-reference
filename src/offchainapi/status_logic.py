""" The Payment object status is defined by the status of both actors,
    senders and receivers, namely the tuple (sender_status, recipient_status).
    An actor status may have the following values:

V0 States
---------

    * None  -- denotes the status of an object that does not exist
    * needs_stable_id -- requests the other VASP for a stable identifier
      for the payment recipient.
    * needs_kyc_data -- requires the other VASP to provide KYC data.
    * ready_for_settlement -- signals that the party is ready to settle
      the transaction.
    * needs_recipient_signature -- requests the recipient VASP to sign the
      identifier for this transaction to put it on chain.
    * signed -- The recipient signed the transaction to settle
    * settled -- a Libra transaction settles this transaction
    * abort - signals that the transactions is to be aborted.

"""

from collections import defaultdict
from enum import Enum


class Status(Enum):
    none = 'none',
    needs_stable_id = 'needs_stable_id',
    needs_kyc_data = 'needs_kyc_data',
    # Sender only
    needs_recipient_signature = 'needs_recipient_signature',
    # Receiver only: this is a virtual flag
    signed = 'signed',
    ready_for_settlement = 'ready_for_settlement',
    settled = 'settled',
    abort = 'abort'

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


# Sequence of status for sender
sender_payment_valid_lattice = \
    [
      (Status.none, Status.needs_kyc_data),
      (Status.needs_kyc_data, Status.needs_recipient_signature),
      (Status.needs_recipient_signature, Status.abort),  # Branch &Terminal
      (Status.needs_recipient_signature, Status.ready_for_settlement),
      (Status.ready_for_settlement, Status.settled)  # Terminal
    ]

# Sequence of status for receiver
receiver_payment_valid_lattice = \
    [
      (Status.none, Status.needs_kyc_data),
      # Branch & terminal
      (Status.needs_kyc_data, Status.abort),
      (Status.needs_kyc_data, Status.ready_for_settlement),
      # Terminal
      (Status.ready_for_settlement, Status.settled)
    ]

status_heights_MUST = {
    Status.none: 100,
    Status.needs_stable_id: 200,
    Status.needs_kyc_data: 200,
    Status.needs_recipient_signature: 200,
    Status.signed: 400,
    Status.ready_for_settlement: 400,
    Status.settled: 800,
    Status.abort: 1000
}

status_heights_SHOULD = {
    Status.none: 100,
    Status.needs_stable_id: 300,
    Status.needs_kyc_data: 400,
    Status.needs_recipient_signature: 500,
    Status.signed: 600,
    Status.ready_for_settlement: 700,
    Status.settled: 800,
    Status.abort: 1000
}


# Express cross party status dependencies & the starting states for process
dependencies = [
    (
        Status.settled, {Status.ready_for_settlement, Status.settled}
    )]

starting_states = [
    (Status.none, Status.none),
    (Status.needs_kyc_data, Status.none),
    (Status.none, Status.needs_kyc_data)
    ]


# Generic functions to create and compose processes
# =================================================

def add_self_loops(lattice):
    ''' Adds transitions from all states to themselves '''
    new_lattice = set(lattice)
    for st, ed in lattice:
        new_lattice.add((st, st))
        new_lattice.add((ed, ed))
    return new_lattice


def cross_product(L0, L1):
    ''' Makes a process from running two processes concurrently '''
    lattice = set()
    for (s0, e0) in L0:
        for (s1, e1) in L1:
            lattice.add(((s0, s1), (e0, e1)))
    return lattice


def add_aborts(jointlattice):
    ''' Adds aborts when one of the joint processes aborts '''
    lattice = set(jointlattice)
    for ((_, _), (e0, e1)) in list(lattice):
        if e0 == Status.abort or e1 == Status.abort:
            new_item = ((e0, e1), (Status.abort, Status.abort))
            lattice.add(new_item)
    return lattice


def keep_one_step(jointlattice):
    ''' Ensures that only one of the two joint processes makes progress '''
    lattice = set()
    for ((s0, s1), (e0, e1)) in jointlattice:
        item = ((s0, s1), (e0, e1))
        if s0 == e0 or s1 == e1:
            lattice.add(item)
    return lattice


def filter_for_cross_party_dependencies(jointlattice, dependencies):
    ''' Ensure cross process status dependencies are respected '''
    lattice = set(jointlattice)
    for (post_state, pre_state) in dependencies:
        for item in list(lattice):
            ((s0, s1), (e0, e1)) = item
            if e0 == post_state and s1 not in pre_state:
                lattice.remove(item)
            elif e1 == post_state and s0 not in pre_state:
                lattice.remove(item)
    return lattice


def filter_one_sided_progress(jointlattice, static_side=0):
    ''' Filters all transitions to keep one side static '''
    lattice = set(jointlattice)
    for item in list(lattice):
        (ST, EN) = item
        if ST[static_side] != EN[static_side]:
            lattice.remove(item)
    return lattice


def filter_for_starting_states(lattice, starting_states):
    ''' Returns all transitions reacheable from the starting states '''
    lattice_map = defaultdict(set)
    for (st, nd) in lattice:
        lattice_map[st].add(nd)

    reach = set()
    for item in starting_states:
        to_explore = set([item])
        while to_explore != set():
            next = to_explore.pop()
            reach.add(next)
            to_explore |= lattice_map[next] - reach

    lattice = [(st, en) for (st, en) in lattice if st in reach]
    return lattice


def extract_end_states(lattice):
    ''' Extracts the end states of the process '''
    return {ed for _, ed in lattice}


# Make payment status joint lattice
# =================================

def make_payment_status_lattice():
    ''' Creates the joint process of status updates
        for the payment protocol. '''
    LS = add_self_loops(sender_payment_valid_lattice)
    LR = add_self_loops(receiver_payment_valid_lattice)
    XSR = cross_product(LS, LR)
    XXSR_abort = add_aborts(XSR)
    step = keep_one_step(XXSR_abort)
    filtered = filter_for_cross_party_dependencies(step, dependencies)
    process = filter_for_starting_states(filtered, starting_states)
    return process


'''A global variable describing the payment protocol status process '''
payment_status_process = make_payment_status_lattice()


def is_valid_status_transition(
        start_sender, start_reciever,
        end_sender, end_receiver,
        is_sender):

    # Check that party has not changed the other side.
    if is_sender and (start_reciever != end_receiver):
        return False
    if not is_sender and (start_sender != end_sender):
        return False

    if is_sender:
        process = filter_one_sided_progress(payment_status_process, 1)
    else:
        process = filter_one_sided_progress(payment_status_process, 0)
    process = filter_by_heights(process, status_heights_MUST)

    all_states = filter_for_starting_states(process, [(start_sender, start_reciever)])
    terminals = extract_end_states(all_states)
    return (end_sender, end_receiver) in terminals

def is_valid_initial(start_sender, start_reciever, is_sender):
    if is_sender:
        process = filter_one_sided_progress(payment_status_process, 1)
    else:
        process = filter_one_sided_progress(payment_status_process, 0)
    process = filter_by_heights(process, status_heights_MUST)

    all_states = filter_for_starting_states(process, [(Status.none, Status.none)])
    terminals = extract_end_states(all_states)
    return (start_sender, start_reciever) in terminals


# These function just pretty print the status hierarchy
# =====================================================


def filter_by_heights(jointprocess, heights):  # pragma: no cover
    process = set(jointprocess)
    for item in list(jointprocess):
        ((s0, s1), (e0, e1)) = item
        if (s0, s1) == (e0, e1):
            continue
        elif s0 == e0 and not heights[e1] >= heights[e0]:
            process.remove(item)
        elif s1 == e1 and not heights[e0] >= heights[e1]:
            process.remove(item)
    return process


def sort_function(status_heights):  # pragma: no cover
    def status_pair_key(spair):
        return [status_heights[i] for i in spair]
    return status_pair_key


def print_status_transmition_updates(status_heights):  # pragma: no cover

    sender_progress = filter_one_sided_progress(payment_status_process, 1)
    all_starts = set([st for (st, en) in sender_progress])
    receiver_progress = filter_one_sided_progress(payment_status_process, 0)
    all_starts |= set([st for (st, en) in receiver_progress])

    sort = sort_function(status_heights)
    for st in sorted(all_starts, key=sort):
        terminals_sender = filter_for_starting_states(sender_progress, [st])
        ends_sender = [(st, ed) for ed in extract_end_states(terminals_sender)]
        ends_sender = filter_by_heights(ends_sender, status_heights)
        ends_sender = extract_end_states(ends_sender)

        terminals_receiver = \
            filter_for_starting_states(receiver_progress, [st])
        ends_receiver = \
            [(st, ed) for ed in extract_end_states(terminals_receiver)]
        ends_receiver = filter_by_heights(ends_receiver, status_heights)
        ends_receiver = extract_end_states(ends_receiver)

        if len(ends_sender) > 1 or len(ends_receiver) > 1:
            print()
            print('* STATUS:', st)

        if len(ends_sender) > 1:
            print('  Sender')
            for ed in sorted(ends_sender, key=sort):
                print(' '*8, '->', ed)

        if len(ends_receiver) > 1:
            print('  Receiver')
            for ed in sorted(ends_receiver, key=sort):
                print(' '*8, '->', ed)
