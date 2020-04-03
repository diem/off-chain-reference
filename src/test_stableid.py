from stableid import *
import pytest

@pytest.fixture
def base():
    db = {}
    res = SubAddressResolver(db)
    return db, res

def test_base_strct(base):
    db, res = base

    # Create
    res.register_account_number('ABC')
    # Get
    meta = res.get_account_by_number('ABC')
    assert meta == {}

    # Check existence
    with pytest.raises(SubAddressError) as _:
        meta = res.get_account_by_number('ABC_not_exist')

    # Update
    res.register_account_number('ABC', {'hello':'world'})
    meta = res.get_account_by_number('ABC')
    assert meta == {'hello':'world'}

def test_subaddress(base):
    db, res = base

    # Raises if account does not exist
    with pytest.raises(SubAddressError) as _:
        sub = res.get_new_subaddress_for_account('ABC')
    
    # Get two new subaddesses, they are unlinkable
    res.register_account_number('ABC', {'hello':'world'})
    sub1 = res.get_new_subaddress_for_account('ABC', [ 'scope1' ])
    sub2 = res.get_new_subaddress_for_account('ABC', [ 'scope2' ])
    sub3 = res.get_new_subaddress_for_account('ABC', [ 'scope2' ])
    assert sub1 != sub2
    assert sub2 != sub3

    # Resolve a subaddress
    acc0, scope1 = res.resolve_subaddress_to_account(sub1)
    assert acc0 == 'ABC'
    assert scope1 == [ 'scope1' ]

    # Raises if subaddress does not exist
    with pytest.raises(SubAddressError) as _:
        acc0, scope1 = res.resolve_subaddress_to_account('NOTEXIST')

def test_stableid(base):
    db, res = base

    # account does not exist
    context = ('OtherVASPAddr_ABC', )
    with pytest.raises(SubAddressError) as _:
        res.get_stable_id_for_account('NOTEXIST', period_id = 10, context=context)
    
    res.register_account_number('ABC', {'hello':'world'})

    id1 = res.get_stable_id_for_account('ABC', period_id = 10, context=context)
    id1p = res.get_stable_id_for_account('ABC', period_id = 10, context=context)
    id2 = res.get_stable_id_for_account('ABC', period_id = 11, context=context)

    assert id1 == id1p
    assert id1 != id2

    # stable ID for same period but different context is different
    context2 = ('OtherVASPAddr_XYZ', )
    id1xyz = res.get_stable_id_for_account('ABC', period_id = 10, context=context2)
    assert id1 != id1xyz

def test_iter(base):
    db, res = base
    
    # Make many subaddresses
    res.register_account_number('ABC', {'hello':'world'})
    sub1 = res.get_new_subaddress_for_account('ABC', [ 'scope1' ])
    sub2 = res.get_new_subaddress_for_account('ABC', [ 'scope2' ])
    sub3 = res.get_new_subaddress_for_account('ABC', [ 'scope3' ])

    # Check they are all returned.
    L = list(res.get_all_subaddress_by_account('ABC'))
    assert L == [sub3, sub2, sub1]
