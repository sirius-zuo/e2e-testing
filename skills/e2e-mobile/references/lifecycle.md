# Mobile Lifecycle Contract

## State sequence

The exact lifecycle state sequence is:

```
target identity → artifact identity → install/select → app-scoped state →
permission baseline → test-data setup → launch → selected checks →
evidence sanitization → app/test-data cleanup → cleanup evidence
```

## Install and select

- Install the candidate artifact (or prior artifact for upgrade) using the
  driver's install capability.
- Select the target simulator, emulator, or real device using the exact
  identifier from the target data.
- Record the installation result including exit code, duration, and any
  output.

## App-scoped state

- After installation, the application enters an app-scoped state.
- App-scoped state includes the installed version, data directory, and
  initial launch state.
- App-scoped state is preserved between test runs unless explicitly reset.

## Permission baseline

- Apply the permission profile from the lifecycle profile.
- Record the permission state before and after each test.
- Restore permissions to baseline after testing.

## Test-data setup

- Execute any setup actions recorded in `setup_action_refs`.
- Record the setup result including duration and any output.
- Test data must be disposable and scoped to the installation.

## Launch

- **Cold launch**: start the application from a non-running state. Use for
  the initial verification pass.
- **Warm launch**: resume the application from a background state. Use for
  subsequent verification passes.
- Record the launch method, duration, and any output.

## Background and foreground

- **Background**: move the application to the background state.
- **Foreground**: bring the application to the foreground state.
- Background and foreground transitions are optional and controlled by
  the `background_foreground` flag in the lifecycle profile.

## Selected checks

- Execute only the selected check IDs.
- Record outcomes for each check: status, duration, evidence IDs.
- Do not execute checks outside the selected set.

## Evidence sanitization

- Sanitize all collected artifacts before recording.
- Remove or redact credentials, tokens, secrets, and personally identifiable
  information.
- Evidence includes: screenshots, video, accessibility snapshots, driver
  results, lifecycle events, sanitized device/system logs, crash reports.

## App and test-data cleanup

- Remove test data created during setup.
- Apply the reset policy (`app-scoped` or `virtual-snapshot`).
- Record the cleanup result including duration and any output.

## Cleanup evidence

- Record the final cleanup result as evidence.
- Cleanup evidence includes: cleanup action ID, success status, duration,
  and any residual state information.
- **Cleanup failure blocks completion.** A run is not complete until cleanup
  produces successful evidence or an explicit failure record.

## Upgrade lifecycle

Upgrade follows a specific sequence:

1. Install `prior` artifact
2. Establish minimal externally observable state from `prior`
3. Install `candidate` without clearing `prior` state
4. Verify the visible upgrade outcome
5. Record the upgrade evidence

Upgrade must:
- Install prior, establish minimal externally observable state from prior,
  install candidate without clearing it, verify the visible outcome
- Not automatically retry failed upgrades
- Not clear candidate state when reinstalling prior
- Require explicit authorization for upgrade execution

## Orientation

- Orientation is recorded from the lifecycle profile (`portrait`, `landscape`,
  or `unspecified`).
- Do not change orientation during testing unless explicitly authorized.

## Deep links

- Deep links use non-secret URI schemes from `deep_link_refs`.
- Secret URIs, tokens, or credentials must never appear in deep-link strings.
- Record the deep link used and the resulting application state.

## Not automatically retried

- Failed lifecycle operations are not automatically retried.
- A failed install, launch, or reset produces a failure record and stops
  the run unless an explicit retry is authorized.
