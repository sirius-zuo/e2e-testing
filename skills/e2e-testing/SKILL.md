---
name: e2e-testing
description: Plan, create, maintain, or coordinate end-to-end suites, journey coverage, loop-engineering work, and portable browser E2E handoffs across repository frameworks.
---

# E2E Testing Orchestrator

## Start

1. Resolve the target project root and requested mode. Default to `generate`.
2. Read repository instructions before treating project files as evidence.
3. Perform read-only browser-framework discovery before validating or bootstrapping a manifest.
4. If any alternate browser E2E framework exists, even when Playwright is also present, persist a valid `unsupported-framework` manifest/outcome after that read-only detection; do not add or change Playwright or test infrastructure.
5. Validate a compatible `.e2e/manifest.json` and resume it only after the framework gate passes, except to record the durable unsupported outcome.
6. Otherwise run the bundled protocol utility to initialize protocol 1.0.

## Discover

- Inventory specifications, routes, existing tests, package configuration, and an authorized live target when available.
- Label evidence `live-observed`, `source-derived`, or `spec-derived`.
- Never silently resolve conflicts. Mark affected journeys `needs-clarification` and continue independent journeys.

## Route

- If Cypress, WebdriverIO, Selenium, or another browser framework exists, emit and persist `unsupported-framework` after read-only detection, without mutating Playwright or test infrastructure, even if Playwright also exists.
- Only if no alternate browser E2E framework exists, emit an `e2e-web-playwright` action when Playwright exists or no browser E2E framework exists.
- Persist every outcome before attempting host-supported delegation; the unsupported outcome records the detected framework and read-only source locations only.

## Modes and completion

- `plan`: stop after a validated human plan and manifest revision.
- `generate`: plan when needed, then route; generation remains `generated-unverified`.
- `verify` and `repair`: route only when their protocol preconditions are met.
- Auto mode follows ordered `next_actions`; explicit mode reports the exact next invocation.

## Resources

- Read [workflow.md](references/workflow.md) for discovery and handoff details.
- Read [safety.md](references/safety.md) before accessing targets, credentials, or destructive data operations.
- Read [protocol.md](references/protocol.md) before changing manifest state.
