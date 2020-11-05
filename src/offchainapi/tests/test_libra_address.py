# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

import pytest
from uuid import uuid4

from ..bech32 import Bech32Error, bech32_address_encode, LBR, TLB
from ..libra_address import LibraAddress, LibraAddressError


def test_onchain_address_only_OK():
    onchain_address_bytes = uuid4().bytes  # 16 bytes

    libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes)
    assert libra_addr.onchain_address_bytes == onchain_address_bytes
    assert libra_addr.subaddress_bytes == None
    expected_encoded_str = bech32_address_encode(
        LBR,
        onchain_address_bytes,
        None
    )
    assert libra_addr.encoded_address_str == expected_encoded_str
    assert libra_addr.as_str() == expected_encoded_str
    assert libra_addr.get_onchain_address_hex() == bytes.hex(onchain_address_bytes)
    assert libra_addr.get_subaddress_hex() == None


def test_non_none_subaddress_OK():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    subaddr_bytes = uuid4().bytes[8:]  # 8 bytes (v1)

    libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes, subaddr_bytes)
    assert libra_addr.onchain_address_bytes == onchain_address_bytes
    assert libra_addr.subaddress_bytes == subaddr_bytes
    expected_encoded_str = bech32_address_encode(
        LBR,
        onchain_address_bytes,
        subaddr_bytes
    )
    assert libra_addr.encoded_address_str == expected_encoded_str
    assert libra_addr.as_str() == expected_encoded_str
    assert libra_addr.get_onchain_address_hex() == bytes.hex(onchain_address_bytes)
    assert libra_addr.get_subaddress_hex() == bytes.hex(subaddr_bytes)


def test_invalid_onchain_address_length():
    onchain_address_bytes = uuid4().bytes[:10]  # 10 bytes
    with pytest.raises(LibraAddressError) as excinfo:
        libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes)
    assert "Bech32Error" in str(excinfo.value)


def test_invalid_subaddress_length():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    subaddr_bytes = uuid4().bytes[:4]  # 4 bytes, invalid
    with pytest.raises(LibraAddressError) as excinfo:
        libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes, subaddr_bytes)
    assert "Bech32Error" in str(excinfo.value)


def test_from_bytes():
    onchain_address_hex = uuid4().hex
    subaddress_hex = uuid4().hex[16:]
    libra_addr = LibraAddress.from_hex(LBR, onchain_address_hex, subaddress_hex)
    assert libra_addr.onchain_address_bytes == bytes.fromhex(onchain_address_hex)
    assert libra_addr.subaddress_bytes == bytes.fromhex(subaddress_hex)

    libra_addr = LibraAddress.from_hex(LBR, onchain_address_hex, None)
    assert libra_addr.onchain_address_bytes == bytes.fromhex(onchain_address_hex)
    assert libra_addr.subaddress_bytes == None


def test_from_encoded_str():
    onchain_address_bytes = uuid4().bytes
    subaddress_bytes = uuid4().bytes[8:]
    libra_addr_one = LibraAddress.from_bytes(TLB, onchain_address_bytes, subaddress_bytes)
    libra_addr_two = LibraAddress.from_encoded_str(libra_addr_one.encoded_address_str)
    assert libra_addr_one == libra_addr_two
    assert libra_addr_two.hrp == TLB
    assert libra_addr_two.onchain_address_bytes == onchain_address_bytes
    assert libra_addr_two.subaddress_bytes == subaddress_bytes

    libra_addr_three = LibraAddress.from_bytes(LBR, onchain_address_bytes, None)
    libra_addr_four = LibraAddress.from_encoded_str(libra_addr_three.encoded_address_str)
    assert libra_addr_three == libra_addr_four
    assert libra_addr_four.hrp == LBR
    assert libra_addr_four.onchain_address_bytes == onchain_address_bytes
    assert libra_addr_four.subaddress_bytes == None


def test_invalid_hrp():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    with pytest.raises(LibraAddressError) as excinfo:
        libra_addr = LibraAddress.from_bytes("haha", onchain_address_bytes, None)
    assert "Bech32Error" in str(excinfo.value)


def test_last_bit():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    subaddr_bytes = uuid4().bytes[8:]  # 8 bytes (v1)
    libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes, subaddr_bytes)
    expected_last_bit = onchain_address_bytes[-1] & 1

    assert libra_addr.last_bit() == expected_last_bit


def test_GE():
    onchain_address_bytes_one = uuid4().bytes  # 16 bytes
    subaddr_bytes_one = uuid4().bytes[8:]  # 8 bytes (v1)
    libra_addr_one = LibraAddress.from_bytes(LBR, onchain_address_bytes_one, subaddr_bytes_one)

    onchain_address_bytes_two = uuid4().bytes  # 16 bytes
    subaddr_bytes_two = uuid4().bytes[8:]  # 8 bytes (v1)
    libra_addr_two = LibraAddress.from_bytes(LBR, onchain_address_bytes_two, subaddr_bytes_two)

    if onchain_address_bytes_one >= onchain_address_bytes_two:
        assert libra_addr_one.greater_than_or_equal(libra_addr_two)
    else:
        assert libra_addr_two.greater_than_or_equal(libra_addr_one)


def test_equal():
    onchain_address_bytes_list = [uuid4().bytes for _ in range(1)]
    subaddress_bytes_list = [uuid4().bytes[8:] for _ in range(1)] + [None]
    hrp_list = [LBR, TLB]

    libra_addr_list_one = [
        LibraAddress.from_bytes(hrp, onchain, sub)
        for onchain in onchain_address_bytes_list
        for sub in subaddress_bytes_list
        for hrp in hrp_list
    ]

    libra_addr_list_two = [
        LibraAddress.from_bytes(hrp, onchain, sub)
        for onchain in onchain_address_bytes_list
        for sub in subaddress_bytes_list
        for hrp in hrp_list
    ]

    for i, vi in enumerate(libra_addr_list_one):
        for j, vj in enumerate(libra_addr_list_two):
            if i == j:
                assert vi == vj
            else:
                assert vi != vj


def test_get_onchain():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    subaddr_bytes = uuid4().bytes[8:]  # 8 bytes (v1)

    libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes, subaddr_bytes)
    onchain_only = libra_addr.get_onchain()
    assert onchain_only == LibraAddress.from_bytes(LBR, onchain_address_bytes)
    assert onchain_only.get_onchain == onchain_only


def test_get_onchain():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    subaddr_bytes = uuid4().bytes[8:]  # 8 bytes (v1)

    libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes, subaddr_bytes)
    onchain_only = libra_addr.get_onchain()
    assert onchain_only == LibraAddress.from_bytes(LBR, onchain_address_bytes)
    assert onchain_only.get_onchain() == onchain_only


def test_last_bit():
    onchain_address_bytes = uuid4().bytes  # 16 bytes
    subaddr_bytes = uuid4().bytes[8:]  # 8 bytes (v1)
    libra_addr = LibraAddress.from_bytes(LBR, onchain_address_bytes, subaddr_bytes)
    expected_last_bit = onchain_address_bytes[-1] & 1

    assert libra_addr.last_bit() == expected_last_bit


def test_GE():
    onchain_address_bytes_one = uuid4().bytes  # 16 bytes
    subaddr_bytes_one = uuid4().bytes[8:]  # 8 bytes (v1)
    libra_addr_one = LibraAddress.from_bytes(LBR, onchain_address_bytes_one, subaddr_bytes_one)

    onchain_address_bytes_two = uuid4().bytes  # 16 bytes
    subaddr_bytes_two = uuid4().bytes[8:]  # 8 bytes (v1)
    libra_addr_two = LibraAddress.from_bytes(LBR, onchain_address_bytes_two, subaddr_bytes_two)

    if onchain_address_bytes_one >= onchain_address_bytes_two:
        assert libra_addr_one.greater_than_or_equal(libra_addr_two)
