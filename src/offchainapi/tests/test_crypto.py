# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from jwcrypto import jwk, jws
import json
from ..crypto import ComplianceKey, OffChainInvalidSignature, \
    encode_ref_id_data
import pytest

def test_init():
    pass

def test_example_sign_verify():
    # Generate and export keys
    key = jwk.JWK.generate(kty='OKP', crv='Ed25519')
    pub_data = key.export_to_pem(private_key=False, password=None)
    print('--- KEY / SIGN / VERIFY TEST ---')

    # Export full key:
    full = key.export_private()
    print('K.Pair:', full)

    # Export public
    pub = key.export_public()
    print('Public:', pub)
    key_pub = jwk.JWK(**json.loads(pub))

    # Sign a message
    payload = "My Integrity protected message"
    print('Payload:', payload)
    jwstoken = jws.JWS(payload.encode('utf-8'))
    jwstoken.add_signature(key, alg='EdDSA')
    sig = jwstoken.serialize(compact=True)
    print('Signature:', sig)

    # Verify a message
    verifier = jws.JWS()
    verifier.deserialize(sig)
    verifier.verify(key, alg='EdDSA')
    payload2 = verifier.payload

    # Verify a message -- pub only
    verifier_pub = jws.JWS()
    verifier_pub.deserialize(sig)
    verifier_pub.verify(key_pub, alg='EdDSA')
    payload3 = verifier_pub.payload

    assert payload.encode('utf-8') == payload3

def test_compl_gen():
    key = ComplianceKey.generate()
    key2 = ComplianceKey.generate()

    # identity works
    assert key == key
    assert key2 == key2

    assert not key == key2

def test_export_import():
    key = ComplianceKey.generate()

    # Export / Import Pub
    pub = key.export_pub()
    assert isinstance(pub, str)
    key_pub = ComplianceKey.from_str(pub)
    assert key.thumbprint() == key_pub.thumbprint()
    assert not key_pub._key.has_private
    assert key != key_pub

    # Export / Import full
    full = key.export_full()
    assert isinstance(full, str)
    key_full = ComplianceKey.from_str(full)
    assert key.thumbprint() == key_full.thumbprint()
    assert key_full._key.has_private
    assert key == key_full


def test_sign_verif_correct():
    key = ComplianceKey.generate()
    sig = key.sign_message(payload = 'Hello World!')
    assert key.verify_message(sig) == 'Hello World!'


def test_sign_verif_incorrect():
    key = ComplianceKey.generate()
    sig = key.sign_message(payload = 'Hello World!')

    key2 = ComplianceKey.generate()
    with pytest.raises(OffChainInvalidSignature):
        assert key2.verify_message(sig) == 'Hello World!'


def test_encode_recipient():

    META_DATA_BYTES = [0x61, 0x1e, 0x0,  0x0,  0x0, 0x0,  0x0, 0x0]
    LIBRA_ADDRESS = [
            0x65, 0xe9, 0xe9, 0xd3, 0x6, 0x3b, 0xbb,  0x14,
            0x31, 0xb3, 0xb6, 0x55, 0xc8, 0x1e, 0x2b, 0x7b,
        ]
    VALUE_BYTES = [0x40, 0x42, 0xf,  0x0,  0x0,  0x0,  0x0,  0x0, ]
    SEPARATOR = [
            0x40, 0x40, 0x24, 0x24, 0x4c, 0x49, 0x42, 0x52,
            0x41, 0x5f, 0x41, 0x54, 0x54, 0x45, 0x53, 0x54,
            0x24, 0x24, 0x40, 0x40]

    MSG = META_DATA_BYTES + LIBRA_ADDRESS + VALUE_BYTES + SEPARATOR

    SIG = [ 0x2b, 0x37, 0xea, 0xe2, 0xea, 0xb9, 0x4f,  0x1,
            0x8e, 0x82, 0x39,  0x1, 0xd8, 0x6e, 0x99, 0x23,
            0xaa, 0x4d, 0xbb, 0x31, 0x29, 0xc2, 0xc3, 0x86,
            0x8a, 0x5f, 0x27, 0xc5, 0x96, 0xd4, 0xa4, 0x99,
            0x3e, 0x36, 0xd2, 0xc6, 0xfd, 0x93, 0xa6, 0xe8,
            0xe8, 0x8a, 0x7a, 0x88, 0x22, 0xb8, 0x94, 0xb4,
            0xaa, 0xc3, 0xa3, 0x28,  0xc, 0x26, 0xdf, 0x1d,
            0x48, 0x60, 0x70, 0x4f, 0x71, 0xc6, 0xa4,  0x2 ]

    PUB = [ 0xe1, 0x4c, 0x7d, 0xdb, 0x77, 0x13, 0xc9, 0xc7,
            0x31, 0x5f, 0x33, 0x73, 0x93, 0xf4, 0x26, 0x1d,
            0x17, 0x13, 0xa5, 0xf8, 0xc6, 0xc6, 0xe1, 0x4c,
            0x49, 0x86, 0xe6, 0x16, 0x46, 0x2,  0x51, 0xe6 ]

    msg_b = bytes(MSG)
    sig_b = bytes(SIG)
    pub_b = bytes(PUB)

    assert len(MSG) == 52
    assert len(sig_b) == 64
    assert len(pub_b) == 32

    # First try verification
    from cryptography.hazmat.primitives.asymmetric.ed25519 \
        import Ed25519PublicKey

    pub = Ed25519PublicKey.from_public_bytes(pub_b)
    pub.verify(sig_b, msg_b)

    # Check the encoding is the same
    enc = encode_ref_id_data(
        bytes([0x61, 0x1e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]),
        bytes([0x65, 0xe9, 0xe9, 0xd3, 0x6, 0x3b, 0xbb, 0x14,
               0x31, 0xb3, 0xb6, 0x55, 0xc8, 0x1e, 0x2b, 0x7b]),
        1_000_000
    )
    assert enc == msg_b

    # Now check the same using our own ComplianceKey abstraction
    ck = ComplianceKey.from_pub_bytes(pub_b)
    ck.verify_ref_id(
        bytes([0x61, 0x1e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]),
        bytes([0x65, 0xe9, 0xe9, 0xd3, 0x6, 0x3b, 0xbb, 0x14,
               0x31, 0xb3, 0xb6, 0x55, 0xc8, 0x1e, 0x2b, 0x7b]),
        1_000_000,
        sig_b.hex()
    )


def test_example_ref_id_sign_verify():
    # Generate and export keys
    key = ComplianceKey.generate()

    meta = bytes([0x61, 0x1e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0])
    addr = bytes([0x65, 0xe9, 0xe9, 0xd3, 0x6, 0x3b, 0xbb, 0x14,
                  0x31, 0xb3, 0xb6, 0x55, 0xc8, 0x1e, 0x2b, 0x7b])
    value = 1_000_000

    # Invalid length
    with pytest.raises(Exception):
        sign = key.sign_ref_id(meta, addr+b'A', value)

    sign = key.sign_ref_id(meta, addr, value)
    key.verify_ref_id(meta, addr, value, sign)


    # Invalid value
    with pytest.raises(OffChainInvalidSignature):
        key.verify_ref_id(meta, addr, value-1, sign)

    # Invalid address
    addr_bad = bytes([0x00]) + addr[1:]
    with pytest.raises(OffChainInvalidSignature):
        key.verify_ref_id(meta, addr_bad, value, sign)
