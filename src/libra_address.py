import base64

# Helper classes
class LibraAddressError(Exception):
    pass

class LibraAddress:
    """ An interface that abstracts a Libra Address and bit manipulations on it."""

    def __init__(self, encoded_address):
        try:
            if type(encoded_address) == str:
                self.encoded_address = encoded_address
            else:
                self.encoded_address = encoded_address.decode('ascii')
            self.decoded_address = base64.b64decode(self.encoded_address)
        except:
            raise LibraAddressError()
    
    def plain(self):
        return self.encoded_address

    @classmethod
    def encode_to_Libra_address(cls, raw_bytes):
        return LibraAddress(base64.b64encode(raw_bytes))

    def last_bit(self):
        return self.decoded_address[-1] & 1

    def greater_than_or_equal(self, other):
        return self.decoded_address >= other.decoded_address

    def equal(self, other):
        return isinstance(other, LibraAddress) \
            and self.decoded_address == other.decoded_address
    
    def __eq__(self, other):
        return self.equal(other)
    
    def __hash__(self):
        return self.decoded_address.__hash__()
