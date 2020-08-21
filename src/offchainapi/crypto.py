# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from jwcrypto.common import base64url_encode
from cryptography.exceptions import InvalidSignature

from jwcrypto import jwk, jws
import json


class OffChainInvalidSignature(Exception):
    pass


class IncorrectInputException(Exception):
    pass



class ComplianceKey:

    def __init__(self, key):
        ''' Creates a compliance key from a JWK Ed25519 key. '''
        self._key = key

    def get_public(self):
        return self._key.get_op_key('verify')

    def get_private(self):
        return self._key.get_op_key('sign')

    @staticmethod
    def generate():
        ''' Generate an Ed25519 key pair for EdDSA '''
        key = jwk.JWK.generate(kty='OKP', crv='Ed25519')
        return ComplianceKey(key)

    @staticmethod
    def from_str(data):
        ''' Generate a compliance key from a JWK JSON string. '''
        key = jwk.JWK(**json.loads(data))
        return ComplianceKey(key)

    @staticmethod
    def from_pub_bytes(pub_key_data):
        ''' Generate a compliance public key (for verification) from
        32 bytes of Ed25519 key. '''
        key = jwk.JWK(
            kty='OKP',
            crv='Ed25519',
            x=base64url_encode(pub_key_data)
        )
        return ComplianceKey(key)

    @staticmethod
    def from_pem(filename, password=None):
        raise NotImplementedError
        #with open(filename, 'rb') as pemfile:
        #    return jwk.JWK.from_pem(pemfile.read(), password=password)

    def to_pem(self, filename, private_key=False, password=None):
        data = self._key.export_to_pem(
            private_key=private_key, password=password
        )
        with open(filename, 'wb') as pemfile:
            pemfile.write(data)

    def export_pub(self):
        return self._key.export_public()

    def export_full(self):
        return self._key.export_private()

    def sign_message(self, payload):
        signer = jws.JWS(payload.encode('utf-8'))
        signer.add_signature(self._key, alg='EdDSA')
        sig = signer.serialize(compact=True)
        return sig

    def verify_message(self, signature):
        try:
            verifier = jws.JWS()
            verifier.deserialize(signature)
            verifier.verify(self._key, alg='EdDSA')
            return verifier.payload.decode("utf-8")
        except jws.InvalidJWSSignature:
            raise OffChainInvalidSignature(signature, "Invalid Signature")
        except jws.InvalidJWSObject:
            raise OffChainInvalidSignature(signature, "Invalid Format")

    def thumbprint(self):
        return self._key.thumbprint()

    def __eq__(self, other):
        if not isinstance(other, ComplianceKey):
            return False
        return self._key.has_private == other._key.has_private \
            and self._key.thumbprint() == other._key.thumbprint()

    def sign_ref_id(self, reference_id_bytes, libra_address_bytes, value_u64):
        """ Sign the reference_id and associated data required for the recipient
            signature using the complance key.

            Params:
               reference_id_bytes (bytes): the bytes of the reference_id.
               libra_address_bytes (bytes): the 16 bytes of the  libra address
               value_u64 (int): a unsigned integer of the value.

            Returns the hex encoded string ed25519 signature (64 x 2 char).
        """

        msg_b = encode_ref_id_data(reference_id_bytes, libra_address_bytes, value_u64)
        priv = self._key._get_private_key()
        return priv.sign(msg_b).hex()

    def verify_ref_id(self, reference_id_bytes, libra_address_bytes, value_u64, signature):
        """ Verify the reference_id and  associated data sgnature from a recipient. Parameters
        are the same as for sign_ref_id, with the addition of the signature in hex format
        as returned by sign_ref_id. """
        msg_b = encode_ref_id_data(reference_id_bytes, libra_address_bytes, value_u64)
        pub = self._key._get_public_key()
        try:
            pub.verify(bytes.fromhex(signature), msg_b)
        except InvalidSignature:
            raise OffChainInvalidSignature(reference_id_bytes, libra_address_bytes, value_u64, signature)

def encode_ref_id_data(reference_id_bytes, libra_address_bytes, value_u64):
    if len(libra_address_bytes) != 16:
        raise IncorrectInputException('Libra Address raw format is 16 bytes.')

    message = b''
    message += reference_id_bytes
    message += libra_address_bytes
    message += value_u64.to_bytes(8, byteorder='little')

    domain_sep = b'@@$$LIBRA_ATTEST$$@@'
    message += domain_sep
    return message
