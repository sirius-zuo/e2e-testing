# Queue boundary coverage

## Boundary evidence

- Publish-consume: message publishing and consumption patterns
- Destination: queue or topic name and configuration
- Attributes: message attributes and headers
- Correlation: correlation IDs and message tracing
- Ack-reject: message acknowledgement and rejection handling
- Redelivery: redelivery policies and dead-letter queues
- Delivery semantics: at-least-once, at-most-once, or exactly-once

Record each confirmed supported external boundary with its destination,
attributes, correlation pattern, and delivery semantics. Label evidence
`live-observed`, `source-derived`, or `spec-derived`.

## Repository-native adapter

Use the repository's built-in queue client when available (e.g. Node.js
built-in TCP or AMQP library). Create a minimal adapter only when no native
client exists. The adapter must:

- Accept `destination`, `message`, and `attributes` parameters.
- Return `{ acknowledged, redelivered, deliverySemantics }` or
  protocol-equivalent structured results.
- Never install vendor dependencies.
- Respect timeouts and connection limits.

## Plan

1. Resolve the queue destination and publish-consume pattern.
2. Confirm the queue configuration exists in the application source.
3. Identify the message attributes and delivery semantics.
4. Record the boundary evidence with the appropriate label.
5. Create a check record with the destination and expected outcome.

## Generate

1. Generate verification code using the repository-native queue client.
2. Encode the publish message, attributes, and expected delivery.
3. Include acknowledgement and redelivery assertions.
4. Mark the output `generated-unverified`.

## Verify

1. Execute the generated queue operation against the authorized target.
2. Assert the message is published and consumed with the expected attributes.
3. Assert the acknowledgement and redelivery status match the expected policy.
4. Record the execution evidence with protocol `queue`, the client type, and
   the target tier.
5. Classify any failure using the failure classification taxonomy.

## Evidence

Execution evidence for queue checks includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `destination` | string | Queue or topic name |
| `message` | object | Published message |
| `acknowledged` | boolean | Whether the message was acknowledged |
| `redelivered` | boolean | Whether the message was redelivered |
| `deliverySemantics` | string | Delivery semantics used |
| `duration_ms` | number | Operation duration |

Production verification is read-only. No message publication, acknowledgement,
or redelivery operations are allowed during production verification.

## Failure distinctions

- `product-defect`: The message attributes, acknowledgement, or delivery
  semantics diverge from the confirmed supported external boundary.
- `test-defect`: The expected destination, message, or delivery policy is
  incorrect.
- `environment`: The queue endpoint is unreachable, the connection times out,
  or the server returns infrastructure errors.
- `inconclusive`: The message is partial or malformed and it is unclear
  whether the product or the client adapter caused the failure.
- `authorization-required`: The queue endpoint returns unauthorized and the
  required authorization is not recorded.

## Safety

- Production queue verification is read-only.
- Never publish messages or acknowledge messages during production verification.
- Never consume unrelated messages or execute empty-timeout success claims.
- Never use arbitrary sleeps; use bounded deadline loops for async operations.
