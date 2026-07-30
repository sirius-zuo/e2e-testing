# Android Platform Profile

## Android SDK and Java requirements

- Android SDK must be available for emulator and real-device testing.
- Java/JDK must be available for build and test execution.
- Record the Android SDK version, API level, and available emulator
  system images.

## Emulator and ADB serial requirements

- Detect available emulators using `emulator -list-avds`.
- Detect connected devices using `adb devices`.
- Record the exact emulator AVD name or ADB serial for all operations.
- Use the explicit AVD or serial; never rely on implicit selection.

## Package ID and artifact requirements

- The `android_package_id` from the `e2e.mobile@1.0` application data must
  match the installed application or candidate artifact.
- The candidate artifact must be recorded with its build reference before
  installation.

## Permission and deep-link support

- Permission requests (location, camera, storage, etc.) require explicit
  recording of the permission profile and its expected state.
- Deep-link operations use non-secret URIs recorded in the
  `deep_link_refs` of the lifecycle profile.
- Permission restoration after testing is required.

## Real-device requirements

- Real-device testing requires pre-provisioned USB debugging.
- The device serial must be explicitly authorized and recorded.
- Do not root, enroll, or manage devices automatically.

## Prohibited operations

- Rooting or enrolling devices is not performed by the mobile skill.
- Broad ADB mutation is not performed by the mobile skill.
- Whole-device wipe is categorically prohibited.
- System-level modifications are not performed by the mobile skill.

## Reset policies

- `app-scoped`: reset application data only. This is the default.
- `virtual-snapshot`: reset to a virtual snapshot. Only valid on disposable
  emulators.
- Distinguish app-scoped reset from whole-device wipe at all times.

## Cleanup evidence

- After testing, record cleanup evidence showing the application state was
  reset and no residual test data remains.
- Cleanup evidence includes the device serial or emulator AVD, package ID,
  and reset result.
