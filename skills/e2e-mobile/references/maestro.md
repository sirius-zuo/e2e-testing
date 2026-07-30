# Maestro Adapter Contract

## Accessibility-driven discovery

accessibility-driven black-box discovery and YAML flow preservation.
1. Look for `.maestro/` directory and YAML flow files in the repository.
2. Detect existing flow conventions: flow naming, tagging, conditional
   execution, and environment variable usage.
3. Detect the Maestro CLI version and installed capabilities.
4. preserve existing flow structure and YAML conventions.

## Repository conventions

- Maestro flows live under `.maestro/` by default.
- Flows may use tags for selective execution.
- Flow variables and environment configuration use YAML frontmatter.
- Preserve all existing conventions; do not introduce new file locations or
  naming schemes.

## Selected flow execution

- Execute only the selected flow files matching the selected check IDs.
- Do not run the entire `.maestro/` suite unless explicitly authorized.
- Record which flows were executed and which were skipped.

## Authorized bootstrap

- If the Maestro CLI is not installed on the host, separate authorization is
  required for repository-local bootstrap (installing `maestro` CLI).
- Bootstrap authorization is distinct from host-level prerequisite
  authorization.
- Bootstrap changes are limited to test infrastructure only.

## Host-level prerequisite

A separate authorization is required for a missing host CLI:
- Maestro CLI (`maestro` or `npx @maestro/cli`)
- iOS simulator or Android emulator tooling for target proof

## iOS simulator and Android emulator baseline

- Maestro operates on iOS simulators and Android emulators by default.
- Detect available simulators and emulators; record their identifiers.
- Do not assume a specific device is available; enumerate and select
  explicitly.

## Version and target proof

- For real-device or remote capabilities, proof of version and target
  availability is required before selection.
- Record the exact device identifier, OS version, and target tier.

## No real-device claim from the Maestro name alone

- The Maestro CLI name does not imply real-device support.
- never claim real-device support from the driver name.
- Real-device or remote-device evidence must come from explicit target
  configuration and authorization.

## No migration to or from Appium

- Maestro is preserved as-is when it already exists in the repository.
- Never migrate between Maestro and Appium; if both are present, route to
  the one that already exists or that has been explicitly authorized.
- If a capability is unavailable, record a `capability-unavailable` outcome
  and stop; do not attempt to migrate to a different driver.
