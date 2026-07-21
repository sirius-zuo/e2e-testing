# Failure classification

## Classify from evidence

Classify each selected test once per verification result. Preserve the original
failure before any bounded rerun. Evidence must include the selected test ID,
sanitized command and output, target context, manifest revision, relevant
trace/screenshot/log references, and the source, specification, or live evidence
used for diagnosis.

Choose exactly one mutually exclusive primary outcome. Assign a confidence from
`0.0` to `1.0`; only a `test-defect` at `0.80` or higher may enter repair. If two
outcomes remain credible, evidence conflicts, or confidence is below `0.80`, use
`inconclusive` and stop rather than repair.

| Primary outcome | Minimum evidence threshold | Required result |
| --- | --- | --- |
| `test-defect` | At least two aligned facts show a test-owned cause, such as a stale locator plus current UI/source evidence, while the intended expected outcome remains supported. Confidence >= `0.80`. | Record `repair-ready`, scoped evidence, and a bounded test-only repair opportunity. |
| `product-defect` | The test accurately expresses a supported expected outcome, and reproducible observed behavior conflicts with it; rule out a test-owned cause. Confidence >= `0.80`. | Record `handoff-required` and request `fix-product-defect`; do not repair application code. |
| `environment-failure` | Target, service, browser runtime, dependency, network, fixture, or infrastructure failure independently explains the result and is not an application behavior claim. Confidence >= `0.80`. | Preserve diagnostics and emit an environment capability handoff. |
| `requirements-conflict` | At least two traceable sources disagree about the intended behavior and neither has an authorized precedence. Confidence >= `0.80`. | Record `needs-clarification`; do not rewrite expectations. |
| `authorization-required` | A required target configuration, credential reference, or exact-action approval is absent before the blocked action. Confidence is `1.00` from the gate record. | Record `needs-authorization` and request the narrow missing authorization. |
| `inconclusive` | Any lower-confidence, mixed, incomplete, flaky, or competing explanation. | Preserve evidence and stop as blocked or request clarification; never repair. |

Do not turn a retry pass into a clean verification result. It is additional
evidence only and must retain the original failure, retry count, and uncertainty.
An unauthorized or prohibited action is classified before execution; do not
attempt it to collect more evidence.
