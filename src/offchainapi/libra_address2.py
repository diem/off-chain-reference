# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from binascii import unhexlify, hexlify
# from bech32 import bech32_encode, bech32_decode, convertbits
from .bech32 import bech32_address_encode, Bech32Error, LBR, TLB

# Helper classes
class LibraAddressError(Exception):
    ''' Represents an error when creating a Libra address. '''
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
        try:
            encoded_address = bech32_address_encode(
                hrp,
                onchain_address_bytes,
                subaddress_bytes
            )
        except Bech32Error as e:
            raise LibraAddressError(f"Bech32Error: {e}")
        return cls(encoded_address, onchain_address_bytes, subaddress_bytes, hrp)

    @classmethod
    def from_hex(cls, onchain_address_hex, subaddress_hex=None, hrp=LBR):
        onchain_address_bytes = bytes.fromhex(onchain_address_hex)
        subaddress_bytes = bytes.fromhex(subaddress_hex) if subaddress_hex else None
        return cls.from_bytes(onchain_address_bytes, subaddress_bytes, hrp)

    def __init__(self, encoded_address_bytes, onchain_address_bytes, subaddress_bytes, hrp):
        """ DO NOT CALL THIS DIRECTLY!! use factory mtheods instead."""

        self.encoded_address_bytes = encoded_address_bytes
        self.onchain_address_bytes = onchain_address_bytes
        self.subaddress_bytes = subaddress_bytes
        self.hrp = hrp

    # FIXME what is this for?
    def as_str(self):
        ''' Returns a string representation of the LibraAddress.

            Returns:
                str: String representation of the LibraAddress.
        '''
        return str(self.encoded_address_bytes)

    def last_bit(self):
        """ Get the last bit of the decoded libra address.

        Returns:
            bool: The last bit of the decoded libra address.
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
        """ Defines equality for Libra addresses.

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
        ''' Returns a LibraAddress representing only the onchain address
            without any subaddress information. '''
        if self.subaddress_bytes is None:
            return self
        return LibraAddress.from_bytes(self.onchain_address_bytes, None, self.hrp)

    # FIXME? what for?
    def get_onchain_bytes(self):
        ''' Returns the decoded 16 bytes onchain address of the VASP.'''
        return self.onchain_address_bytes

    # FIXME? what for?
    def get_subaddress_bytes(self):
        ''' Returns the decoded bytes of the subaddress at the VASP
        if it is not None'''
        return self.subaddress_bytes
