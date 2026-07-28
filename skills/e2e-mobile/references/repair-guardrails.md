# Mobile Repair Guardrails

## Allowed Changes

Repair is strictly limited to:

1. **Mobile tests and Maestro flows** — `.maestro/` YAML flows, Appium test
   files, and test support scripts owned by the mobile skill.
2. **Driver test configuration** — `appium.config.js` test sections, Maestro
   flow configuration, and test-specific capability overrides.
3. **Fixtures** — deterministic fixture data in `evals/fixtures/mobile-contract/`.
4. **Dedicated test support** — test-specific helpers, shims, and mock utilities
   under `test-support/` owned by the mobile skill.

## Protected Paths

The following must **never** be modified during repair:

- **Application source code** — native, React Native, Flutter, or hybrid source.
- **Native/cross-platform build files** — Gradle, Pod, Cargo, or build scripts.
- **Signing and provisioning** — certificates, provisioning profiles, keystore,
  entitlements, or code-signing configuration.
- **Production configuration** — production URLs, API keys, feature flags, or
  deployment settings.
- **Public behavior** — observable app behavior, navigation flows, or UI content.
- **Expected outcomes** — assertions, expected responses, or acceptance criteria.
- **Unconditional skips** — do not add unconditional skips to bypass failures.
- **Arbitrary sleeps** — do not add `sleep`, `wait`, or timed delays.

## Repair Budget

- Compare every changed test's assertions and journey comments before and after.
- Do not exceed either repair or wall-clock budget.
- After every repair, invoke `verify`.

## Classification Gate

Only a `test-defect` classification at confidence 0.80 or higher may enter repair.
Use `inconclusive` and stop rather than repair when confidence is insufficient.

## Evidence Preservation

- Original test/flow code is preserved under a dated backup path.
- Manifest revision is incremented for each repair cycle.
- Repair evidence carries `support_only: true` and is not an acceptance oracle.
