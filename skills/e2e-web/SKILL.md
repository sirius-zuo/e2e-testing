---
name: e2e-web
description: Plan, generate, verify, and safely repair repository-native web E2E coverage through Protocol 2.
---

# Web E2E

Playwright remains the V2 execution driver behind the surface-oriented `e2e-web` boundary.

## Start

1. Resolve `plan`, `generate`, `verify`, or `repair`; default to `generate`.
2. Perform read-only browser-framework detection before validating, initializing, or resuming Protocol 2.
3. Stop as `capability-unavailable` if another browser driver exists; persist only that durable outcome after detection, without Playwright or test-infrastructure mutation.
4. Validate and resume an existing Protocol 2 run, initialize one with the bundled utility when absent, or pass `--replace-protocol-1` to discard an exact Protocol 1 manifest, only after the framework gate passes, except to record that `capability-unavailable` outcome.

## Preserve the project

- Reuse the package manager, language, config, paths, fixtures, and helpers.
- Create one minimal Playwright setup only when none exists.
- Keep workflow artifacts under `.e2e/` and test code in established test paths.

## Run the requested mode

- `plan`: enrich journeys with web preconditions and observable outcomes.
- `generate`: use live inspection when authorized and available; otherwise use source/spec evidence. Do not execute the suite. End `generated-unverified`.
- `verify`: authorize the target, run manifest-selected checks, preserve evidence, and classify every failure.
- `repair`: require a recorded test defect, change test/support files only, then invoke `verify`. Repair changes are bounded by manifest budgets.

## Stop safely

- Never modify application code.
- Never weaken expected outcomes, delete coverage, add unconditional skips, or add hardcoded sleeps.
- Emit a fix-product-defect capability handoff for product defects, plus handoffs for environments, credentials, or authorization.
- End when budgets are exhausted; do not loop indefinitely.

## Resources

- Read [workflow.md](references/workflow.md) for framework discovery and mode procedures.
- Read [failure-classification.md](references/failure-classification.md) during verification.
- Read [repair-guardrails.md](references/repair-guardrails.md) before editing tests.
- Read [protocol.md](references/protocol.md) before changing manifest state.
