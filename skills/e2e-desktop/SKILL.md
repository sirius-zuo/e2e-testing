---
name: e2e-desktop
description: Plan, generate, verify, and repair black-box E2E checks for installed native macOS, native Windows, and Electron desktop applications.
---

# Desktop E2E

Use this skill only for one declared installed desktop application. Default to `generate` when the mode is omitted. Supported modes are `plan`, `generate`, `verify`, and `repair`.

Use `e2e.desktop@1.0`. Treat Appium Mac2, NovaWindows, and WebdriverIO Electron as first-class adapters. Preserve existing capability-gated Playwright Electron or WinAppDriver setups; never migrate them automatically.

Every live run requires a dedicated OS user session or ephemeral VM. Refuse a general-purpose, shared, locked, disconnected, or unbounded session.

Read [workflow](references/workflow.md), [safety](references/safety.md), [lifecycle](references/lifecycle.md), and [evidence](references/evidence.md) before acting. Read the selected platform/driver reference and [protocol](references/protocol.md). For repair, also read [failure classification](references/failure-classification.md) and [repair guardrails](references/repair-guardrails.md).

Generation creates repository-native desktop tests and ends `generated-unverified`. Verification runs only selected check IDs and requires current-revision execution plus cleanup evidence. Never modify application source, packaging, signing, expected outcomes, OS security, or production configuration.
