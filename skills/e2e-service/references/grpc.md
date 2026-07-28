# gRPC boundary coverage

## Boundary evidence

- Unary: single request, single response calls
- Client stream: client sends multiple requests, server returns single response
- Server stream: client sends single request, server returns multiple responses
- Bidirectional: both client and server stream multiple messages
- Metadata: request and response metadata headers
- Messages: request and response message schemas
- Status: gRPC status codes and details
- Details: error details and custom detail messages
- Deadline: call deadline and timeout configuration
- Cancellation: client and server cancellation signals
- Trailers: response trailers and metadata

Record each confirmed supported external boundary with its method signature,
message types, and expected status. Label evidence `live-observed`,
`source-derived`, or `spec-derived`.

## Repository-native adapter

Use the repository's built-in gRPC client when available (e.g. Node.js `@grpc`
built-in or HTTP/2 framing). Create a minimal adapter only when no native client
exists. The adapter must:

- Accept `method`, `id`, and message parameters.
- Return `{ status, details, trailers }` or protocol-equivalent structured
  results.
- Never install vendor dependencies.
- Respect timeouts and connection limits.

## Plan

1. Resolve the gRPC method and message types for the selected journey.
2. Confirm the protobuf service definition exists in the application source.
3. Identify the expected response message and status code.
4. Record the boundary evidence with the appropriate label.
5. Create a check record with the method and expected outcome.

## Generate

1. Generate verification code using the repository-native gRPC client.
2. Encode the method, message, deadline, and expected status.
3. Include response message and trailer assertions.
4. Mark the output `generated-unverified`.

## Verify

1. Execute the generated gRPC call against the authorized target.
2. Assert the response status, message, and trailers match the expected schema.
3. Record the execution evidence with protocol `grpc`, the client type, and
   the target tier.
4. Classify any failure using the failure classification taxonomy.

## Evidence

Execution evidence for gRPC checks includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `method` | string | gRPC method name |
| `status` | object | Status code and details |
| `message` | object | Response message |
| `trailers` | object | Response trailers |
| `duration_ms` | number | Call duration |

Production verification is read-only. No write or update methods are allowed
during production verification.

## Failure distinctions

- `product-defect`: The response status, message, or trailers diverge from the
  confirmed supported external boundary.
- `test-defect`: The expected message schema or status code is incorrect.
- `environment`: The gRPC endpoint is unreachable, the connection times out, or
  the server returns infrastructure errors.
- `inconclusive`: The response is partial or malformed and it is unclear
  whether the product or the client adapter caused the failure.
- `authorization-required`: The endpoint returns `UNAUTHENTICATED` or
  `PERMISSION_DENIED` and the required authorization is not recorded.

## Safety

- Production gRPC verification is read-only.
- Never invoke write or update methods during production verification.
- Never consume unrelated messages or execute empty-timeout success claims.
- Never use arbitrary sleeps; use bounded deadline loops for async operations.
