# Adapter protocol usage

The adapter consumes protocol `1.0` manifests and uses the bundled utility as the
authoritative validator and state writer. Resolve the utility from the installed
adapter directory, never from an assumed `scripts/` directory in the target
project. First perform the workflow's read-only framework gate. If it detects an
alternate browser E2E framework, return `unsupported-framework` to the caller
without calling the protocol utility, creating or validating `.e2e/`, or writing
any target-project evidence. It can otherwise run directly: initialize
`.e2e/manifest.json` when absent, record the requested mode and discovered
Playwright selection, then validate before every state update. Keep adapter
workflow artifacts in `.e2e/` and do not place secret values in the manifest or
evidence.

The CLI provides `init`, `validate`, and state `transition` convenience commands.
For adapter-owned record updates beyond `status` and `next_actions`, load the
bundled `e2e_protocol.py` from its explicit adapter path (for example with
Python's `importlib.util.spec_from_file_location`) and call its public
`save_manifest(manifest_path, data, expected_revision)` function. Read the
current manifest first, preserve its history, supply its current revision, and
let that function validate, atomically write, and increment the revision. Never
hand-edit a manifest or overwrite it with a stale revision.

## Adapter-owned records

Maintain the following adapter-specific facts in the existing manifest fields:

- `project.framework`: detected framework and the evidence that supports it.
- `journeys`: web preconditions, observable checkpoints, source labels, and
  per-journey status.
- `tests`: stable test ID, linked `journey_id`, file path, browser project, and
  selected-test status.
- `evidence`: sanitized generation or verification evidence, including the
  fields required by [workflow.md](workflow.md#verify).
- `attempt_history`: verification and repair attempt IDs, consumed budgets,
  selected tests, and classification references.
- `handoffs` and `next_actions`: capability, scoped journey/test IDs, missing
  prerequisite or product defect, revision, and resume condition.

## State use

For a compatible direct or delegated run, use only valid utility transitions.
`plan` moves discoverable work toward `planned` and `ready-for-adapter`.
`generate` writes test registrations and finishes `generated-unverified` without
suite execution. `verify` enters `verifying`, then records either `verified`,
`repair-ready`, `handoff-required`, `needs-clarification`,
`needs-authorization`, or `blocked` according to its classification.

`repair` begins only from recorded test-defect evidence in `repair-ready`; after
the bounded test-only change it returns through `generated-unverified` and
invokes verification. Unsupported browser framework detection ends as
`unsupported-framework`; an unsupported manifest version ends as
`protocol-incompatible`. Each successful write increments `revision`; do not
overwrite a stale manifest writer. Preserve previous evidence and actions rather
than replacing history.
