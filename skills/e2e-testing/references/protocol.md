# Protocol operating guide

## Contents

- [Protocol scope](#protocol-scope)
- [Modes](#modes)
- [State transitions](#state-transitions)
- [Command examples](#command-examples)
- [Revisions and conflicts](#revisions-and-conflicts)
- [Journey and aggregate status](#journey-and-aggregate-status)

## Protocol scope

Protocol 2 is the manifest contract shared by the orchestrator and `e2e-web`.
Use the bundled utility and schema as the source of truth for manifest shape.
This guide explains when to change state; it intentionally does not duplicate
the JSON Schema.

Always validate a compatible manifest before resuming it. Initialize a new
Protocol 2 manifest only when none exists. A malformed manifest, or one with an
unrecognized `protocol_version`, is preserved untouched. Only an exact
parseable Protocol 1 object (`protocol_version` equal to `1.0`) may be
replaced, and only with `--replace-protocol-1`; this discards the Protocol 1
object and creates a fresh Protocol 2 run, and does not preserve Protocol 1
history. Preserve prior actions and evidence rather than rebuilding history
from a new observation.

## Modes

| Mode | Preconditions | Required result |
| --- | --- | --- |
| `plan` | target root and enough evidence to describe journeys | validated plan and `run.revision`; stop |
| `generate` | valid plan or enough evidence to create one | route generation; mark output `generated-unverified` |
| `verify` | valid generated work, authorized target, and runnable verification action | route only after all are recorded |
| `repair` | a recorded verification failure tied to a journey and revision | route only to address that failure |
| auto | valid manifest with eligible ordered actions | take the first eligible `actions` entry |

Explicit mode does not silently fall through to another mode. If its
preconditions are absent, persist or report the exact action needed to satisfy
them. In `plan`, no capability generation or target verification occurs.

## State transitions

Use manifest-defined statuses, retaining evidence and action history at every
transition. Common orchestrator transitions are:

| From | Event | To |
| --- | --- | --- |
| `initialized` | planning completes | `planned` |
| `initialized` | conflicting or missing material evidence | `needs-clarification` |
| `initialized` | unsupported browser driver detected | `capability-unavailable` |
| `planned` | `e2e-web` route is persisted | `ready-for-adapter` |
| `ready-for-adapter` | routed generation completes | `generated-unverified` |
| `generated-unverified` | authorized verification starts | `verifying` |
| `verifying` | verification succeeds with selected-test evidence | `verified` |
| `verifying` | test defect is classified | `repair-ready` |
| `verifying` | product defect is classified | `handoff-required` |
| `repair-ready` | bounded repair is recorded pending re-verification | `generated-unverified` |

Never upgrade a journey merely because `e2e-web` produced artifacts. Verification
is a distinct transition with its own evidence and authorization conditions.

## Command examples

Run the bundled protocol utility from the portable skill directory, supplying
the project manifest path required by the utility. Use the available command
help to confirm exact arguments in the installed protocol version.

```sh
python3 scripts/e2e_protocol.py --help
python3 scripts/e2e_protocol.py init --help
python3 scripts/e2e_protocol.py validate --help
```

Initialize, resume, or replace an exact Protocol 1 manifest with:

```sh
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json --replace-protocol-1
python3 scripts/e2e_protocol.py validate PROJECT/.e2e/manifest.json
```

Validate after initialization, before routing, after applying a handoff result,
and before reporting completion. A manifest path may live under the target
project's `.e2e/` directory; do not assume the skill bundle itself is the
project root.

## Revisions and conflicts

Every mutating operation consumes a known `run.revision` and creates the next
revision. Record that base revision on actions and capability handoffs. On
resume, compare the current `run.revision` to the consumed one before applying a
result.

If revisions conflict, do not overwrite or merge by guesswork. Keep both
records, identify the affected journeys, mark any uncertain journey
`needs-clarification`, and create an action to reconcile the conflict. An
independent journey can continue if its evidence and actions do not depend on
the conflict.

Stale handoff results remain valuable evidence but cannot update current state
until they are explicitly reconciled. Report the exact revision mismatch and
the next invocation that can resolve it.

## Journey and aggregate status

Status is first evaluated per journey. Each `journey-<kebab-name>` record has
its own evidence, risks, preconditions, action history, and state. Do not let a
successful journey conceal a blocked or unverified sibling.

The aggregate `run.status` summarizes those journey states for routing and
human reporting. It must distinguish at least these outcomes:

| Aggregate condition | Report |
| --- | --- |
| all scoped journeys have completed their requested mode | complete for that mode |
| any journey needs a decision | needs clarification, with IDs |
| any journey is generated but not verified | generated-unverified, with IDs |
| any journey has an eligible action | pending, showing ordered `actions` |
| all remaining work is blocked | blocked, with reason and required authority |

Report both the aggregate summary and each non-complete journey. This makes a
partial result actionable without overstating what has been verified.
