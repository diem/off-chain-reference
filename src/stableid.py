''' A sample implementation to support privacy-friendly subaddresses and stable IDs in Business Contexts. 

    Key features:
        - Register long term user accounts.
        - Allows fresh subaddresses to be derived.
        - Can limit the scope for subaddresses to specific time periods, roles and correspondants.
        - No dependence on any external cryptography library to maximize compatibility.
    
    Experimental:
        - Ability to revoke subaddresses.
        - Support pull authorization flows.


'''

from utils import get_unique_string

ACCOUNT_TAG = 'account'
STABLEID_TAG = 'stableid'
SUBADDRESS_TAG = 'subaddress'
SUBHEAD_TAG = 'subhead'

class SubAddressError(Exception):
    pass

class SubAddressResolver:

    def __init__(self, storage):
        ''' Initializes the resolver with a storage system that follows the dict 
            protocol (can be gnudb) or other persistent store. '''
        self.storage = storage

    # Core features

    def register_account_number(self, account_number, meta_data = None):
        ''' Register an account number and some associated meta-data. '''
        if meta_data is None:
            meta_data = {}
        key = (ACCOUNT_TAG, account_number)
        self.storage[key] = meta_data
    
    def get_account_by_number(self, account_number):
        key = (ACCOUNT_TAG, account_number)
        if key not in self.storage:
            raise SubAddressError(f'Account number {account_number} does not exist.')
        return self.storage[key]


    def get_stable_id_for_account(self, account_number, period_id):
        ''' Return a stable identifier for an account number per period. 
            Ensure that stable identifiers are not linkable between periods. '''
        key = (ACCOUNT_TAG, account_number)
        if key not in self.storage:
            raise SubAddressError(f'Account number {account_number} does not exist.')
        
        key = (STABLEID_TAG, account_number, period_id)
        if key not in self.storage:
            self.storage[key] = get_unique_string()
        return self.storage[key]


    def get_new_subaddress_for_account(self, account_number, scope=None):
        ''' Makes a fresh sub-address with a specific scope '''
        key = (ACCOUNT_TAG, account_number)
        if key not in self.storage:
            raise SubAddressError(f'Account number {account_number} does not exist.')

        # Check if there is a previous subaddress
        prev_subaddress =  None
        key_head = (SUBHEAD_TAG, account_number)
        if key_head in self.storage:
            prev_subaddress = self.storage[key_head]

        # Create a sub address
        new_subaddress = get_unique_string()
        key = (SUBADDRESS_TAG, new_subaddress) 
        self.storage[key] = (account_number, scope, prev_subaddress)

        # Make new subaddress the head of the list
        self.storage[key_head] = new_subaddress

        return new_subaddress

    def resolve_subaddress_to_account(self, sub_address):
        ''' Resolve a subaddress to an account address and scope '''
        key = (SUBADDRESS_TAG, sub_address) 
        if key not in self.storage:
            raise SubAddressError(f'Sub-address {sub_address} does not exist.')
        account_number, scope, _ = self.storage[key]
        return account_number, scope

    def get_all_subaddress_by_account(self, account_number):
        # TODO: Make a list structure to keep track of subaccounts
        key_head = (SUBHEAD_TAG, account_number) 
        if key_head not in self.storage:
            return

        curr_subaddress = self.storage[key_head]
        while curr_subaddress is not None:
            yield curr_subaddress
            key = (SUBADDRESS_TAG, curr_subaddress) 
            _, _, curr_subaddress = self.storage[key]

    # Experimental features

    def revoke_subaddress(self, sub_address):
        # TODO: ...
        raise NotImplementedError()

    def resolve_authenticator(self, sub_address, scope):
        # TODO: ...
        raise NotImplementedError()
