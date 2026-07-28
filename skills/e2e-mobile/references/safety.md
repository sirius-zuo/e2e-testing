# Mobile Safety Contract

## Target tiers

| Tier | Rules |
| --- | --- |
| `local` | Allowed; use dedicated simulator or emulator. |
| `ephemeral` | Allowed; use disposable virtual target with snapshot reset. |
| `staging` | Allowed with explicit authorization; non-destructive observation only. |
| `production` | Allowed with explicit authorization; non-destructive observation only. |

## Dedicated devices

- Use dedicated devices for mobile testing.
- Never share a testing device with other processes or users.
- Dedicated devices reduce the risk of interference from background apps
  or system services.

## Synthetic accounts and data

- Use synthetic test accounts and synthetic test data for all testing.
- Never use real user accounts or production data in tests.
- Synthetic data must be disposable and scoped to the installation.

## Runtime credential references

- Credentials remain runtime references.
- Credential names are recorded; values are never stored in manifests,
  generated tests, deep links, screenshots, video, accessibility dumps,
  logs, or handoffs.
- Credentials must be provided via secure environment variables or
  authorized secret managers.

## Sensitive evidence suppression

- Screenshots, video, and accessibility snapshots are sanitized before
  recording.
- Credentials, tokens, secrets, and PII are redacted from all artifacts.
- Sanitization is applied at collection time, not just before recording.

## Reset policies

- `app-scoped reset` is the default for all targets.
- `virtual-snapshot` reset is only valid on disposable virtual targets
  (simulators and emulators with snapshot support).
- Whole-real-device wipe is categorically prohibited.

## Disposable virtual snapshot reset

- Only available on disposable simulators and emulators.
- Records a snapshot before testing and restores it after cleanup.
- Not available on real devices or remote targets.

## Whole-real-device wipe prohibition

- Whole-device wipe is categorically prohibited on all targets.
- Only app-scoped or virtual-snapshot reset is permitted.
- Any operation that would cause whole-device state loss must be rejected.

## Non-secret deep links

- Deep links must use non-secret URI schemes and parameters.
- Secret URIs, tokens, or credentials must never appear in deep-link strings.
- Deep links are recorded as references, not as plaintext values.

## Permission restoration

- Permission profiles are applied before testing and restored after testing.
- Permission changes must be recorded and reverted.
- Permission external effects (e.g., system dialogs) are not replayed.

## Production-connected app restrictions

- Production-connected app verification is explicitly configured.
- Non-destructive observation only; no backend mutation or external side effects.
- Backend mutation and external side effects are categorically prohibited.
- Separate authorization is required for each production-connected session.

## Incident stop conditions

Stop execution immediately when:
- A real device shows personal data or unexpected content.
- An unexpected write or mutation is detected outside test scope.
- Cleanup fails and cannot be recovered.
- A target drift is detected (device/OS change during the run).
