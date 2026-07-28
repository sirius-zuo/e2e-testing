# Orchestrator workflow

## Contents

- [Purpose](#purpose)
- [Discovery inventory](#discovery-inventory)
- [Journey planning](#journey-planning)
- [Routing](#routing)
- [Actions and handoffs](#actions-and-handoffs)
- [Resume](#resume)

## Purpose

This workflow turns repository evidence into a portable journey plan. It does
not select implementation APIs, generate framework code, or claim browser
verification. Those decisions belong to the routed capability.

Start with the requested mode and the project root. Read repository-level
instructions before inspecting application source, package metadata, tests, or
targets. Before reading, validating, or initializing Protocol 2, perform a
read-only browser-framework discovery from package metadata, lockfiles, browser
test scripts, configuration, existing specs, fixtures, and CI commands. If any
alternate browser driver is detected, including alongside Playwright,
persist a valid `capability-unavailable` outcome with the detected
driver and source locations. Detection itself is read-only: do not add or
change Playwright dependencies, configuration, tests, evidence, or other test
infrastructure. The sole write permitted for that outcome is its durable
manifest record. A manifest records all other work after this framework gate
passes; then update it before a handoff and after receiving a handoff result.

## Discovery inventory

Record only evidence that can be traced to a source. The inventory should cover
the following fields for every candidate journey.

| Evidence area | Look for | Evidence label | Record in plan |
| --- | --- | --- | --- |
| Specifications | acceptance criteria, stories, design notes | `spec-derived` | source location and uncertainty |
| Routes | navigation, handlers, public URLs, app entrypoints | `source-derived` | entry and endpoint |
| Existing tests | unit, integration, browser suites, fixtures | `source-derived` | coverage, conventions, gaps |
| Package setup | dependencies, scripts, lockfiles, CI config | `source-derived` | detected framework and commands |
| Live target | approved deployment, visible flows, response behavior | `live-observed` | target tier, observation time |
| Data model | test accounts, reset paths, mutable records | `source-derived` | setup and cleanup risks |
| Authentication | supported test login path and roles | `source-derived` | role and secret reference only |

Do not infer a live behavior merely because the source suggests it. Likewise,
do not treat an observed deployment as proof of an uninspected branch. Preserve
the distinction with `live-observed`, `source-derived`, and `spec-derived`.

When sources disagree, capture each source and the affected journey. Assign
`needs-clarification`, add a question to the plan, and keep working on journeys
that do not depend on that answer.

## Journey planning

Use a stable identifier in the exact form `journey-<kebab-name>`. Derive the
name from the user outcome rather than a route or test filename. For example,
`journey-checkout-with-card` remains stable when the checkout URL changes.

Each journey plan includes:

- user goal and entry condition;
- ordered observable checkpoints;
- evidence sources and their labels;
- required role, seed data, and cleanup needs;
- risk fields: `risk_level`, `risk_reason`, `data_mutation`, `environment`,
  `approval_required`, and `blocking_question` when applicable;
- current status and the action that can advance it.

Use a focused independent journey per meaningful user outcome. A broad flow can
link to smaller journey IDs but must not hide their separate risks or status.
When a checkpoint lacks evidence, make the uncertainty explicit instead of
inventing a selector, an expected response, or a data value.

## Routing

### Surface discovery

Identify the surface before routing:
- Confirmed web boundary only → route to `e2e-web`.
- Confirmed service boundary (HTTP, GraphQL, gRPC, WebSocket, queue, or stream) → route to
  `e2e-service`.
- Both web and service requested or required → return `needs-clarification`. Multi-system and
  multi-surface composition are excluded in V2.
- No confirmed boundary → return `needs-clarification`.

One primary surface per run. Persist the route before delegation.

### Browser framework gate

Routing is framework-neutral for web. First determine whether a browser E2E driver
is present from package setup, existing suite structure, and repository
instructions. Do not alter dependencies, configuration, or test infrastructure
as part of this decision.

| Detected condition | Persisted action | Result |
| --- | --- | --- |
| Cypress, WebdriverIO, Selenium, or another driver is present, even with Playwright | `capability-unavailable` | persist the detected driver and read-only evidence only; do not mutate Playwright or test infrastructure |
| Playwright is present with no alternate browser driver | `e2e-web` | hand off to `e2e-web` |
| No browser E2E driver is present | `e2e-web` | hand off to `e2e-web` |
| Driver evidence is ambiguous but does not establish an alternate driver | `needs-clarification` | ask without infrastructure change |

Direct routing is appropriate when the host can invoke the capability by name.
Automated routing is appropriate only when the host has an authorized capability
for delegation. After the framework gate passes, persist the action first,
including its inputs, `run.revision`, target journey IDs, and expected resume
condition. For an unavailable capability, persist the durable manifest outcome
only after the read-only gate; it is not a license to bootstrap, migrate, or
mutate test infrastructure.

### Service boundary gate

When service boundaries are confirmed:
- Route complete work to `e2e-service` only.
- The same framework gate logic applies but uses service boundary evidence instead of browser drivers.

### Mobile boundary gate

When mobile boundaries are confirmed:
- Detect Appium (`appium.config.js`, `androidTest/`, `ios/`, XCUITest/UiAutomator2) or
  Maestro (`.maestro/`, flow YAML) repository-native conventions.
- Detox and Flutter `integration_test` are treated as non-black-box capability evidence;
  they are recorded but never used as an acceptance oracle or a migration target.
- Persist the detected driver, source locations, and target tier before routing.
- Never mutate an unsupported setup or migrate between drivers.
- Route complete mobile work to `e2e-mobile` only.

### Database support

- Use `database-setup`, `database-cleanup`, and `database-diagnostics` capabilities for execution
  support. See [database-support.md](database-support.md) for rules.
- Database actions use existing core records; they are never an acceptance oracle.
- Cleanup failure blocks run completion without rewriting check outcomes.

## Actions and handoffs

`actions` is ordered. The first action is the default only when its
preconditions are true. Independent actions may appear together so a capable
host can execute them concurrently; their order still records deterministic
resume behavior. Do not put mutually dependent actions in concurrent groups.

Every action record includes an action identifier, kind, journey IDs, input
summary, source `run.revision`, owner or capability, status, and result or
failure reference. Keep a capability handoff record for each delegated action:

| Field | Meaning |
| --- | --- |
| `id` | stable identifier for this delegation |
| `capability` | capability requested, such as `e2e-web` |
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

Apply returned evidence to only the scoped journey IDs. Re-evaluate their
status, risks, and ordered `actions`. A successful `e2e-web` result can
advance generated work, but it does not change `generated-unverified` to a
verified status without the protocol conditions for verification.

When no compatible capability can continue, provide the exact explicit mode,
journey IDs, action kind, and `run.revision` needed for the next invocation.
