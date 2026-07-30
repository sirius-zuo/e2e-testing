# iOS Platform Profile

## macOS and Xcode requirements

- macOS is required for iOS simulator and real-device testing.
- Xcode and the iOS SDK must be available for simulator discovery and
  management.
- Record the Xcode version, iOS SDK version, and available simulator
  device types.

## Simulator discovery

- Detect available simulators using `xcrun simctl list`.
- Record simulator UDID, device type, and OS version.
- Use the explicit UDID for all operations; never rely on implicit selection.

## Bundle ID and artifact requirements

- The `ios_bundle_id` from the `e2e.mobile@1.0` application data must match
  the installed application or candidate artifact.
- The candidate artifact must be recorded with its build reference and
  provisioning information before installation.

## Permission and deep-link operations

- Permission requests (notifications, location, camera, etc.) require explicit
  recording of the permission profile and its expected state.
- Deep-link operations use non-secret URI schemes recorded in the
  `deep_link_refs` of the lifecycle profile.
- Permission restoration after testing is required.

## Real-device requirements

- Real-device testing requires pre-provisioned signing certificates,
  provisioning profiles, and device trust.
- The device UDID must be explicitly authorized and recorded.
- Do not pair, trust, provision, or manage devices automatically.

## Prohibited operations

- Pairing or trusting devices is not performed by the mobile skill.
- Provisioning profile management is not performed by the mobile skill.
- Whole-device wipe is categorically prohibited.
- System-level modifications are not performed by the mobile skill.

## Reset policies

- `app-scoped`: reset application data only. This is the default.
- `virtual-snapshot`: reset to a virtual snapshot. Only valid on disposable
  simulators.
- Distinguish app-scoped reset from whole-device wipe at all times.

## Cleanup evidence

- After testing, record cleanup evidence showing the application state was
  reset and no residual test data remains.
- Cleanup evidence includes the target UDID, app bundle ID, and reset result.
