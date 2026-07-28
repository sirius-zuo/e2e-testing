# Mobile Evidence Contract

## Normalized execution environment

Every mobile execution record carries this normalized environment:

```json
{
  "driver": "appium",
  "driver_version": "recorded-at-runtime",
  "platform": "ios",
  "os_version": "recorded-at-runtime",
  "target_kind": "simulator",
  "application_build_ref": "artifact-candidate-ios",
  "target_reference": "target-ios-sim",
  "target_tier": "local",
  "evidence_origin": "platform"
}
```

## Evidence origin values

- `platform`: evidence collected from a real or virtual target during actual
  driver execution.
- `fixture`: evidence produced by a deterministic fixture shim for workflow
  and evaluator testing only.

Fixture evidence must be explicitly expected by a deterministic case and
**cannot** support a live-platform claim.

## Mobile execution environment fields

| Field | Meaning |
| --- | --- |
| `driver` | Appium or Maestro |
| `driver_version` | Recorded at runtime |
| `platform` | ios or android |
| `os_version` | Recorded at runtime |
| `target_kind` | simulator, emulator, real, or remote |
| `application_build_ref` | Artifact ID for the installed application |
| `target_reference` | Target identifier from the manifest |
| `target_tier` | local, ephemeral, staging, or production |
| `evidence_origin` | platform or fixture |

## Artifact vocabulary

### Screenshots

- Captured at key lifecycle points (install, launch, check start, check end).
- Sanitized before recording; credentials and PII are redacted.
- Stored with lifecycle phase and check ID references.

### Video

- Optional screen recording during verification.
- Sanitized before recording; credentials and PII are redacted.
- Stored with lifecycle phase and check ID references.

### Accessibility snapshots

- Captured via the driver's accessibility API.
- Used for UI structure validation.
- Sanitized before recording.

### Driver results

- Exit codes, stderr/stdout captures, and driver-specific metadata.
- Include session IDs, connection endpoints, and protocol versions.

### Lifecycle events

- Record each lifecycle phase transition: target, install, app-reset,
  permissions, launch, cleanup.
- Include timestamps and duration for each phase.

### Sanitized device/system logs

- Opt-in only; never captured by default.
- Sanitized before recording; credentials and PII are redacted.
- Used for diagnostic purposes only.

### Crash reports

- Captured if the application crashes during testing.
- Stored with crash timestamp, stack trace, and lifecycle context.

### Install and cleanup results

- Record install and cleanup exit codes, duration, and output.
- Required for evaluator gates.

### Network captures

- **network capture is disabled by default.**
- Opt-in only for diagnostic purposes.
- Sanitized before recording; credentials, tokens, and PII are redacted.
- Never used as a mobile acceptance oracle.

## Fixture evidence

- Produced by deterministic fixture shims (e.g., `test-support/mobile-driver.js`).
- Carries `evidence_origin: "fixture"`.
- Proves workflow and evaluator behavior only.
- Cannot support a real simulator, emulator, real-device, remote-device, or
  application verification claim.
