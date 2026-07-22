---
name: e2e-testing
description: Plan, create, maintain, or coordinate end-to-end suites, journey coverage, loop-engineering work, and portable browser E2E handoffs across repository frameworks.
---

# E2E Testing Orchestrator

## Start

1. Resolve the target project root and requested mode. Default to `generate`.
2. Read repository instructions before treating project files as evidence.
3. Perform read-only browser-framework discovery before accessing or creating `.e2e/` state.
4. If an unsupported browser driver exists, preserve test infrastructure and record a Protocol 2 `capability-unavailable` web outcome after discovery.
5. Otherwise validate and resume Protocol 2, initialize it when absent, or use `--replace-protocol-1` to discard an exact Protocol 1 manifest and create a fresh Protocol 2 run.
6. Establish one externally observable `web` system boundary and route complete work only to `e2e-web`.

## Discover

- Inventory specifications, routes, existing tests, package configuration, and an authorized live target when available.
- Label evidence `live-observed`, `source-derived`, or `spec-derived`.
- Never silently resolve conflicts. Mark affected journeys `needs-clarification` and continue independent journeys.

## Route

- If Cypress, WebdriverIO, Selenium, or another browser driver exists, even when Playwright is also present, record the `capability-unavailable` outcome after read-only discovery, without mutating Playwright or test infrastructure.
- Otherwise route complete work to `e2e-web` only.
- Persist every outcome before attempting delegation; the `capability-unavailable` outcome records the detected driver and read-only source locations only.

## Modes and completion

- `plan`: stop after a validated human plan and Protocol 2 revision.
- `generate`: plan when needed, then route; generation remains `generated-unverified`.
- `verify` and `repair`: route only when their Protocol 2 preconditions are met.
- Auto mode follows ordered `actions`; action ordering remains deterministic. Explicit mode reports the exact next invocation.

## Resources

- Read [workflow.md](references/workflow.md) for discovery and handoff details.
- Read [safety.md](references/safety.md) before accessing targets, credentials, or destructive data operations.
- Read [protocol.md](references/protocol.md) before changing Protocol 2 state.
