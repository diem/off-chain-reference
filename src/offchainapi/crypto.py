# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from jwcrypto import jwk, jws
import json


class OffChainInvalidSignature(Exception):
    pass


class ComplianceKey:

    def __init__(self, key):
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
        key = jwk.JWK(**json.loads(data))
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
            raise OffChainInvalidSignature()

    def thumbprint(self):
        return self._key.thumbprint()

    def __eq__(self, other):
        if not isinstance(other, ComplianceKey):
            return False
        return self._key.has_private == other._key.has_private \
            and self._key.thumbprint() == other._key.thumbprint()
