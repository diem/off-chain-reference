from binascii import unhexlify, hexlify


# Helper classes
class LibraAddressError(Exception):
    ''' Represents an error when creating a Libra address. '''
    pass


class LibraAddress:

    def __init__(self, encoded_address):
        """ An interface that abstracts a Libra Address
            and bit manipulations on it.

        Args:
            encoded_address (str or bytes): String or byte representation of
                                            a Libra Address.

        Raises:
            LibraAddressError: If the provided encoded address cannot be parsed
                               to a Libra Address.
        """
        try:
            if type(encoded_address) == str:
                self.encoded_address = encoded_address
            else:
                assert type(encoded_address) == bytes
                self.encoded_address = encoded_address.decode('ascii')
            self.decoded_address = unhexlify(self.encoded_address)
        except Exception:
            raise LibraAddressError()

    def as_str(self):
        ''' Returns a string representation of the LibraAddress.

            Returns:
                str: String representation of the LibraAddress.
        '''
        return self.encoded_address

    @classmethod
    def encode_to_Libra_address(cls, raw_bytes):
        """ Make a Libra address from bytes.

        Args:
            raw_bytes (bytes): The bytes from which to create a Libra address.

        Returns:
            LibraAddress: The Libra address.
        """
        return LibraAddress(hexlify(raw_bytes))

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
