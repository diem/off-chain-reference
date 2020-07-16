# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from binascii import unhexlify, hexlify
from .bech32 import (
    bech32_address_encode,
    bech32_address_decode,
    Bech32Error,
    LBR,
    TLB,
    __LIBRA_HRP
)


class LibraAddressError(Exception):
    ''' Represents an error when creating a LibraAddress. '''
    pass


class LibraAddress:
    """
    A representation of address used in this protocol that consists of three parts:
    1. onchain_address: a 16 bytes address on chain, for example a VASP address
    2. subaddress: a subaddress in bytes
    3. hrp: Human Readable Part, indicating the network version:
        * "lbr" for Mainnet addresses
        * "tlb" for Testnet addresses
    """

    @classmethod
    def from_bytes(cls, onchain_address_bytes, subaddress_bytes=None, hrp=LBR):
        """ Return a LibraAddress given onchain address in bytes, subaddress
        in bytes (optional), and hrp (Human Readable Part)
        """
        try:
            encoded_address = bech32_address_encode(
                hrp,
                onchain_address_bytes,
                subaddress_bytes
            )
        except Bech32Error as e:
            raise LibraAddressError(
                f"Can't create LibraAddress from "
                f"onchain_address_bytes: {onchain_address_bytes}, "
                f"subaddress_bytes: {subaddress_bytes}, "
                f"hrp: {hrp}, got Bech32Error: {e}"
            )
        return cls(encoded_address, onchain_address_bytes, subaddress_bytes, hrp)

    @classmethod
    def from_hex(cls, onchain_address_hex, subaddress_hex=None, hrp=LBR):
        """ Return a LibraAddress given onchain address in hex, subaddress
        in hex (optional), and hrp (Human Readable Part)
        """
        onchain_address_bytes = bytes.fromhex(onchain_address_hex)
        subaddress_bytes = bytes.fromhex(subaddress_hex) if subaddress_hex else None
        return cls.from_bytes(onchain_address_bytes, subaddress_bytes, hrp)

    @classmethod
    def from_encoded_str(cls, encoded_str):
        """ Return a LibraAddress given an bech32 encoded str """
        try:
            hrp, _version, onchain_address_bytes, subaddress_bytes = bech32_address_decode(encoded_str)
        except Bech32Error as e:
            raise LibraAddressError(
                f"Can't create LibraAddress from encoded str {encoded_str}, "
                f"got Bech32Error: {e}"
            )
        # If subaddress is absent, subaddress_bytes is a list of 0
        subaddrss_ints = list(subaddress_bytes)
        none_zero = [i for i in subaddrss_ints if i]
        if none_zero:
            return cls(encoded_str, onchain_address_bytes, subaddress_bytes, hrp)
        return cls(encoded_str, onchain_address_bytes, None, hrp)


    def __init__(self, encoded_address_bytes, onchain_address_bytes, subaddress_bytes, hrp):
        """ DO NOT CALL THIS DIRECTLY!! use factory mtheods instead."""

        self.encoded_address_bytes = encoded_address_bytes
        self.onchain_address_bytes = onchain_address_bytes
        self.subaddress_bytes = subaddress_bytes
        self.hrp = hrp

    def __repr__(self):
        return (
            f"LibraAddress with onchain_address_bytes: {self.onchain_address_bytes}, "
            f"subaddress_bytes: {self.subaddress_bytes}, hrp: {self.hrp}"
        )

    def as_str(self):
        return self.encoded_address_bytes

    def last_bit(self):
        """ Get the last bit of the decoded onchain address.
        """
        return self.onchain_address_bytes[-1] & 1

    def greater_than_or_equal(self, other):
        """ Compare two Libra addresses in term of their on-chain part

        Args:
            other (LibraAddress): The Libra address to compare against.

        Returns:
            bool: If the current address is greater (or equal) than other.
        """
        return self.onchain_address_bytes >= other.onchain_address_bytes

    def equal(self, other):
        """ Define equality for LibraAddresses.

        Args:
            other (LibraAddress): An other Libra address.

        Returns:
            bool: Whether this address equals the other address.
        """
        return isinstance(other, LibraAddress) \
            and self.onchain_address_bytes == other.onchain_address_bytes \
            and self.subaddress_bytes == other.subaddress_bytes \
            and self.hrp == other.hrp

    def __eq__(self, other):
        return self.equal(other)

    def __hash__(self):
        return self.encoded_address_bytes.__hash__()

    def get_onchain(self):
        """ Return a LibraAddress representing only the onchain address
            without any subaddress information. """
        if self.subaddress_bytes is None:
            return self
        return LibraAddress.from_bytes(self.onchain_address_bytes, None, self.hrp)

    def get_onchain_encoded_str(self):
        """ Return an encoded str representation of LibraAddress containing
        only the onchain address """
        return self.get_onchain().as_str()

    def get_onchain_address_hex(self):
        """ Return onchain address in hex """
        return bytes.hex(self.onchain_address_bytes)

    def get_subaddress_hex(self):
        """ Return subaddress in hex, if not None"""
        if self.subaddress_bytes:
            return bytes.hex(self.subaddress_bytes)
        return None
