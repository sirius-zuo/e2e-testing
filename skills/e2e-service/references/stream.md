# Stream boundary coverage

## Boundary evidence

- Append-publish: event appending and publishing patterns
- Read-subscribe: event reading and subscription patterns
- Key-partition: partition keys and ordering guarantees
- Order: event ordering within and across partitions
- Cursor-offset: cursor position and offset tracking
- Replay: event replay and position restoration
- Correlation: correlation IDs and event tracing
- Bounded observation: maximum observation time before timeout

Record each confirmed supported external boundary with its channel, key
partition, cursor policy, and ordering guarantees. Label evidence
`live-observed`, `source-derived`, or `spec-derived`.

## Repository-native adapter

Use the repository's built-in stream client when available (e.g. Node.js
built-in TCP or event sourcing library). Create a minimal adapter only when no
native client exists. The adapter must:

- Accept `channel`, `event`, and `correlationId` parameters.
- Return `{ cursorCommitted, partition, order, event }` or protocol-equivalent
  structured results.
- Never install vendor dependencies.
- Respect timeouts and connection limits.

## Plan

1. Resolve the stream channel and append-read pattern.
2. Confirm the stream configuration exists in the application source.
3. Identify the key partition and cursor policy.
4. Record the boundary evidence with the appropriate label.
5. Create a check record with the channel and expected outcome.

## Generate

1. Generate verification code using the repository-native stream client.
2. Encode the append event, key partition, and expected read.
3. Include cursor and ordering assertions.
4. Mark the output `generated-unverified`.

## Verify

1. Execute the generated stream operation against the authorized target.
2. Assert the event is appended and read with the expected key and cursor.
3. Assert the ordering and correlation match the expected policy.
4. Record the execution evidence with protocol `stream`, the client type, and
   the target tier.
5. Classify any failure using the failure classification taxonomy.

## Evidence

Execution evidence for stream checks includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `channel` | string | Stream channel name |
| `event` | object | Published or read event |
| `cursorCommitted` | boolean | Whether the cursor was committed |
| `partition` | string | Event partition key |
| `order` | number | Event order within partition |
| `duration_ms` | number | Operation duration |

Production verification is read-only. No event publication, cursor commits, or
offset updates are allowed during production verification.

## Failure distinctions

- `product-defect`: The event, cursor, partition, or ordering diverges from the
  confirmed supported external boundary.
- `test-defect`: The expected channel, event, or cursor policy is incorrect.
- `environment`: The stream endpoint is unreachable, the connection times out,
  or the server returns infrastructure errors.
- `inconclusive`: The event is partial or malformed and it is unclear whether
  the product or the client adapter caused the failure.
- `authorization-required`: The stream endpoint returns unauthorized and the
  required authorization is not recorded.

## Safety

- Production stream verification is read-only.
- Never publish events or commit cursors during production verification.
- Never consume unrelated messages or execute empty-timeout success claims.
- Never use arbitrary sleeps; use bounded deadline loops for async operations.
