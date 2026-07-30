# Mobile Platform Acceptance

## Authorization Gate

Every live-platform mobile session requires **explicit reviewer authorization**.
Do not run mobile acceptance tests without authorization for that individual session.

## Preflight

Record the following before each authorized session:

- Git revision being tested
- Host OS and version
- Appium or Maestro version and adapter version
- Device/OS identity (simulator UDID, emulator AVD, or real-device serial)
- Application build reference
- Target tier (local, ephemeral, staging)
- Credential reference names only (never values)

## Required Matrix

| Row | Driver | Platform | Status |
| --- | --- | --- | --- |
| 1 | Appium | iOS simulator | pending |
| 2 | Appium | Android emulator | pending |
| 3 | Maestro | iOS simulator | pending |
| 4 | Maestro | Android emulator | pending |
| 5 | Appium | real or remote | pending |

## Authorized Session Steps

1. Select one matrix row and record the preflight data.
2. Run the repository-native selected-check command for the selected check IDs of that driver/platform.
3. Validate the resulting manifest:
   ```bash
   python3 skills/e2e-mobile/scripts/e2e_protocol.py validate .e2e/manifest.json
   ```
4. Confirm the manifest contains:
   - Platform-origin selected-check evidence (not fixture evidence)
   - Successful cleanup evidence
   - Bound to the exact driver, platform, OS, target, artifact, tier, and revision
5. Record the result: `pass`, `fail`, or `not-authorized`.

## Evidence Requirements

- Execution evidence must come from platform-origin runs, not fixtures.
- Cleanup evidence must show successful app-scoped or virtual-snapshot reset.
- Secret/sensitive artifacts must be reviewed before retention.

## Prohibitions

- fixture evidence cannot support a real simulator, emulator, real-device,
  remote-device, or application verification claim.
- Do not use fixture evidence as a substitute for authorized platform runs.

## Abort Rules

Stop execution immediately when:
- Target drift is detected (device/OS change during the run).
- Personal data is observed on a testing device.
- Unexpected writes or mutations occur outside test scope.
- Cleanup fails and cannot be recovered.

## Result Table

| Row | Driver | Platform | Result |
| --- | --- | --- | --- |
| 1 | Appium | iOS simulator | not-authorized |
| 2 | Appium | Android emulator | not-authorized |
| 3 | Maestro | iOS simulator | not-authorized |
| 4 | Maestro | Android emulator | not-authorized |
| 5 | Appium | real or remote | not-authorized |

## V3 Release Block

The V3 release is blocked while any required row is `not-authorized` or lacks
evidence. V3 exit requires every required matrix row to show `pass` with
platform-origin evidence.
