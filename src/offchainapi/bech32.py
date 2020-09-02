# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

# Bech32 implementation for Libra human readable addresses based on
# Bitcoin's segwit python lib https://github.com/fiatjaf/bech32 modified to support the
# requirements of Libra (sub)address and versioning specs.
#
# MIT Licence of the above here: https://github.com/fiatjaf/bech32/blob/master/LICENSE
# commit: 48b6fe15ccdbf2741a9410df277bd95f9086e18a

"""Reference implementation for Bech32 encoding of Libra Blockchain addresses and sub-addresses."""

from typing import Iterable, List, Optional, Tuple


LBR = "lbr"  # lbr for mainnet
TLB = "tlb"  # tlb for testnet

# Bech32 constants
__BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
__BECH32_SEPARATOR = "1"
__BECH32_CHECKSUM_CHAR_SIZE = 6

# LIBRA constants
__LIBRA_HRP = [LBR, TLB]
__LIBRA_ADDRESS_SIZE = 16  # in bytes
__LIBRA_SUBADDRESS_SIZE = 8  # in bytes (for V1)
__LIBRA_BECH32_VERSION = 1
__LIBRA_BECH32_SIZE = 50  # in characters

LIBRA_ZERO_SUBADDRESS = b"\0" * __LIBRA_SUBADDRESS_SIZE


class Bech32Error(Exception):
    """ Represents an error when creating a Libra address. """

    pass


def bech32_address_encode(
    hrp: str, address_bytes: bytes, subaddress_bytes: Optional[bytes]
) -> str:
    """Encode a Libra address (and sub-address if provided)."""
    # check correct hrp
    if hrp not in __LIBRA_HRP:
        raise Bech32Error(
            f"Wrong Libra address Bech32 human readable part (prefix): expected "
            f"{__LIBRA_HRP[0]} for mainnet or {__LIBRA_HRP[1]} for testnet, but {hrp} was provided"
        )

    # only accept correct size for Libra address
    if len(address_bytes) != __LIBRA_ADDRESS_SIZE:
        raise Bech32Error(
            f"Address size should be {__LIBRA_ADDRESS_SIZE}, but got: {len(address_bytes)}"
        )

    # only accept correct size for Libra subaddress (if set)
    if (
        subaddress_bytes is not None
        and len(subaddress_bytes) != __LIBRA_SUBADDRESS_SIZE
    ):
        raise Bech32Error(
            f"Subaddress size should be {__LIBRA_SUBADDRESS_SIZE}, but got: {len(subaddress_bytes)}"
        )

    encoding_version = __LIBRA_BECH32_VERSION

    # if subaddress has not been provided it's set to 8 zero bytes.
    subaddress_final_bytes = (
        subaddress_bytes if subaddress_bytes is not None else LIBRA_ZERO_SUBADDRESS
    )
    total_bytes = address_bytes + subaddress_final_bytes

    five_bit_data = __convertbits(total_bytes, 8, 5, True)
    # check base conversion
    if five_bit_data is None:
        raise Bech32Error("Error converting bytes to base32")
    return __bech32_encode(hrp, [encoding_version] + five_bit_data)


def bech32_address_decode(bech32: str, expected_hrp: Optional[str] = None) -> Tuple[str, int, bytes, bytes]:
    """Validate a Bech32 Libra address Bech32 string, and split between version, address and sub-address."""
    len_bech32 = len(bech32)
    # check expected length
    if len_bech32 != __LIBRA_BECH32_SIZE:
        raise Bech32Error(
            f"Bech32 size should be {__LIBRA_BECH32_SIZE}, but it is: {len_bech32}"
        )

    # do not allow mixed case per BIP 171
    if bech32 != bech32.lower() and bech32 != bech32.upper():
        raise Bech32Error(f"Mixed case Bech32 addresses are not allowed, got: {bech32}")
    bech32 = bech32.lower()

    # check hrp
    hrp = bech32[:3]
    if hrp not in __LIBRA_HRP:
        raise Bech32Error(
            f'Wrong Libra address Bech32 human readable part (prefix): expected "{LBR}" '
            f'for mainnet or "{TLB}" for testnet but got "{hrp}"'
        )

    if expected_hrp and expected_hrp != hrp:
        raise Bech32Error(
            f'Wrong Libra address Bech32 human readable part (prefix): requested "{expected_hrp}" but '
            f'got "{hrp}"'
        )

    # check separator
    if bech32[3] != __BECH32_SEPARATOR:
        raise Bech32Error(f"Non-expected Bech32 separator: {bech32[3]}")

    # check characters after separator in Bech32 alphabet
    if not all(x in __BECH32_CHARSET for x in bech32[4:]):
        raise Bech32Error(f"Invalid Bech32 characters detected: {bech32}")
    hrp = bech32[:3]

    # version is defined by the index of the Bech32 character after separator
    address_version = __BECH32_CHARSET.find(bech32[4])
    # check valid version
    if address_version != __LIBRA_BECH32_VERSION:
        raise Bech32Error(
            f"Version mismatch. Expected {__LIBRA_BECH32_VERSION}, "
            f"but received {address_version}"
        )

    # we've already checked that all characters are in the correct alphabet,
    # thus, this will always succeed
    data = [__BECH32_CHARSET.find(x) for x in bech32[5:]]

    # check Bech32 checksum
    if not __bech32_verify_checksum(hrp, [address_version] + data):
        raise Bech32Error(f"Bech32 checksum validation failed: {bech32}")

    decoded_data = __convertbits(data[:-__BECH32_CHECKSUM_CHAR_SIZE], 5, 8, False)
    # check base conversion
    if decoded_data is None:
        raise Bech32Error("Error converting bytes from base32")

    length_data = len(decoded_data)
    # extra check about the expected output (sub)address size in bytes
    if length_data != __LIBRA_ADDRESS_SIZE + __LIBRA_SUBADDRESS_SIZE:
        raise Bech32Error(
            f"Expected {__LIBRA_ADDRESS_SIZE + __LIBRA_SUBADDRESS_SIZE} bytes after decoding, but got: {length_data}"
        )

    return (
        hrp,
        address_version,
        bytes(decoded_data[:__LIBRA_ADDRESS_SIZE]),
        bytes(decoded_data[-__LIBRA_SUBADDRESS_SIZE:]),
    )


def __bech32_polymod(values: Iterable[int]) -> int:
    """Internal function that computes the Bech32 checksum."""
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def __bech32_hrp_expand(hrp: str) -> List[int]:
    """Expand the HRP into values for checksum computation."""
    # TODO We could pre-compute expanded Libra's HRP.
    # __LIBRA_MAINNET_HRP_EXPANDED = [3, 3, 3, 0, 12, 2, 18]
    # __LIBRA_TESTNET_HRP_EXPANDED = [3, 3, 3, 0, 20, 12, 2]
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def __bech32_verify_checksum(hrp: str, data: Iterable[int]) -> bool:
    """Verify a checksum given HRP and converted data characters."""
    return __bech32_polymod(__bech32_hrp_expand(hrp) + list(data)) == 1


def __bech32_create_checksum(hrp: str, data: Iterable[int]) -> List[int]:
    """Compute the checksum values given HRP and data."""
    values = __bech32_hrp_expand(hrp) + list(data)
    polymod = __bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def __bech32_encode(hrp: str, data: Iterable[int]) -> str:
    """Compute a Bech32 string given HRP and data values."""
    combined = list(data) + __bech32_create_checksum(hrp, data)
    return hrp + __BECH32_SEPARATOR + "".join([__BECH32_CHARSET[d] for d in combined])


def __convertbits(
    data: Iterable[int], from_bits: int, to_bits: int, pad: bool
) -> Optional[List[int]]:
    """General power-of-2 base conversion."""
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None
    return ret
