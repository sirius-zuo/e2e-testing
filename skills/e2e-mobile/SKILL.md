---
name: e2e-mobile
description: >-
  Use when the user needs to plan, generate, verify, or repair black-box E2E
  coverage for an installed iOS or Android application through Appium or
  Maestro, including native, React Native, Flutter, hybrid, simulator,
  emulator, provisioned real-device, or preconfigured remote-device workflows.
---

# E2E Mobile Surface Skill

Use `e2e-mobile` for one logical system and one installed application. Support
`plan`, `generate`, `verify`, or `repair`; default to `generate`.

## Recipe

1. Resolve mode, repository root, installed-app boundary, and target tier.
2. Perform read-only mobile discovery before Protocol state.
3. Confirm mobile ownership; embedded WebViews remain mobile and standalone
   mobile-browser sites route to `e2e-web`.
4. Detect existing Appium or Maestro conventions and never migrate between them.
5. Validate or initialize Protocol 2 and bind one `e2e.mobile@1.0` extension.
6. Select driver, platform, artifact, target, and complete lifecycle profile.
7. Require authorization before repository-local bootstrap or target mutation.
8. Generate without building, installing, launching, or executing; finish
   `generated-unverified`.
9. Verify only selected check IDs after artifact, target, credential, permission,
   setup, cleanup, and evidence prerequisites are recorded.
10. Classify failures and repair tests/support only within budget.
11. Complete only after required app-scoped cleanup succeeds.

## Surface contract

- Appium and Maestro are the supported drivers.
- iOS simulator and Android emulator are the deterministic baseline.
- Real and remote targets are explicitly provisioned and capability-gated.
- One run has one logical system and one installed application.
- Never modify application source, build/signing configuration, public behavior,
  production configuration, device provisioning, or provider administration.

## Resources

- Read [workflow.md](references/workflow.md).
- Read [safety.md](references/safety.md) before target or credential access.
- Read [lifecycle.md](references/lifecycle.md) before install or state changes.
- Read [evidence.md](references/evidence.md) before collecting artifacts.
- Read [appium.md](references/appium.md) for Appium.
- Read [maestro.md](references/maestro.md) for Maestro.
- Read [ios.md](references/ios.md) for iOS.
- Read [android.md](references/android.md) for Android.
- Read [failure-classification.md](references/failure-classification.md).
- Read [repair-guardrails.md](references/repair-guardrails.md).
- Read [protocol.md](references/protocol.md).
