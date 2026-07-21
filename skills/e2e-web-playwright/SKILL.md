---
name: e2e-web-playwright
description: Plan, generate, verify, and safely repair Playwright browser E2E coverage through the portable E2E manifest protocol.
---

# Playwright E2E Adapter

## Start

1. Resolve `plan`, `generate`, `verify`, or `repair`; default to `generate`.
2. Perform read-only browser-framework detection before validating or bootstrapping a manifest.
3. Stop as `unsupported-framework` if another browser E2E framework exists; return the outcome without target-repository mutation.
4. Validate an existing manifest or bootstrap one with the bundled utility only after the framework gate passes.

## Preserve the project

- Reuse the package manager, language, config, paths, fixtures, and helpers.
- Create one minimal Playwright setup only when none exists.
- Keep workflow artifacts under `.e2e/` and test code in established test paths.

## Run the requested mode

- `plan`: enrich journeys with web preconditions and observable outcomes.
- `generate`: use live inspection when authorized and available; otherwise use source/spec evidence. Do not execute the suite. End `generated-unverified`.
- `verify`: authorize the target, run manifest-selected IDs, preserve evidence, and classify every failure.
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
