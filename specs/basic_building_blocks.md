# Basic Off-Chain Building Blocks

* **HTTP end-points**: Each VASP exposes an HTTPS POST end point at
`https://hostname:port/<protocol_version>/<localVASPAddress>/<RemoteVASPAddress>/command`. It receives `CommandRequestObject`s in the POST body, and responds with `CommandResponseObject`s in the HTTP response (See [Travel Rule Data Exchange](travel_rule_data_exchange.md) for more details. Single command requests-responses are supported (HTTP1.0) but also pipelined request-responses are supported (HTTP1.1). The version for the Off-chain protocol is the string `v1`. All HTTP requests and responses contain a header `X-Request-ID` with a unique ID for the request, used for tracking requests and debugging. Responses must have the same string in the `X-Request-ID` header value as the requests they correspond to.
* **Serialization to JSON**: All structures transmitted, nested within `CommandRequestObject` and `CommandResponseObject` are valid JSON serialized objects and can be parsed and serialized using standard JSON libraries. The content type for requests and responses is set to `Content-type: application/json; charset=utf-8` indicating all content is JSON encoded.
* **JWS Signatures**: all transmitted structures are signed by the sending party using the JWS Signature standard (with the Ed25519 / EdDSA ciphersuite, and `compact` encoding). This ensures all information and meta-data about payments is authenticated and cannot be repudiated.

Next: [Travel Rule Data Exchange](travel_rule_data_exchange.md)

Previous: [Overview](off_chain_protocol.md)
