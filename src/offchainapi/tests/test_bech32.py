# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

import pytest

from ..bech32 import Bech32Error, bech32_address_decode, bech32_address_encode, LBR, TLB

def test_bech32_valid_address() -> None:
    some_address = bytes(bytearray.fromhex("f72589b71ff4f8d139674a3f7369c69b"))
    some_sub_address = bytes(bytearray.fromhex("cf64428bdeb62af2"))
    none_sub_address = None
    zero_sub_address = b"\0\0\0\0\0\0\0\0"

    # do not set a subaddress
    bech32_libra_address = bech32_address_encode(
        LBR, some_address, none_sub_address
    )
    assert bech32_libra_address == "lbr1p7ujcndcl7nudzwt8fglhx6wxnvqqqqqqqqqqqqqflf8ma"

    version, address, subaddress = bech32_address_decode(LBR, bech32_libra_address)
    assert version == 1
    assert address == some_address
    assert subaddress == zero_sub_address

    # set subaddress to all zeros and check we get the same as if we never added one
    bech32_libra_address = bech32_address_encode(
        LBR, some_address, zero_sub_address
    )
    assert bech32_libra_address == "lbr1p7ujcndcl7nudzwt8fglhx6wxnvqqqqqqqqqqqqqflf8ma"

    # set some subaddress
    some_sub_address = bytes(bytearray.fromhex("cf64428bdeb62af2"))

    bech32_libra_address = bech32_address_encode(
        LBR, some_address, some_sub_address
    )
    assert bech32_libra_address == "lbr1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t"

    version, address, subaddress = bech32_address_decode(LBR, bech32_libra_address)
    assert version == 1
    assert address == some_address
    assert subaddress == some_sub_address

    # decode uppercase bech32 addresses
    version, address, subaddress = bech32_address_decode(
        LBR, bech32_libra_address.upper()
    )
    assert version == 1
    assert address == some_address
    assert subaddress == some_sub_address

    # testnet address
    some_sub_address = bytes(bytearray.fromhex("cf64428bdeb62af2"))

    bech32_libra_address = bech32_address_encode(
        TLB, some_address, some_sub_address
    )
    assert bech32_libra_address == "tlb1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usugm707"

    version, address, subaddress = bech32_address_decode(TLB, bech32_libra_address)
    assert version == 1
    assert address == some_address
    assert subaddress == some_sub_address


def test_bech32_invalid_address() -> None:

    # fail to decode invalid hrp
    invalid_hrp_bech32_address = (
        "btc1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t"
    )

    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, invalid_hrp_bech32_address)

    # fail to decode invalid "expected" hrp
    with pytest.raises(Bech32Error):
        bech32_address_decode(
            "BTC", "lbr1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t"
        )

    # fail to decode invalid version
    invalid_version_bech32_address = (
        "lbr1q7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t"  # v = 0
    )
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, invalid_version_bech32_address)

    # fail to decode due to checksum error
    invalid_checksum_bech32_address = "lbr1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72p"  # change last char from t to p
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, invalid_checksum_bech32_address)

    # fail to decode mixed case per BIP 173
    mixedcase_bech32_address = (
        "LbR1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5P72T"  # some uppercase
    )
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, mixedcase_bech32_address)

    # fail to decode shorter payload
    short_bech32_address = "lbr1p7ujcndcl7nudzwt8fglhx6wxnvqqqqqqqqqqqqelu3xv"  # sample 23 bytes encoded
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, short_bech32_address)

    # fail to decode larger payload
    large_bech32_address = "lbr1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4us4g3ysw8a"  # sample 25 bytes encoded
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, large_bech32_address)

    # fail to decode invalid separator
    invalid_separator_bech32_address = (
        "lbr2p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t"  # separator = 2
    )
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, invalid_separator_bech32_address)

    # fail to decode invalid character
    invalid_char_bech32_address = (
        "lbr1pbujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t"  # add b char
    )
    with pytest.raises(Bech32Error):
        bech32_address_decode(LBR, invalid_char_bech32_address)
