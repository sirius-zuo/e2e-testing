# Adapter protocol usage

`e2e-web` consumes Protocol 2 manifests and uses the bundled utility as the
authoritative validator and state writer. Resolve the utility from the installed
`e2e-web` skill directory, never from an assumed `scripts/` directory in the target
project. First perform the workflow's read-only framework gate. If it detects an
alternate browser driver, after read-only detection, create the durable capability-unavailable outcome without adding Playwright infrastructure.
Use the protocol utility only to persist that outcome with detected framework
names and source locations; do not bootstrap, migrate, or write tests or other
evidence. It can otherwise run directly: initialize or resume
`.e2e/manifest.json` when needed, record the requested mode and discovered
Playwright selection, then validate before every state update. Keep `e2e-web`
workflow artifacts in `.e2e/` and do not place secret values in the manifest or
evidence.

Initialize, resume, or replace an exact Protocol 1 manifest with:

```sh
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json --replace-protocol-1
python3 scripts/e2e_protocol.py validate PROJECT/.e2e/manifest.json
```

A malformed manifest, or one with an unrecognized `protocol_version`, is
preserved untouched. Only an exact parseable Protocol 1 object
(`protocol_version` equal to `1.0`) may be replaced, and only with
`--replace-protocol-1`; this discards the Protocol 1 object and creates a fresh
Protocol 2 run, and does not preserve Protocol 1 history.

The CLI provides `init`, `validate`, and state `transition` convenience commands.
For `e2e-web`-owned record updates beyond `run.status` and `actions`, load the
bundled `e2e_protocol.py` from its explicit skill path (for example with
Python's `importlib.util.spec_from_file_location`) and call its public
`save_manifest(manifest_path, data, expected_revision)` function. Read the
current manifest first, preserve its history, supply its current revision, and
let that function validate, atomically write, and increment the revision. Never
hand-edit a manifest or overwrite it with a stale revision.

## Adapter-owned records

Maintain the following `e2e-web`-specific facts in the existing Protocol 2
fields:

- `systems[0].project_root` and the `e2e.web` extension's `data.driver` and
  `data.project`: detected browser driver, project shape, and the evidence
  that supports it.
- `journeys`: web preconditions, observable checkpoints, source labels, and
  per-journey status.
- `checks`: stable check ID, linked `journey_id`, `execution_unit_id`, file
  path, browser project, and selected-check status.
- `evidence`: sanitized generation or verification evidence, including the
  fields required by [workflow.md](workflow.md#verify).
- `attempts`: verification and repair attempt IDs, consumed budgets, selected
  checks, and classification references.
- `handoffs` and `actions`: capability, scoped journey/check IDs, missing
  prerequisite or product defect, `run.revision`, and resume condition.

## State use

For a compatible direct or delegated run, use only valid utility transitions.
`plan` moves discoverable work toward `planned` and `ready-for-adapter`.
`generate` writes check registrations and finishes `generated-unverified` without
suite execution. `verify` enters `verifying`, then records either `verified`,
`repair-ready`, `handoff-required`, `needs-clarification`,
`needs-authorization`, or `blocked` according to its classification.

`repair` begins only from recorded test-defect evidence in `repair-ready`; after
the bounded test-only change it returns through `generated-unverified` and
invokes verification. Unsupported browser driver detection ends as
`capability-unavailable`; an unsupported extension version ends as
`extension-incompatible`. Each successful write increments `run.revision`; do not
overwrite a stale manifest writer. Preserve previous evidence and actions rather
than replacing history.
