from status_logic import *

def test_lattice_finality_barrier_works():
    process = payment_status_process

    # Prove that when both sides are ready to settle an abort cannot happen.
    terminals = filter_for_starting_states(process, [(Status.ready_for_settlement, Status.ready_for_settlement)] )
    for ((s0,e0), (s1, e1)) in terminals:
        assert Status.abort not in [s0, e0, s1, e1]

def test_sender_cannot_settle_alone():
    process = payment_status_process
    sender_progress = filter_one_sided_progress(process,1)
    terminals = filter_for_starting_states(sender_progress, [(Status.none, Status.none)] )
    assert (Status.settled, Status.settled) not in extract_end_states(terminals)

def test_receiver_cannot_settle_alone():
    process = payment_status_process
    sender_progress = filter_one_sided_progress(process,0)
    terminals = filter_for_starting_states(sender_progress, [(Status.none, Status.none)] )
    assert (Status.settled, Status.settled) not in extract_end_states(terminals)

def test_process_is_live():
    process = payment_status_process
    # sender_progress = filter_one_sided_progress(process,0)
    terminals = filter_for_starting_states(process, [(Status.none, Status.none)] )
    assert (Status.settled, Status.settled) in extract_end_states(terminals)
    assert (Status.abort, Status.abort) in extract_end_states(terminals)

if __name__ == '__main__':
    print_status_transmition_updates()
