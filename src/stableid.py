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

from util import get_unique_string

ACCOUNT_TAG = 'account'
STABLEID_TAG = 'stableid'
SUBADDRESS_TAG = 'subaddress'

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


    def get_stable_id_for_account(self, account_number, period_id):
        ''' Return a stable identifier for an account number per period. 
            Ensure that stable identifiers are not linkable between periods. '''
        key = (STABLEID_TAG, account_number, period_id)
        if key not in self.storage:
            self.storage[key] = get_unique_string()
        return self.storage[key]


    def get_new_subaddress_for_account(self, account_number, scope=None):
        ''' Makes a fresh sub-address with a specific scope '''
        new_subaddress = get_unique_string()
        key = (SUBADDRESS_TAG, new_subaddress) 
        self.storage[key] = (account_number, scope)
        return new_subaddress

    def resolve_subaddress_to_account(self, sub_address):
        ''' Resolve a subaddress to an account address and scope '''
        key = (SUBADDRESS_TAG, sub_address) 
        if key not in self.storage:
            raise SubAddressError(f'Sub-address {sub_address} does not exist.')
        account_number, scope = self.storage[key]
        return account_number, scope

    def get_all_subaddress_by_account(self, account_number):
        # TODO: Make a list structure to keep track of subaccounts
        raise NotImplementedError()

    # Experimental features

    def revoke_subaddress(self, sub_address):
        # TODO: ...
        raise NotImplementedError()

    def resolve_authenticator(self, sub_address, scope):
        # TODO: ...
        raise NotImplementedError()
