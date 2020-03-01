from collections import defaultdict

class TypeEnumeration:
    ''' Express & Validate status values '''
    def __init__(self, allowed):
        self._allowed = set(allowed)

    def __getattr__(self, attr):
        #only called what self.attr doesn't exist
        if attr in self._allowed:
            return attr
        raise StructureException('Status %s not supported' % attr)

    def __contains__(self, item):
        return item in self._allowed

Status = TypeEnumeration([
    'none',
    'maybe_needs_kyc',           # Sender only
    'needs_stable_id',
    'needs_kyc_data',
    'ready_for_settlement',
    'needs_recipient_signature', # Sender only
    'signed',                    # Receiver only
    'settled',
    'abort'
])

# Sequence of status for sender
sender_payment_valid_lattice = \
    [ (Status.none, Status.maybe_needs_kyc),
      (Status.maybe_needs_kyc, Status.needs_stable_id),
      (Status.needs_stable_id, Status.needs_kyc_data),
      (Status.needs_kyc_data, Status.ready_for_settlement),
      (Status.needs_kyc_data, Status.abort), # Branch &Terminal
      (Status.ready_for_settlement, Status.needs_recipient_signature),
      (Status.needs_recipient_signature, Status.settled) # Terminal
    ]

# Sequence of status for receiver
receiver_payment_valid_lattice = \
    [ (Status.none, Status.needs_stable_id),
      (Status.needs_stable_id, Status.needs_kyc_data),
      (Status.needs_kyc_data, Status.ready_for_settlement),
      (Status.needs_kyc_data, Status.abort), # Branch & terminal
      (Status.ready_for_settlement, Status.signed),
      (Status.signed, Status.settled) # Terminal
    ]

# Express cross party status dependencies & the starting states for process
dependencies = [(Status.settled, {Status.settled, Status.signed}) ]
starting_states = [ (Status.none, Status.none) ]

# Generic functions to create and compose processes

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
            lattice.add(((s0,s1), (e0, e1)))
    return lattice

def add_aborts(jointlattice):
    ''' Adds aborts when once of the joint process aborts '''
    lattice = set(jointlattice)
    for ((s0, s1),(e0, e1)) in list(lattice):
        if e0 == Status.abort or e1 == Status.abort:
            new_item = ((e0, e1),(Status.abort, Status.abort))
            lattice.add(new_item)
    return lattice

def keep_one_step(jointlattice):
    ''' Ensures that only one of the two joint processes makes progress '''
    lattice = set()
    for ((s0, s1), (e0, e1)) in jointlattice:
        item = ((s0, s1), (e0, e1))
        #((s0, s1), (e0, e1)) = item
        if s0 == e0 or s1 == e1:
            lattice.add(item)
    return lattice

def filter_for_dependencies(jointlattice, dependencies):
    ''' Ensure cross process status dependencies are respected '''
    lattice = set(jointlattice)
    for (post_state, pre_state) in dependencies:
        for item in list(lattice):
            ((s0, s1), (e0, e1)) = item
            if e0 == post_state and not s1 in pre_state:
                lattice.remove(item)
            elif e1 == post_state and not s0 in pre_state:
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
        to_explore = set([ item ])
        while to_explore != set():
            next = to_explore.pop()
            reach.add(next)
            to_explore = to_explore | lattice_map[next]
            to_explore = to_explore - reach

    lattice = [(st, en) for (st, en) in lattice if st in reach]
    return lattice

def extract_end_states(lattice):
    ''' Extracts the end states of the process '''
    return {ed for _, ed in lattice}

## Make payment status joint lattice

def make_payment_status_lattice():
    ''' Creates the joint process of status updates for the payment protocol '''
    LS = add_self_loops(sender_payment_valid_lattice)
    LR = add_self_loops(receiver_payment_valid_lattice)
    XSR = cross_product(LS, LR)
    XXSR_abort = add_aborts(XSR)
    step = keep_one_step(XXSR_abort)
    filtered = filter_for_dependencies(step, dependencies)
    process = filter_for_starting_states(filtered, starting_states)
    return process

''' A global variable describing the payment protocol status process '''
payment_status_process = make_payment_status_lattice()
