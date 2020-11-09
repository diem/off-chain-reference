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

    {"crv":"Ed25519","d":"vLtWeB7kt7fcMPlk01GhGmpWYTHYqnGRZUUN72AT1K4","kty":"OKP","x":"vUfj56-5Teu9guEKt9QQqIW1idtJE4YoVirC7IVyYSk"}

Corresponding verification key (hex, bytes), as the 32 bytes stored on the Libra blockchain.

    "bd47e3e7afb94debbd82e10ab7d410a885b589db49138628562ac2ec85726129" (len=64)

Sample payload message to sign (str, utf8):

    "Sample signed payload." (len=22)

Valid JWS Compact Signature (str, utf8):

    "eyJhbGciOiJFZERTQSJ9.U2FtcGxlIHNpZ25lZCBwYXlsb2FkLg.dZvbycl2Jkl3H7NmQzL6P0_lDEW42s9FrZ8z-hXkLqYyxNq8yOlDjlP9wh3wyop5MU2sIOYvay-laBmpdW6OBQ" (len=138)

## Reference specification for valid `recipient_signature` fields

Payments between services on chain may require a recipient signature using the services compliance key. The verification key for each service is stored on chain in their account.

* The algorithm used to generate the signature is `EdDSA` as specified in RFC 8032.
* The signature is over the Libra Canonical Serialization of a Metadata structure including `reference_id` (bytes, ASCII), a 16-byes Libra on-chain `address`, the payment `amount` (u64), and a domain separator `DOMAIN_SEPARATOR` (with value in ascii `@@$$LIBRA_ATTEST$$@@`).
* The output is a hex encoded 64-byte string representing the raw byte representation of the EdDSA signature.

JWK key:

    {"crv":"Ed25519","d":"vLtWeB7kt7fcMPlk01GhGmpWYTHYqnGRZUUN72AT1K4","kty":"OKP","x":"vUfj56-5Teu9guEKt9QQqIW1idtJE4YoVirC7IVyYSk"}

The data that contributes to the compliance recipient signature.

    reference_id (ascii): "lbr1pg9q5zs2pg9q5zs2pg9q5zs2pgyqqqqqqqqqqqqqqspa3m_5b8403c986f53fe072301fe950d030cb" (in hex "6c6272 ... 306362")

    libra_address_bytes (hex, bytes) = "53414d504c4552454641444452455353"

    amount (u64) = "5123456" (Hex "802d4e0000000000")

Metadata is serialized using  LCS (including encoding of `reference_id`) and appended to the fixed length byte sequences representing `address`, `amount`, and `DOMAIN_SEPARATOR`. For example the byte sequence that is signed for the transaction data above is (bytes, hex):

    "020001536c62723170673971357a733270673971357a733270673971357a73327067797171717171717171717171717171737061336d5f356238343033633938366635336665303732333031666539353064303330636253414d504c4552454641444452455353802d4e0000000000404024244c494252415f41545445535424244040" (len=262)

The above serialized byte array represents:

        "0200"                                      - Metadata type and version (2 bytes, constant value)
        "0153"                                      - uleb128 encoded reference_id length (variable)◊
        "6c6272 ... 306362"                         - Bytes of reference_id (variable)
        "53414d504c4552454641444452455353"          - Bytes of Libra address (16 bytes)
        "802d4e0000000000"                          - Bytes of amount (8 bytes)
        "404024244c494252415f41545445535424244040"  - DOMAIN_SEPARATOR (20 bytes)

For information on uleb128 encoding of a u32 length integer see: https://en.wikipedia.org/wiki/LEB128

A valid compliance Signature output is (bytes, hex):

    "4c988922f95f0697e83783383ce81cfc5e1ac06e6201ad7223c5abf38b839532ebb24ad46d0bde14ee30f2139580163670bfb4b06d730603bc19759d326e6602" (len=128)
