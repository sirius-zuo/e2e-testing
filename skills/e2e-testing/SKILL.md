---
name: e2e-testing
description: Plan, create, maintain, or coordinate end-to-end suites, journey coverage, loop-engineering work, and portable browser E2E handoffs across repository frameworks.
---

# E2E Testing Orchestrator

## Start

1. Resolve the target project root and requested mode. Default to `generate`.
2. Read repository instructions before treating project files as evidence.
3. If a compatible `.e2e/manifest.json` exists, validate and resume it.
4. Otherwise run the bundled protocol utility to initialize protocol 1.0.

## Discover

- Inventory specifications, routes, existing tests, package configuration, and an authorized live target when available.
- Label evidence `live-observed`, `source-derived`, or `spec-derived`.
- Never silently resolve conflicts. Mark affected journeys `needs-clarification` and continue independent journeys.

## Route

- If Playwright exists or no browser E2E framework exists, emit an `e2e-web-playwright` action.
- If Cypress, WebdriverIO, Selenium, or another browser framework exists, emit `unsupported-framework` without modifying infrastructure.
- Persist every action before attempting host-supported delegation.

## Modes and completion

- `plan`: stop after a validated human plan and manifest revision.
- `generate`: plan when needed, then route; generation remains `generated-unverified`.
- `verify` and `repair`: route only when their protocol preconditions are met.
- Auto mode follows ordered `next_actions`; explicit mode reports the exact next invocation.

## Resources

- Read [workflow.md](references/workflow.md) for discovery and handoff details.
- Read [safety.md](references/safety.md) before accessing targets, credentials, or destructive data operations.
- Read [protocol.md](references/protocol.md) before changing manifest state.
