from jwcrypto import jwk, jws
import json
from ..crypto import ComplianceKey, OffChainInvalidSignature
import pytest

def test_init():
    pass

def test_example_sign_verify():
    # Generate and export keys
    key = jwk.JWK.generate(kty='OKP', crv='Ed25519')
    pub_data = key.export_to_pem(private_key=False, password=None)
    print('--- KEY / SIGN / VERIFY TEST ---')

    # Export public
    pub = key.export_public()
    print(pub)
    key_pub = jwk.JWK(**json.loads(pub))

    # Sign a message
    payload = "My Integrity protected message"
    jwstoken = jws.JWS(payload.encode('utf-8'))
    jwstoken.add_signature(key, alg='EdDSA')
    sig = jwstoken.serialize(compact=True)
    print(sig)

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
