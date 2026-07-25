# GraphQL boundary coverage

## Boundary evidence

- Query: GraphQL query operations and fields
- Mutation: GraphQL mutation operations (production prohibited)
- Subscription: GraphQL subscription operations and topics
- Variables: input variables and validation
- Operation name: named operations and fragments
- Fragments: shared fragment definitions and reuse
- Data: response data structure and types
- Errors: GraphQL error objects, extensions, and error paths
- Transport: HTTP or WebSocket transport layers
- Schema: schema validation and introspection results
- Operation validation: operation-level validation results

Record each confirmed supported external boundary with its query, expected
data structure, and error format. Label evidence `live-observed`,
`source-derived`, or `spec-derived`.

## Repository-native adapter

Use the repository's built-in GraphQL client when available (e.g. `node-fetch`
with GraphQL endpoint, or inline `fetch` with `POST`). Create a minimal adapter
only when no native client exists. The adapter must:

- Accept `operation`, `variables`, and `operationName` parameters.
- Return `{ data, errors }` or protocol-equivalent structured results.
- Never install vendor dependencies.
- Respect timeouts and connection limits.

## Plan

1. Resolve the GraphQL operation and variables for the selected journey.
2. Confirm the schema and operation exist in the application source.
3. Identify the expected data structure and error format.
4. Record the boundary evidence with the appropriate label.
5. Create a check record with the operation and expected outcome.

## Generate

1. Generate verification code using the repository-native GraphQL client.
2. Encode the operation, variables, and expected data structure.
3. Include error assertion for the `errors` array when expected.
4. Mark the output `generated-unverified`.

## Verify

1. Execute the generated GraphQL operation against the authorized target.
2. Assert the response data matches the expected structure and values.
3. Assert GraphQL error objects are present or absent as expected.
4. Record the execution evidence with protocol `graphql`, the client type, and
   the target tier.
5. Classify any failure using the failure classification taxonomy.

## Evidence

Execution evidence for GraphQL checks includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `operation` | string | GraphQL operation name or query |
| `variables` | object | Input variables |
| `data` | object | Response data |
| `errors` | array | GraphQL error objects |
| `duration_ms` | number | Request duration |

Production verification is read-only. No mutation operations are allowed during
production verification.

## Failure distinctions

- `product-defect`: The response data or error objects diverge from the
  confirmed supported external boundary.
- `test-defect`: The expected data structure or error assertion is incorrect.
- `environment`: The GraphQL endpoint is unreachable, the connection times out,
  or the server returns infrastructure errors.
- `inconclusive`: The response is partial or malformed and it is unclear
  whether the product or the client adapter caused the failure.
- `authorization-required`: The endpoint returns unauthorized and the required
  authorization is not recorded.

## Safety

- Production GraphQL verification is read-only.
- Never execute mutation operations during production verification.
- Never consume unrelated messages or execute empty-timeout success claims.
- Never use arbitrary sleeps; use bounded deadline loops for async operations.
