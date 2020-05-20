from binascii import unhexlify, hexlify
from bech32 import bech32_encode, bech32_decode, convertbits

# Helper classes
class LibraAddressError(Exception):
    ''' Represents an error when creating a Libra address. '''
    pass


class LibraAddress:

    def __init__(self, encoded_address, hrp='lbr'):
        """ An interface that abstracts a Libra Address
            and bit manipulations on it.

        Args:
            encoded_address (str or bytes): Representation of a Libra address in bech32.

        Raises:
            LibraAddressError: If the provided encoded address cannot be parsed
                               to a Libra Address.
        """

        assert hrp in ('lbr', 'tlb')
        self.hrp = hrp
        self.encoded_address = encoded_address

        # Do basic bech32 decoding
        ver, self.decoded_address = decode(self.hrp, self.encoded_address)
        if self.decoded_address is None:
            raise LibraAddressError(
                f'Incorrect version or bech32 encoding: "{encoded_address}"')

        # Set the version
        self.version = ver
        if self.version == 0:
            # This is a libra network address without subaddress.
            if len(self.decoded_address) != 16:
                raise LibraAddressError(
                    f'Libra network address must be 16'
                    f' bytes, found: "{len(self.decoded_address)}"')
            self.decoded_address = bytes(self.decoded_address)
            self.decoded_sub_address = None

        elif self.version == 1:
            # This is a libra network sub-address
            if len(self.decoded_address) < 16 + 8:
                raise LibraAddressError(
                    f'Libra network sub-address must be > 16+8'
                    f' bytes, found: "{len(self.decoded_address)}"')

            addr_bytes = bytes(self.decoded_address)
            self.decoded_address = addr_bytes[:16]
            self.decoded_sub_address = addr_bytes[16:]
        else:
            raise LibraAddressError(
                f'Unknown Address version number: "{ver}"')


    def as_str(self):
        ''' Returns a string representation of the LibraAddress.

            Returns:
                str: String representation of the LibraAddress.
        '''
        return str(self.encoded_address)

    @classmethod
    def encode(cls, raw_bytes_address, raw_bytes_subaddr=None, hrp='lbr'):
        """ Make a Libra address from bytes.

        Args:
            raw_bytes (bytes): The bytes from which to create a Libra address.

        Returns:
            LibraAddress: The Libra address.
        """
        if len(raw_bytes_address) != 16:
            raise LibraAddressError(f'Libra address must be 16 bytes, not: {len(raw_bytes_address)}')
        if not (raw_bytes_subaddr is None or len(raw_bytes_subaddr) >= 8):
            raise LibraAddressError(f'Invalid subaddress: {raw_bytes_subaddr}')

        # Check id we encode on-chain or subaddress
        if raw_bytes_subaddr is None:
            version = 0
            raw_bytes = raw_bytes_address
        else:
            version = 1
            raw_bytes = raw_bytes_address + raw_bytes_subaddr

        # Encode using bech32
        enc = encode(hrp, version, raw_bytes)
        if enc is None:
            raise LibraAddressError(
                f'Cannot convert to LibraAddress: "{raw_bytes}"')

        addr = cls(enc, hrp)
        return addr

    def last_bit(self):
        """ Get the last bit of the Libra address.

        Returns:
            bool: The last bit of the Libra address.
        """
        return self.decoded_address[-1] & 1

    def greater_than_or_equal(self, other):
        """ Compare two Libra addresses.

        Args:
            other (LibraAddress): The Libra address to compare against.

        Returns:
            bool: If the current address is greater (or equal) than other.
        """
        return self.decoded_address >= other.decoded_address

    def equal(self, other):
        """ Defines equality for Libra addresses.

        Args:
            other (LibraAddress): An other Libra address.

        Returns:
            bool: Whether this address equals the other address.
        """
        return isinstance(other, LibraAddress) \
            and self.decoded_address == other.decoded_address \
            and self.decoded_sub_address == other.decoded_sub_address

    def __eq__(self, other):
        return self.equal(other)

    def __hash__(self):
        return self.encoded_address.__hash__()

    def onchain(self):
        ''' Returns a Libra Address representing only the onchain address
            without any subaddress information. '''
        if self.decoded_sub_address is None:
            return self
        return LibraAddress.encode(self.decoded_address)

    def get_onchain_bytes(self):
        ''' Returns the decoded 16 bytes onchain address of the VASP.'''
        return self.decoded_address

    def get_subaddress_bytes(self):
        ''' Returns the decoded 8+ bytes of the subaddress at the VASP.'''
        return self.decoded_sub_address

# Adapted from : https://github.com/fiatjaf/bech32/blob/master/bech32/__init__.py
# MIT Licence here: https://github.com/fiatjaf/bech32/blob/master/LICENSE
# Copyright (c) 2017 Pieter Wuille

def encode(hrp, witver, witprog):
    """Encode a segwit address."""
    five_bit_witprog = convertbits(witprog, 8, 5)
    if five_bit_witprog is None:
        return None
    ret = bech32_encode(hrp, [witver] + five_bit_witprog)
    decoded = decode(hrp, ret)
    if decoded == (None, None):
        return None
    return ret

def decode(hrp, addr):
    """Decode a segwit address."""
    hrpgot, data = bech32_decode(addr)
    if hrpgot != hrp:
        return (None, None)
    assert data is not None
    decoded = convertbits(data[1:], 5, 8, False)
    return (data[0], decoded)
