# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from jwcrypto.common import base64url_encode
from cryptography.exceptions import InvalidSignature
from libra import txnmetadata, utils
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

    async def sign_message(self, payload):
        signer = jws.JWS(payload.encode('utf-8'))
        signer.add_signature(self._key, alg='EdDSA')
        sig = signer.serialize(compact=True)
        return sig

    async def verify_message(self, signature):
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

    def sign_dual_attestation_data(self, reference_id, libra_address_bytes, amount):
        """ Sign the dual attestation message using the compliance key
            Params:
               reference_id (str)
               libra_address_bytes (bytes): the 16 bytes of sender Libra Blockchain address
               amount (int): a unsigned integer of transaction amount

            Returns ed25519 signature bytes
        """
        address = utils.account_address(bytes.hex(libra_address_bytes))
        _, dual_attestation_msg = txnmetadata.travel_rule(reference_id, address, amount)

        return self.get_private().sign(dual_attestation_msg)

    def verify_dual_attestation_data(
        self,
        reference_id,
        libra_address_bytes,
        amount,
        signature
    ):
        """
        Verify the dual attestation message given reference id, sender libra address (bytes),
        payment amount and signature
            Params:
               reference_id (str)
               libra_address_bytes (bytes): the 16 bytes of sender Libra Blockchain address
               amount (int): a unsigned integer of transaction amount
               signature (bytes): ed25519 signature bytes
            Returns none when verification succeeds.
            Raises OffChainInvalidSignature when verification fails.
        """
        address = utils.account_address(bytes.hex(libra_address_bytes))
        _, dual_attestation_msg = txnmetadata.travel_rule(reference_id, address, amount)
        try:
            self.get_public().verify(signature, dual_attestation_msg)
        except InvalidSignature:
            raise OffChainInvalidSignature(
                reference_id,
                libra_address_bytes,
                amount,
                signature
            )
