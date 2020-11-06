# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

from jwcrypto import jwk, jws
from jwcrypto.common import base64url_encode, base64url_decode
import json
from ..crypto import ComplianceKey, OffChainInvalidSignature
import pytest

def test_init():
    pass

def test_example_sign_verify():
    from jwcrypto.common import json_encode

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
    jwstoken.add_signature(
        key,
        alg=None,
        protected=json_encode({"alg": "EdDSA"}),
        header=json_encode({"kid": key.thumbprint()}))
    sig = jwstoken.serialize(compact=True)
    print('Signature:', sig)

    # Verify a message
    verifier = jws.JWS()
    verifier.deserialize(sig)
    verifier.verify(key)  # , alg='EdDSA')
    payload2 = verifier.payload

    # Verify a message -- pub only
    verifier_pub = jws.JWS()
    verifier_pub.deserialize(sig)
    verifier_pub.verify(key_pub)  #, alg='EdDSA')
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


async def test_sign_verif_correct():
    key = ComplianceKey.generate()
    sig = await key.sign_message(payload = 'Hello World!')
    raw = await key.verify_message(sig)
    assert raw == "Hello World!"

async def test_sign_verif_compatibility():
    key = ComplianceKey.generate()
    print("JWK key:", key.export_full())

    # LIP-1 Messages

    payload = 'Hello World!'
    verif = base64url_decode(json.loads(key.export_pub())["x"])
    verif_hex = verif.hex()
    print('Verification key (hex, bytes): "%s" (len=%s)' % (verif_hex, len(verif_hex)))
    print('Payload message (str, utf8): "%s" (len=%s)' % (payload, len(payload)))

    sig = await key.sign_message(payload = payload)
    print('Signature (str, utf8): "%s" (len=%s)' % (sig, len(sig)))
    raw = await key.verify_message(sig)
    assert raw == payload

    ## Dual attestation
    reference_id = 'SAMPLE_REF_ID'
    libra_address_bytes = b'SAMPLEREFADDRESS'
    amount = 5_123_456

    from libra import txnmetadata, utils
    address = utils.account_address(bytes.hex(libra_address_bytes))
    _, dual_attestation_msg = txnmetadata.travel_rule(reference_id, address, amount)
    print(f'Metadata: reference_id (utf8) = "{reference_id}" libra_address_bytes (hex, bytes) = "{libra_address_bytes.hex()}" amount (u64) = "{amount}"')
    print(f'LCS Metadata (bytes, hex): "{dual_attestation_msg.hex()}" (len={len(dual_attestation_msg.hex())})')

    signature = key.sign_dual_attestation_data(reference_id, libra_address_bytes, amount)
    print(f'Compliance Signature (bytes, hex): "{signature.hex()}" (len={len(signature.hex())})')

async def test_sign_verif_incorrect():
    key = ComplianceKey.generate()
    sig = await key.sign_message(payload = 'Hello World!')

    key2 = ComplianceKey.generate()
    with pytest.raises(OffChainInvalidSignature):
        sig = await key2.verify_message(sig)
        assert sig == 'Hello World!'


def test_dual_attestation_signing_and_verifying():
    key = ComplianceKey.generate()
    addr_bytes = bytes.fromhex("f72589b71ff4f8d139674a3f7369c69b")
    reference_id = "reference_id"
    amount = 5_555_555
    dual_attestation_signature = key.sign_dual_attestation_data(
        reference_id,
        addr_bytes,
        amount,
    )

    key.verify_dual_attestation_data(
        reference_id,
        addr_bytes,
        amount,
        dual_attestation_signature,
    )

    # Invalid length
    with pytest.raises(Exception):
        dual_attestation_signature = key.sign_dual_attestation_data(
            reference_id,
            addr_bytes+b'A',
            amount
        )

    # Invalid amount
    with pytest.raises(OffChainInvalidSignature):
        key.verify_dual_attestation_data(reference_id, addr_bytes, amount-1, dual_attestation_signature)

    # Invalid address
    with pytest.raises(OffChainInvalidSignature):
        key.verify_dual_attestation_data(
            reference_id,
            bytes.fromhex("fffffffffffffffff9674a3f7369c69b"),
            amount,
            dual_attestation_signature
        )
