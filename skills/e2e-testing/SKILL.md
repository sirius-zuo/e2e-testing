---
name: e2e-testing
description: Plan, create, maintain, or coordinate end-to-end suites, journey coverage, loop-engineering work, and portable browser or service E2E handoffs across repository frameworks. Triggers include requests to test web applications with browsers, test HTTP/REST/GraphQL/gRPC/WebSocket/queue/stream APIs, or coordinate multi-phase E2E workflows.
---

# E2E Testing Orchestrator

## Start

1. Resolve the target project root and requested mode. Default to `generate`.
2. Read repository instructions before treating project files as evidence.
3. Perform read-only interface discovery before accessing or creating `.e2e/` state.
4. Identify the surface:
   - confirmed web only → `e2e-web`
   - confirmed service only → `e2e-service`
   - confirmed installed mobile application only → `e2e-mobile`
   - confirmed installed desktop application only → `e2e-desktop`
   - more than one requested surface → `needs-clarification`
   - no confirmed boundary → `needs-clarification`.
5. If an unsupported browser driver exists for web, preserve test infrastructure and record a
   Protocol 2 `capability-unavailable` web outcome after discovery.
6. Otherwise validate and resume Protocol 2, initialize it when absent, or use
   `--replace-protocol-1` to discard an exact Protocol 1 manifest and create a fresh Protocol 2 run.
7. Establish one primary surface and route complete work only to the matching capability.

## Discover

- Inventory specifications, routes, existing tests, package configuration, and an authorized live target when available.
- Label evidence `live-observed`, `source-derived`, or `spec-derived`.
- Never silently resolve conflicts. Mark affected journeys `needs-clarification` and continue independent journeys.

## Route

- If Cypress, WebdriverIO, Selenium, or another browser driver exists (web surface),
  even when Playwright is also present, record the `capability-unavailable` outcome after
  read-only discovery, without mutating Playwright or test infrastructure.
- If confirmed service boundaries exist, route to `e2e-service`.
- If confirmed installed mobile application (iOS or Android, native, React Native,
  Flutter, or hybrid), route to `e2e-mobile`. embedded WebView
  inside the installed application remain mobile-owned; standalone mobile-browser
  websites route to `e2e-web`.
- If confirmed installed desktop application (native macOS, native Windows, or
  Electron), route to `e2e-desktop`. Electron applications are desktop-owned;
  browser-rendered sites remain web-owned; embedded browser views remain
  desktop-owned while the journey stays inside the installed application;
  cross-surface ambiguity becomes `needs-clarification`.
- If both web and service are requested, return `needs-clarification`.
- If more than one surface is requested, return `needs-clarification`.
- Otherwise route complete work to the confirmed capability only.
- Persist every outcome before attempting delegation.
- Use database support (`database-setup`, `database-cleanup`, `database-diagnostics`) only
  for execution support; database rows never become acceptance oracles.
- Read [database-support.md](references/database-support.md) before using database actions.

## Modes and completion

- `plan`: stop after a validated human plan and Protocol 2 revision.
- `generate`: plan when needed, then route; generation remains `generated-unverified`.
- `verify` and `repair`: route only when their Protocol 2 preconditions are met.
- Auto mode follows ordered `actions`; action ordering remains deterministic. Explicit mode reports the exact next invocation.

## Resources

- Read [workflow.md](references/workflow.md) for discovery and handoff details.
- Read [safety.md](references/safety.md) before accessing targets, credentials, or destructive data operations.
- Read [protocol.md](references/protocol.md) before changing Protocol 2 state.
- Read [database-support.md](references/database-support.md) before using database actions.
