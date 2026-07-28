# HTTP boundary coverage

## Boundary evidence

- Method: GET, POST, PUT, PATCH, DELETE
- Path: URL path patterns and route handlers
- Query: query parameters and validation
- Headers: request and response headers, content negotiation
- Content negotiation: Accept and Content-Type headers
- Body: request and response body schemas
- Auth refs: authorization headers, tokens, and session references
- Status: HTTP status codes and error classes
- Response headers: cache control, CORS, and content headers
- Response body: response schema validation
- Contracts: OpenAPI, RAML, or API specification references
- Redirects: 3xx redirect chains and location headers
- Errors: error response formats and error codes

Record each confirmed supported external boundary with its method, path,
expected status, and response contract. Label evidence `live-observed`,
`source-derived`, or `spec-derived`.

## Repository-native adapter

Use the repository's built-in HTTP client when available (e.g. `node:http`,
`node:https`, `fetch`). Create a minimal adapter only when no native client
exists. The adapter must:

- Accept `method`, `path`, `headers`, `body`, and `query` parameters.
- Return `{ status, headers, body }` or protocol-equivalent structured results.
- Never install vendor dependencies.
- Respect timeouts and connection limits.

## Plan

1. Resolve the HTTP method and path for the selected journey.
2. Confirm the route handler exists in the application source.
3. Identify the expected status code and response body schema.
4. Record the boundary evidence with the appropriate label.
5. Create a check record with the method, path, and expected outcome.

## Generate

1. Generate verification code using the repository-native HTTP client.
2. Encode the method, path, query, headers, body, and expected status.
3. Include response header and body assertions.
4. Mark the output `generated-unverified`.

## Verify

1. Execute the generated HTTP request against the authorized target.
2. Assert the response status, headers, and body match the expected contract.
3. Record the execution evidence with protocol `http`, the client type, and
   the target tier.
4. Classify any failure using the failure classification taxonomy.

## Evidence

Execution evidence for HTTP checks includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `method` | string | HTTP method used |
| `path` | string | Request path |
| `status` | number | Response status code |
| `headers` | object | Response headers |
| `body` | object or string | Response body |
| `duration_ms` | number | Request duration |

Production verification is read-only. No POST, PUT, PATCH, or DELETE mutations
are allowed during production verification.

## Failure distinctions

- `product-defect`: The response status, headers, or body diverge from the
  confirmed supported external boundary.
- `test-defect`: The expected status, headers, or body assertion is incorrect.
- `environment`: The target is unreachable, the connection times out, or the
  server returns infrastructure errors (502, 503, 504).
- `inconclusive`: The response is partial or malformed and it is unclear
  whether the product or the client adapter caused the failure.
- `authorization-required`: The endpoint returns 401 or 403 and the required
  authorization is not recorded.

## Safety

- Production HTTP verification is read-only.
- Never mutate data via POST, PUT, PATCH, or DELETE during production
  verification.
- Never consume unrelated messages or execute empty-timeout success claims.
- Never use arbitrary sleeps; use bounded deadline loops for async operations.
