# Mobile Failure Classification

## Primary Classifications

Choose exactly one mutually exclusive primary outcome:

| Classification | When to use |
| --- | --- |
| `product-defect` | The selected check failed due to observable behavior in the installed application that is not caused by a test error, missing authorization, or unavailable capability. |
| `test-defect` | The test code, Maestro flow, or Appium configuration contains an error that caused the failure. Confidence must be at least 0.80 before repair is allowed. |
| `environment` | The target device, simulator, or emulator is in an unexpected state, or the execution environment does not match the declared target. |
| `authorization-required` | A required authorization is missing, expired, or insufficient. This includes repository-local bootstrap authorization, host-level prerequisites, real-device provisioning, and production access. |
| `capability-unavailable` | The selected driver adapter or target capability is not available. This includes missing Appium server, missing Maestro CLI, unavailable simulator, or unavailable emulator. |
| `inconclusive` | The failure cannot be determined with sufficient confidence. Stop rather than repair. |

## Classification Requirements

Every classification must include:
- **confidence**: numeric value between 0.0 and 1.0
- **rationale**: plain-text explanation of the classification
- **linked_evidence_ids**: valid manifest evidence IDs for the failed run
- **original_attempt_preservation**: the original test/flow code and manifest revision are preserved and not overwritten

## Prohibited Blind Replay

Do not blindly replay:
- upgrade sequences
- state-losing install operations
- permission external effects
- real-device provisioning
- production-connected operations

## Mapping to Protocol Status

| Classification | Protocol Status |
| --- | --- |
| `product-defect` | `handoff-required` |
| `test-defect` | `generated-unverified` (enter repair) |
| `environment` | `needs-clarification` |
| `authorization-required` | `needs-authorization` |
| `capability-unavailable` | `capability-unavailable` |
| `inconclusive` | `needs-clarification` |
