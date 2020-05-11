from binascii import unhexlify, hexlify
from bech32 import encode, decode

# Helper classes
class LibraAddressError(Exception):
    ''' Represents an error when creating a Libra address. '''
    pass


class LibraAddress:

    hrp = 'm'
    version = 1

    def __init__(self, encoded_address):
        """ An interface that abstracts a Libra Address
            and bit manipulations on it.

        Args:
            encoded_address (str or bytes): Representation of a Libra address in bech32.

        Raises:
            LibraAddressError: If the provided encoded address cannot be parsed
                               to a Libra Address.
        """

        self.encoded_address = encoded_address
        ver, self.decoded_address = decode(self.hrp, self.encoded_address)
        if self.decoded_address is None or ver != self.version:
            raise LibraAddressError(
                f'Incorrect version or bech32 encoding: "{encoded_address}"')
        self.decoded_address = bytes(self.decoded_address)

    def as_str(self):
        ''' Returns a string representation of the LibraAddress.

            Returns:
                str: String representation of the LibraAddress.
        '''
        return str(self.encoded_address)

    @classmethod
    def encode(cls, raw_bytes):
        """ Make a Libra address from bytes.

        Args:
            raw_bytes (bytes): The bytes from which to create a Libra address.

        Returns:
            LibraAddress: The Libra address.
        """
        enc = encode(cls.hrp, cls.version, raw_bytes)
        if enc is None:
            raise LibraAddressError(
                f'Cannot convert to LibraAddress: "{raw_bytes}"')
        addr = cls(enc)
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
            and self.decoded_address == other.decoded_address

    def __eq__(self, other):
        return self.equal(other)

    def __hash__(self):
        return self.decoded_address.__hash__()


class LibraSubAddress(LibraAddress):
    ''' Represents a Libra subaddress. '''
    hrp = 's'
    version = 1
