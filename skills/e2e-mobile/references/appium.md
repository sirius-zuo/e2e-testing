# Appium Adapter Contract

## Evidence-based discovery

1. Look for `appium.config.js` or equivalent Appium configuration files in the
   repository root or project subdirectories.
2. Detect repository-native test clients (JavaScript, Python, Java, C#) and
   existing test-runner conventions. Preserve existing conventions; do not
   introduce a different test framework or runner.
3. Detect the Appium server version and installed platform drivers (XCUITest
   for iOS, UiAutomator2 for Android). Record versions and capability lists.
4. Detect available commands: `appium`, `appium driver`, `appium plugin`, and
   any repository-level wrapper scripts.
5. Detect supported capabilities from the configuration and driver versions.

## XCUITest for iOS and UiAutomator2 for Android

- XCUITest is the required iOS driver; UiAutomator2 is the required Android
  driver.
- Detect available XCUITest and UiAutomator2 versions and record them.
- Do not migrate between XCUITest and other iOS drivers or between
  UiAutomator2 and other Android drivers.

## Preserve existing conventions

- preserve existing language, client library, and test-runner conventions.
- Do not add, remove, or change dependencies, configuration, or test
  infrastructure as part of discovery.
- If an alternate Appium configuration exists (e.g., separate test and
  production configs), detect and preserve it.

## Repository-local bootstrap

- Separate authorization is required before any repository-local bootstrap
  (installing the Appium server, platform drivers, or plugins).
- Authorization for bootstrap is distinct from authorization for host-level
  prerequisites.
- Bootstrap changes are limited to test infrastructure only.

## Host-level prerequisite action

A separate authorization is required for missing prerequisites:
- Appium server CLI (`appium`)
- Platform driver (XCUITest for iOS, UiAutomator2 for Android)
- Xcode and iOS SDK for simulator
- Android SDK and Java/JDK for emulator
- Cloud provider access for remote Appium endpoints

## Target selection

- Select the exact simulator UDID, emulator serial, or real-device UDID from
  the configuration or from an explicitly authorized list.
- Never use "first connected device" or implicit device selection.
- Record the exact target identifier in the manifest.

## Remote Appium endpoint

- Remote Appium endpoints (BrowserStack, Sauce Labs, Firebase Test Lab, etc.)
  require explicit authorization and provider provisioning.
- Do not connect to a remote Appium endpoint without first recording the
  remote endpoint reference, provider identity, and authorization.
- Remote targets are capability-gated: only capabilities supported by the
  remote provider are valid.

## Generation and execution

- Generate tests or flows against selected check IDs only.
- Execute only the generated tests or flows; do not run the entire suite.
- Normalize evidence into the mobile execution environment vocabulary.

## Capability-unavailable behavior

- If the selected capability is not available (missing driver, unavailable
  simulator/emulator, missing server), record a `capability-unavailable`
  outcome and stop.
- Never attempt framework migration (e.g., from Appium to Maestro or vice
  versa) to fill a capability gap.
