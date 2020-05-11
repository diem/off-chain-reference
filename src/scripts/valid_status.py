from offchainapi.status_logic import Status, \
    print_status_transmition_updates, payment_status_process, status_heights_MUST

if __name__ == '__main__':
    print_status_transmition_updates(status_heights_MUST)
