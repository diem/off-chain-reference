from jwcrypto import jwk, jws

def test_init():
    pass

def test_example_sign_verify():
    # Generate and export keys
    key = jwk.JWK.generate(kty='OKP', crv='Ed25519')
    pub_data = key.export_to_pem(private_key=False, password=None)
    print(pub_data)
    # pub = jwk.JWK.from_pem(pub_data)
    print(key.export_to_pem(private_key=True, password=None))

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
    payload2 = jwstoken.payload

    assert payload.encode('utf-8') == payload2
