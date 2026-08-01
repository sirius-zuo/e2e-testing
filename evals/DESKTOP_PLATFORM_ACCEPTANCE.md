# Desktop platform acceptance

Live desktop acceptance is opt-in. Every invocation requires explicit authorization for the exact host, OS session, driver, application artifact, target, mutation scope, evidence capture, and cleanup plan. Never use a general user session or production credentials.

## Required matrix

- Appium Mac2 + native macOS
- NovaWindows + native Windows
- WebdriverIO Electron + macOS
- WebdriverIO Electron + Windows
- one remote macOS or Windows path

## Required record

Record run/revision, selected checks, host and OS version, driver/adapter/backend versions, target, dedicated-session identity reference and isolation proof, application and artifact identity/hash/signing metadata, authorizations, lifecycle phases, selected-check evidence, cleanup evidence, baseline restoration, timestamps, and reviewer.

Fixture, mocked, stale-revision, cross-session, incomplete-cleanup, or unredacted evidence cannot satisfy this matrix. Linux, Playwright Electron, and WinAppDriver remain capability-gated and do not satisfy the required matrix.
