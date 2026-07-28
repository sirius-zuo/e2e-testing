# Mobile Surface Workflow

## Purpose

This workflow turns repository evidence into a portable mobile journey plan. It
does not select implementation APIs, generate framework code, or claim device
verification. Those decisions belong to the routed capability.

Start with the requested mode and the project root. Read repository-level
instructions before inspecting application source, package metadata, tests, or
targets. Perform read-only mobile discovery from package metadata, lockfiles,
mobile test scripts, configuration, existing specs, fixtures, and CI commands.
Detect existing Appium or Maestro conventions and persist a valid capability
outcome with the detected driver and source locations. Detection itself is
read-only: do not add or change dependencies, configuration, tests, evidence,
or test infrastructure. The sole write permitted for that outcome is its
durable manifest record. You may then validate or initialize Protocol 2.

## Read-only mobile discovery

Inventory specifications, routes, existing tests, package configuration, and
an authorized live target when available. Label evidence `live-observed`,
`source-derived`, or `spec-derived`.

Look for:
- Mobile test directories (`.maestro/`, `e2e/`, `androidTest/`, `ios/`)
- `appium.config.js` or similar Appium configuration files
- Maestro flow YAML files
- Package metadata indicating React Native, Flutter, or native iOS/Android
- CI commands referencing mobile testing tools

When sources disagree, capture each source and the affected journey. Assign
`needs-clarification`, add a question to the plan, and keep working on journeys
that do not depend on that answer.

## Boundary ownership

- Embedded WebViews inside the installed application remain mobile-owned.
- Standalone mobile-browser websites route to `e2e-web`.
- One logical system and one installed application per run.
- Multi-device, multi-app, multi-system, and cross-surface composition are
  excluded.

## Driver selection

1. Detect existing Appium or Maestro conventions.
2. never migrate between drivers.
3. For new repositories, require explicit authorization before repository-local
   bootstrap and a separate host-level prerequisite action for missing CLI or
   SDK.
4. Select the driver that already exists or that has been explicitly authorized.
5. Record the selected check IDs before generation or verification.

## Plan

Use a stable identifier in the form `journey-<kebab-name>`. Derive the name
from the user outcome. Each journey plan includes:
- user goal and entry condition
- ordered observable checkpoints
- evidence sources and their labels
- required role, seed data, and cleanup needs
- risk fields and current status

## Generate

Generation produces test code, Maestro flows, or Appium configuration without
building, installing, launching, or executing. Finish with status
`generated-unverified`. Record the created test paths and configuration
references.

## Verify

Verify only selected check IDs after:
- candidate artifact and target are recorded
- credential references (not values) are recorded
- permission profile is recorded
- setup actions are recorded
- cleanup actions are recorded
- evidence collection paths are recorded

Verify against the existing driver convention. Record lifecycle events,
screenshots, video, accessibility snapshots, and driver results. Sanitize
all artifacts before recording.

## Repair

Classify failures using [failure-classification.md](failure-classification.md).
Repair is bounded to mobile tests, driver test configuration, fixtures, and
dedicated test support only. See [repair-guardrails.md](repair-guardrails.md).

After every repair, invoke `verify`. Never replay upgrade, state-losing install,
permission external effect, or real-device provisioning blindly.

## Actions and handoffs

`actions` is ordered. Every action record includes: action identifier, kind,
journey IDs, input summary, source `run.revision`, owner or capability, status,
and result or failure reference.

Keep a capability handoff record for each delegated action:

| Field | Meaning |
| --- | --- |
| `id` | stable identifier for this delegation |
| `capability` | capability requested, such as `e2e-mobile` |
| `requested_at` | timestamp of the persisted request |
| `manifest_revision` | revision consumed by the delegate |
| `journey_ids` | immutable list of scoped journey IDs |
| `reproduction_steps` | ordered steps that reproduce the selected failure |
| `expected_behavior` | supported behavior the selected test expected |
| `actual_behavior` | observed behavior from failed execution evidence |
| `artifact_refs` | valid IDs for sanitized logs, traces, screenshots, or videos |
| `evidence_ids` | valid manifest evidence IDs, including the failed run and classification |
| `resume` | object containing the exact command for resumed verification |
| `result` | returned status, artifacts, and new evidence |

The handoff must never include plaintext secrets. It may contain approved
secret-reference names and the minimum target context needed by the receiver.

## Resume

On resume, validate the manifest and inspect the most recent action and handoff
records. Confirm the receiving capability used the recorded `run.revision`. If a
result is stale, failed, incomplete, or cannot be tied to that revision, retain
the record, mark its action accordingly, and create the appropriate next action
instead of overwriting history.

Apply returned evidence to only the scoped journey IDs. A successful `e2e-mobile`
result can advance generated work, but it does not change `generated-unverified`
to a verified status without the protocol conditions for verification.

When no compatible capability can continue, provide the exact explicit mode,
journey IDs, action kind, and `run.revision` needed for the next invocation.

cleanup failure blocks completion. A mobile run is not complete until
required app-scoped or virtual-snapshot cleanup produces successful evidence.
