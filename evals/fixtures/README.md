# Evaluation Fixtures

Each child directory is a minimal repository used by one or more behavioral cases. The host harness copies a fixture into an isolated temporary repository; agents never operate on the source fixture.

## Mobile contract fixture

The `mobile-contract` fixture uses metadata-only artifacts and deterministic
driver/device shims (`test-support/mobile-driver.js`). It produces fixture-origin
evidence for Appium and Maestro on iOS and Android.

Fixture evidence proves workflow and evaluator behavior only. It cannot support
a real simulator, emulator, real-device, remote-device, or application
verification claim.

## Desktop contract fixture

The `desktop-contract` fixture uses metadata-only applications, targets, and
artifacts for four combinations: native macOS with Appium Mac2, native Windows
with NovaWindows, Electron macOS with WebdriverIO, and Electron Windows with
WebdriverIO. The deterministic shim (`test-support/desktop-driver.js`) produces
fixture-origin evidence for install, launch, activation, minimize/restore, reset,
native dialog, permission, notification, filesystem, protocol handler, update,
selected execution, artifacts, cleanup, session loss, driver failure, and
product behavior scenarios.

Fixture evidence proves workflow and evaluator behavior only. It cannot support
a real desktop session, real-device, or application verification claim. Fixture
shim output is fixture-only and never live platform evidence.

## Integrity baselines

Every fixture contains a source-controlled `.fixture-baseline.json`. It maps every other fixture file to its SHA-256 digest. These files are intentional test inputs, not caches or disposable generated output.

The evaluator uses the baseline to distinguish:

- **preserved** files, which must remain byte-identical;
- **created** files, which must not exist in the baseline;
- **changed** files, which must exist in the baseline and receive an intentional modification.

Tracking the baseline makes fixture changes explicit in code review and prevents a modified source fixture from silently changing the expected evaluation result.

## Changing a fixture

1. Change only the files required by the scenario.
2. Recalculate `.fixture-baseline.json` with sorted relative POSIX paths and lowercase SHA-256 digests.
3. Ensure the baseline contains every fixture file except itself.
4. Run:

   ```sh
   python3 -m unittest tests.test_evaluation_contracts.FixtureContractTests -v
   ```

5. Review the fixture and baseline together. An unexpected hash change is a test-contract change, not formatting noise.

## Fixture rules

- Keep fixtures minimal, deterministic, and dependency-light.
- Do not add credentials, tokens, production endpoints, retained transcripts, or generated `.e2e` run artifacts.
- Do not initialize nested Git repositories.
- Do not edit source fixtures during a behavioral run; use the harness-created copy.
