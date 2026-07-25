# WebSocket boundary coverage

## Boundary evidence

- Handshake: WebSocket handshake request and response headers
- Subprotocol: negotiated subprotocol and version
- Ordered send-receive: message ordering guarantees
- Message contract: message schema and field validation
- Correlation: correlation IDs and message tracing
- Close: close codes and reasons
- Bounded idle-response timeout: maximum idle time before timeout

Record each confirmed supported external boundary with its handshake
requirements, subprotocol, message contract, and timeout configuration. Label
evidence `live-observed`, `source-derived`, or `spec-derived`.

## Repository-native adapter

Use the repository's built-in WebSocket client when available (e.g. Node.js
`ws` or `node:http` with upgrade). Create a minimal adapter only when no native
client exists. The adapter must:

- Accept `url`, `subprotocols`, and `message` parameters.
- Return `{ messages, closeCode, closeReason }` or protocol-equivalent
  structured results.
- Never install vendor dependencies.
- Respect timeouts and connection limits.

## Plan

1. Resolve the WebSocket endpoint and handshake requirements.
2. Confirm the server supports the required subprotocol.
3. Identify the message contract and expected responses.
4. Record the boundary evidence with the appropriate label.
5. Create a check record with the endpoint and expected outcome.

## Generate

1. Generate verification code using the repository-native WebSocket client.
2. Encode the handshake, subprotocol, message, and expected responses.
3. Include close code and reason assertions.
4. Mark the output `generated-unverified`.

## Verify

1. Execute the generated WebSocket connection against the authorized target.
2. Assert the handshake succeeds with the expected subprotocol.
3. Send the message and assert the response matches the expected contract.
4. Assert the close code and reason match the expected values.
5. Record the execution evidence with protocol `websocket`, the client type,
   and the target tier.
6. Classify any failure using the failure classification taxonomy.

## Evidence

Execution evidence for WebSocket checks includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `handshakeStatus` | number | HTTP status code from handshake |
| `subprotocol` | string | Negotiated subprotocol |
| `messages` | array | Received messages |
| `closeCode` | number | WebSocket close code |
| `closeReason` | string | WebSocket close reason |
| `duration_ms` | number | Connection duration |

Production verification is read-only. No command messages are allowed during
production verification.

## Failure distinctions

- `product-defect`: The handshake, message, or close response diverges from the
  confirmed supported external boundary.
- `test-defect`: The expected subprotocol, message, or close code is incorrect.
- `environment`: The WebSocket endpoint is unreachable, the handshake fails with
  infrastructure errors, or the connection times out.
- `inconclusive`: The message is partial or malformed and it is unclear whether
  the product or the client adapter caused the failure.
- `authorization-required`: The handshake returns unauthorized and the required
  authorization is not recorded.

## Safety

- Production WebSocket verification is read-only.
- Never send command or data messages during production verification.
- Never consume unrelated messages or execute empty-timeout success claims.
- Never use arbitrary sleeps; use bounded deadline loops for async operations.
