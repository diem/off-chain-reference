# LIP-1 Signature Specifications and Test Vectors


## Reference specification for JWS signatures used

All `CommandRequestObject` and `CommandResponseObject` messages exchanged on the off-chain channel between two services must be signed using a specific configuration of the JWS scheme.

The JSON Web Signature (JWS) scheme is specified in RFC 7515. Messages in the off-chain channel are signed with a specific configuration:

* The JWS Signature Scheme used is `EdDSA` as specified in RFC 8032 (EdDSA) and RFC 8037 (Elliptic Curve signatures for JWS).
* The JWS Serialization scheme used is `Compact` as specified in Section 3.1 of RFC 7515 (https://tools.ietf.org/html/rfc7515#section-3.1)
* The Protected Header should contain the JSON object `{"alg": "EdDSA"}`, indicating the signature algorithm used.
* The Unprotected header must be empty

### A Test Vector illustrating signature generation and verification is provided:

JWK key:

    {"crv":"Ed25519","d":"txWBp6D61bBT-80v8hn-mwOgh6p1oTQIhDFW55AKvmk","kty":"OKP","x":"xJsn7MmQWtElKzP8B6TtBkzTPv3JRh2lwnnShpsVFTg"}

Corresponding verification key (hex, bytes), as the 32 bytes stored on the Libra blockchain.

    "c49b27ecc9905ad1252b33fc07a4ed064cd33efdc9461da5c279d2869b151538" (len=64)

Sample payload message to sign (str, utf8):

    "Hello World!" (len=12)

Valid JWS Compact Signature (str, utf8):

    "eyJhbGciOiJFZERTQSJ9.SGVsbG8gV29ybGQh.AkVQBFMkSNklZDT0eOK7OOsz4gPsjfjgJXZujH5TGGYgfBulTS2kdJkwJX7UpLcfKoqGNE5G_WYBwDV8X01fDg" (len=124)

## Reference specification for valid `recipient_signature` fields

Payments between services on chain may require a recipient signature using the services compliance key. The verification key for each service is stored on chain in their account.

* The algorithm used to generate the signature is `EdDSA` as specified in RFC 8032.
* The signature is over the Libra Canonical Serialization of a Metadata structure including `reference_id` (bytes, ASCII), a 16-byes Libra on-chain `address`, the payment `amount` (u64), and a domain separator `DOMAIN_SEPARATOR` (with value in ascii `@@$$LIBRA_ATTEST$$@@`).
* The output is a hex encoded 64-byte string representing the raw byte representation of the EdDSA signature.

JWK key:

    {"crv":"Ed25519","d":"txWBp6D61bBT-80v8hn-mwOgh6p1oTQIhDFW55AKvmk","kty":"OKP","x":"xJsn7MmQWtElKzP8B6TtBkzTPv3JRh2lwnnShpsVFTg"}

The data that contributes to the compliance recipient signature.

    reference_id (ascii) = "SAMPLE_REF_ID" (hex "53414d504c455f5245465f4944")
    libra_address_bytes (hex, bytes) = "53414d504c4552454641444452455353"
    amount (u64) = 5123456 (Hex: "802d4e0000000000")

Metadata serialized using  LCS (including encoding of `reference_id`) + `address` + `amount` + `DOMAIN_SEPARATOR` (bytes, hex):

    "0200010d53414d504c455f5245465f494453414d504c4552454641444452455353802d4e0000000000404024244c494252415f41545445535424244040" (len=122)

The above serialized string represents:

        "0200"                                      - Metadata type and version (2, constant)
        010d"                                       - uleb128 encoded reference_id length (variable)
        "53414d504c455f5245465f4944"                - Bytes of reference_id (variable)
        "53414d504c4552454641444452455353"          - Bytes of Libra address (16)
        "802d4e0000000000"                          - Bytes of amount (8)
        "404024244c494252415f41545445535424244040"  - DOMAIN_SEPARATOR (20)

For information on uleb128 encoding of a u32 length integer see: https://en.wikipedia.org/wiki/LEB128

Compliance Signature output (bytes, hex):

    "04d3527cc29880c93ea453d161797b87d4a1e3b7f65b48449696883aa39dc968160ae77c9abeea741384a6b1afe64d58f7e3722c212dd3d7f8ae83518812f60f" (len=128)
