# V3 Mobile UI Design

**Date:** 2026-07-27
**Status:** Approved design; pending written-spec review
**Project:** `e2e-testing`

## 1. Purpose

V1 established browser E2E testing. V2 established the stable Protocol 2
kernel, migrated the web surface, and added the complete service surface. V3
adds black-box E2E testing for installed iOS and Android applications.

This cycle creates one independently installable `e2e-mobile` skill with
first-class Appium and Maestro support. It covers native and cross-platform
applications through externally observable mobile behavior. React Native,
Flutter, hybrid, and other implementation technologies do not change the
acceptance boundary.

V3 includes:

- repository-native mobile test planning, generation, selected verification,
  failure classification, and bounded repair;
- iOS simulator and Android emulator baseline support through Appium and
  Maestro;
- capability-gated real-device and remote-device execution;
- install, launch, app-scoped reset, background and foreground, deep-link,
  permission, cleanup, and optional upgrade lifecycles;
- mobile-specific artifacts and sanitized evidence; and
- deterministic fixtures plus required Codex and Claude Code behavioral host
  evaluations.

## 2. Governing Principles

- An installed application is treated as a black box behind supported mobile UI
  and operating-system interaction boundaries.
- App internals, framework state, widget trees unavailable through public
  accessibility surfaces, and private APIs are not E2E acceptance oracles.
- `mobile` is the interaction surface. Appium and Maestro are drivers within
  that surface. iOS and Android are platform profiles.
- Native and cross-platform apps follow the same external acceptance rules.
- Existing repository-native test conventions are preserved.
- Driver bootstrap is allowed only with explicit authorization and remains
  limited to test infrastructure and configuration.
- Appium and Maestro are peer supported drivers. V3 never automatically
  migrates a repository from one to the other.
- Protocol 2 core meanings and fields remain unchanged. All mobile-specific
  state belongs in `e2e.mobile@1.0`.
- Simulator and emulator execution is the deterministic baseline. Real and
  remote targets require explicit provisioning, selection, and capability
  evidence.
- A run covers one logical system and one installed application boundary. It
  may contain iOS and Android execution units for that application.
- Multi-device, multi-system, and cross-surface composition remain excluded.
- Generated work is never reported as verified without selected-check execution
  evidence and verified cleanup.

## 3. Ecosystem Revalidation and Driver Selection

The V3 design revalidated driver assumptions against current official
documentation on 2026-07-27.

### 3.1 Supported drivers

Appium is supported through:

- the XCUITest driver for black-box iOS and iPadOS automation on simulators and
  provisioned real devices; and
- the UiAutomator2 driver for Android native, hybrid, and mobile-app automation
  on emulators and provisioned real devices.

Appium uses a WebDriver-based boundary, supports repository-native client
libraries, and provides the required reference path for real devices and
preconfigured remote Appium endpoints.

Maestro is supported as a black-box, accessibility-driven runner for installed
iOS and Android applications, including native, React Native, Flutter, and
hybrid apps. Its repository-native YAML flows make it the preferred greenfield
bootstrap for straightforward local virtual-device journeys.

Driver-specific real-device or remote claims are never inferred from a product
name. The installed driver version, host, target, and provider must prove each
required capability before execution.

### 3.2 Explicitly unsupported driver models

Gray-box and implementation-coupled frameworks are outside the V3 driver
contract even if a target repository already uses them. For example, Detox
explicitly synchronizes with application internals, and Flutter
`integration_test` uses framework test APIs. These suites may be useful
integration tests, but V3 does not extend or verify them as black-box mobile E2E
coverage.

When only an unsupported or ambiguous setup exists, the skill records
`needs-clarification` or `capability-unavailable`. It does not mutate that setup
or mislabel it as supported mobile E2E infrastructure.

### 3.3 Source references

- Appium architecture:
  <https://appium.io/docs/en/latest/intro/appium/>
- Appium XCUITest overview:
  <https://appium.github.io/appium-xcuitest-driver/latest/overview/>
- Appium UiAutomator2 driver:
  <https://github.com/appium/appium-uiautomator2-driver>
- Maestro architecture:
  <https://docs.maestro.dev/get-started/how-maestro-works>
- Maestro repository:
  <https://github.com/mobile-dev-inc/Maestro>
- Detox design principles:
  <https://wix.github.io/Detox/docs/articles/design-principles/>
- Flutter integration tests:
  <https://docs.flutter.dev/testing/integration-tests>

These references justify the initial driver boundary. Runtime support is still
determined from the target repository and installed toolchain rather than from
versions copied into this design.

## 4. Architecture and Ownership

### 4.1 Skill architecture

`e2e-mobile` is one independently installable surface skill:

```text
e2e-mobile
├── shared mobile workflow and safety
├── Appium driver adapter
├── Maestro driver adapter
├── iOS platform profile
└── Android platform profile
```

The driver adapters and platform profiles are internal reference modules, not
independently installed skills.

`e2e-testing` remains the orchestrator. It performs read-only surface
discovery, applies shared safety policy, persists routing, and delegates complete
installed-app work to `e2e-mobile`.

### 4.2 Responsibility boundaries

The shared mobile workflow owns:

- boundary and repository discovery;
- driver and target selection;
- authorization gates;
- Protocol 2 actions, handoffs, revisions, and outcomes;
- common lifecycle ordering;
- evidence and sanitization policy;
- failure classification; and
- bounded test-only repair.

Driver adapters own:

- repository-native configuration discovery;
- driver prerequisite and capability checks;
- driver-specific generation conventions;
- selected-check commands;
- driver result normalization; and
- driver-specific artifacts and diagnostics.

Platform profiles own:

- installable artifact forms and app identifiers;
- simulator, emulator, and real-device prerequisites;
- app launch, background, foreground, termination, and reset mappings;
- permission and deep-link mappings;
- upgrade behavior;
- platform evidence; and
- supported cleanup behavior.

No unit owns application source changes, signing repair, vendor account
provisioning, or general device administration.

### 4.3 Protocol ownership

The canonical extension catalog adds `e2e.mobile@1.0`, owned by `e2e-mobile`.
Bundle projections become:

| Bundle | Recognized namespaces |
| --- | --- |
| `e2e-web` | `e2e.web` |
| `e2e-service` | `e2e.service` |
| `e2e-mobile` | `e2e.mobile` |
| `e2e-testing` | `e2e.web`, `e2e.service`, `e2e.mobile` |

The generic catalog loader, Protocol 2 manifest schema, revision rules,
extension compatibility behavior, and unknown-extension preservation remain
unchanged.

Protocol 2 already supports `mobile` execution units and a mobile primary
surface. V3 does not add a new core public-interface kind. The installed-app
boundary is represented by the core system, target, journeys, mobile execution
units, checks, evidence, actions, and the typed mobile extension. Any supported
embedded WebView interface may retain its existing core `web` interface record,
but the owning execution unit remains mobile.

## 5. Surface and Routing Boundaries

An installed iOS or Android app is owned by `e2e-mobile`, including journeys
that enter an embedded WebView inside that installed app. A standalone website
opened in Safari, Chrome, or another mobile browser remains owned by `e2e-web`.

Repository implementation does not determine surface ownership:

- native iOS and Android apps are mobile;
- React Native, Flutter, and other cross-platform installed apps are mobile;
- hybrid apps remain mobile while the user remains inside the installed app;
- mobile-responsive websites remain web.

A V3 run has one logical system and one installed application boundary. The same
logical app may declare both an iOS bundle ID and Android package ID and may
produce execution units for both platforms. Journeys cannot coordinate two
devices, another installed app, a service execution unit, a browser execution
unit, or a desktop execution unit.

Ambiguous ownership becomes `needs-clarification`. Independent journeys may
continue only when they do not depend on the ambiguity.

## 6. `e2e.mobile@1.0` Data Model

The mobile extension stores only mobile-specific configuration. Core Protocol 2
remains authoritative for systems, targets, journeys, execution units, checks,
evidence, actions, handoffs, authorizations, attempts, statuses, and revisions.

The extension has five required areas:

```json
{
  "application": {},
  "drivers": [],
  "targets": [],
  "artifacts": [],
  "lifecycle_profiles": []
}
```

Empty arrays are valid during unresolved planning. Verification requires the
records selected by its execution units and actions.

### 6.1 Application

The application record contains:

- one logical application ID;
- optional iOS bundle ID and Android package ID;
- repository-relative source and configuration references;
- existing build-command references;
- declared native and embedded-WebView entry points; and
- optional discovered implementation-framework evidence.

At least one platform app identifier is required before generation. Framework
evidence informs repository discovery only and never changes acceptance
semantics.

### 6.2 Drivers

Each driver record contains:

- a stable driver ID;
- driver kind, `appium` or `maestro`;
- discovered driver and adapter versions;
- repository configuration and command references;
- declared capabilities;
- host-platform requirements;
- optional remote-endpoint reference; and
- bootstrap status and authorization reference when applicable.

The extension stores no endpoint credentials or secret values. Those remain
approved references under the core target.

For Appium, capabilities identify the selected platform driver, such as
XCUITest or UiAutomator2. For Maestro, capabilities are taken from the installed
CLI and target rather than assumed globally.

### 6.3 Targets

Each target record contains:

- a stable target ID;
- platform, `ios` or `android`;
- target kind, `simulator`, `emulator`, `real`, or `remote`;
- sanitized device or provider reference;
- operating-system version;
- selected driver ID;
- provisioning status;
- disposable-target flag;
- supported lifecycle capabilities; and
- capability-discovery evidence references.

Target names, bundle IDs, package IDs, and provider references do not prove
authorization. A target is unusable until it is explicitly selected and all
required capabilities are confirmed.

### 6.4 Artifacts

Each artifact record contains:

- a stable artifact ID;
- platform;
- role, `candidate` or `prior`;
- sanitized local or provider artifact reference;
- existing build-command reference when the artifact is built locally;
- application ID and version/build reference; and
- signing or provisioning reference name when required.

The extension never stores signing certificates, provisioning profiles, private
keys, passwords, tokens, or raw provider credentials.

Ordinary generation and verification require only a candidate artifact or an
approved existing build command. Upgrade journeys require explicit prior and
candidate artifacts.

### 6.5 Lifecycle profiles

Each lifecycle profile binds one mobile execution unit to:

- target and artifact IDs;
- install and uninstall policy;
- launch and termination policy;
- app-state reset policy;
- background and foreground operations;
- orientation requirements when present;
- declared deep-link schemes or domains;
- permission baseline and restoration plan;
- optional upgrade transition;
- test-data setup and cleanup actions; and
- final cleanup requirements.

Unsupported lifecycle operations remain explicit capability gaps. They are
never silently skipped.

Portable schema validation enforces the extension shape. Contract tests and
evaluators enforce cross-record references, selected-driver compatibility, and
lifecycle completeness without adding mobile-aware logic to the Protocol 2
kernel.

## 7. Repository-Native Driver Policy

### 7.1 Existing setup

When a repository already has a supported Appium or Maestro setup,
`e2e-mobile` preserves its language, package manager, test runner, directory
layout, fixtures, configuration, commands, selectors, and artifact conventions.

When both drivers are present, the requested or journey-associated convention
wins. If neither can be selected from evidence, the skill asks for
clarification. It never rewrites or migrates tests between the drivers.

### 7.2 Authorized bootstrap

When no supported setup exists, the skill may create the smallest coherent
repository-native setup only after explicit authorization covering dependency
and configuration changes.

The default selection is:

- Maestro for a straightforward local simulator or emulator journey when its
  installed capabilities satisfy the lifecycle; or
- Appium when the required path includes a real device, remote Appium endpoint,
  repository-native Appium conventions, or a capability Maestro cannot prove.

Bootstrap may change only mobile test dependencies, lockfiles, test
configuration, generated tests, and dedicated test-support paths. It does not
change application source, production configuration, public behavior, build
settings, signing settings, deployment configuration, or unrelated
infrastructure.

Repository-local bootstrap authorization does not silently authorize host-level
installation. If the selected driver also requires a missing system-wide CLI,
SDK component, or host service, the skill persists the exact prerequisite and
requests separate authorization. Generation may continue only where the
repository-local result remains coherent; verification stays blocked until the
host prerequisite is independently satisfied.

Partial bootstrap failure is recorded with the exact changed paths and
diagnostics. The skill does not erase pre-existing user changes or claim that
the setup is runnable.

### 7.3 Application build boundary

The skill may invoke an existing repository-native build command after the
verification prerequisites and authorization gates pass. It never invents or
repairs application build or signing configuration merely to obtain an
installable artifact.

If neither an approved artifact nor a working approved build path exists, the
journey becomes `needs-clarification` or `capability-unavailable`.

## 8. Target Policy

### 8.1 Deterministic baseline

Both Appium and Maestro must support the deterministic baseline on:

- one supported iOS simulator configuration; and
- one supported Android emulator configuration.

iOS simulator execution requires an authorized compatible macOS/Xcode host.
Android emulator execution requires an authorized compatible host with the
Android SDK, Java, and selected emulator image.

The skill discovers these prerequisites. It does not install Xcode, an Android
SDK, operating-system images, virtualization support, or system-wide tools as
ordinary driver bootstrap.

### 8.2 Real devices

Real devices are optional, pre-provisioned targets. They require:

- explicit device selection;
- proof that the driver/version supports every required lifecycle operation;
- platform trust, debugging, signing, and provisioning already established;
- a dedicated test-device policy;
- synthetic accounts and test data; and
- an app-scoped cleanup plan.

The skill does not pair, enroll, trust, jailbreak, root, or generally administer
a real device. Whole-device wipes are prohibited.

### 8.3 Remote devices

V3 supports preconfigured remote device farms only through repository-native
remote Appium endpoints or an already established supported driver command.
Vendor account creation, billing, provider provisioning, device-pool
administration, and vendor-specific orchestration are excluded.

Remote provider names do not imply capabilities. The configured endpoint and
selected target must prove install, lifecycle, evidence, and cleanup behavior.

### 8.4 Reset policy

App-scoped reset is the default for all targets. A declared disposable simulator
or emulator may use an authorized snapshot or full virtual-device reset. A real
device may use only supported app-scoped operations and must never be erased or
reset as a whole.

## 9. Workflow

### 9.1 Read-only discovery

Before changing Protocol state, inspect:

- repository instructions and package metadata;
- iOS and Android app identifiers;
- native and cross-platform project layouts;
- existing Appium and Maestro dependencies, configurations, tests, and commands;
- build commands and installable artifacts;
- local, real, and remote target declarations;
- accessibility identifiers and externally visible labels;
- test accounts, fixtures, reset paths, and cleanup support;
- embedded WebView entry points; and
- authorized live target observations when available.

Evidence remains labeled `live-observed`, `source-derived`, or `spec-derived`.
Source presence alone does not prove a supported installed-app boundary or
runnable target.

### 9.2 Plan

`plan` records:

- supported user outcomes and observable checkpoints;
- one logical app boundary;
- platform execution units;
- selected or candidate drivers and targets;
- candidate and optional prior artifacts;
- target tier and authorization requirements;
- lifecycle and permission profiles;
- credential and test-data reference names;
- cleanup requirements;
- evidence requirements; and
- capability gaps or blocking questions.

It persists actions and handoffs using the existing revision-aware Protocol 2
workflow.

### 9.3 Generate

`generate` preserves an existing supported driver setup or performs the
authorized minimal bootstrap. It creates repository-native checks for selected
journeys without building, installing, launching, or executing the app.

Generated work ends `generated-unverified`.

Selectors prioritize stable accessibility identifiers and externally visible
accessibility labels. Coordinate-only actions, arbitrary sleeps, hidden
framework internals, and selectors derived solely from private implementation
structure are prohibited.

### 9.4 Verify prerequisites

Before `verify`, require:

- a valid current manifest revision;
- selected journey and check IDs;
- an explicitly selected compatible target;
- a supported configured driver;
- a candidate artifact or approved existing build command;
- required endpoint and credential references;
- target-tier and mutation authorization;
- a complete lifecycle and permission profile;
- test-data setup and cleanup paths; and
- evidence sanitization policy.

Missing prerequisites create a durable action or handoff. They do not trigger
speculative infrastructure changes.

### 9.5 Prepare app-scoped state

Verification may build through the approved existing command, then:

1. confirm target identity and capabilities;
2. install or select the approved candidate artifact;
3. establish the declared app-scoped state;
4. establish the required permission baseline;
5. apply authorized test-data setup; and
6. launch the app from the declared entry point.

A disposable virtual target may use its declared snapshot reset instead of
individual app-state operations.

### 9.6 Execute selected checks

Only manifest-selected checks run. Interactions are limited to visible UI,
public accessibility surfaces, supported OS-level user interactions, and
declared embedded WebViews.

Backgrounding, foregrounding, termination, relaunch, rotation, deep links, and
permission prompts run only when the selected lifecycle declares them and the
target proves support.

### 9.7 Evidence and cleanup

Execution records selected check IDs, manifest revision, driver and version,
platform, target reference, OS version, application artifact/build reference,
lifecycle events, outcomes, bounded retries, and sanitized artifact references.

Cleanup runs on success and every terminal failure path where it is safe. It
restores declared permissions and app state where supported, removes disposable
test data through its declared cleanup action, and records cleanup evidence.

A cleanup failure preserves earlier outcomes but blocks a successful run
completion claim.

### 9.8 Repair

`repair` requires a recorded high-confidence `test-defect`, remaining budget,
and an explicit allowed-path list. It may change generated mobile tests, mobile
test configuration, driver configuration, fixtures, and dedicated test-support
files.

It never changes application source, build or signing configuration, public
behavior, expected outcomes, production configuration, device provisioning, or
provider administration. Every repair returns to selected verification.

## 10. Lifecycle Requirements

### 10.1 Install and launch

The lifecycle records whether the app must be freshly installed, reused,
reinstalled, or upgraded. Driver defaults such as "first connected device" are
not sufficient target selection.

Launch verifies the declared app identifier and externally observable entry
state. A process start alone is not successful acceptance evidence.

### 10.2 Reset

Reset behavior distinguishes:

- app data and cache;
- app install state;
- app permissions;
- synthetic app-owned test data; and
- virtual-device snapshot state.

No lifecycle may use a vague `reset` command without declaring which state
classes it changes.

### 10.3 Background and foreground

Background and foreground checks declare the expected user-observable
continuity or restart behavior and a bounded duration. They do not use internal
process state as the acceptance oracle.

### 10.4 Deep links

Deep links must use declared application schemes, universal links, or app links
and non-secret payloads. The journey verifies the externally visible destination
and error behavior. Secret-bearing query strings or copied authentication
tokens are prohibited.

### 10.5 Permissions

Permission profiles declare:

- permission type;
- initial state;
- user action or target setup required;
- expected app behavior for grant, denial, or restriction;
- target support; and
- restoration action.

Camera, microphone, location, contacts, photos, notifications, biometrics, and
similar capabilities use synthetic or simulator-provided data where possible.
The skill never consumes personal real-device data merely because access is
available.

### 10.6 Upgrade

Upgrade is an optional lifecycle journey. It requires explicit `prior` and
`candidate` artifacts.

The flow:

1. installs the prior artifact;
2. creates only the minimum approved externally observable app state;
3. installs the candidate without clearing that state;
4. launches the candidate;
5. verifies supported user-visible post-upgrade behavior; and
6. performs normal cleanup.

Upgrade transitions are not automatically retried because replay may destroy
the retained state under test. Missing either artifact yields
`needs-clarification`.

## 11. Credential, Test-Data, and Evidence Safety

### 11.1 Credentials

Manifests, extensions, generated tests, deep links, evidence, and handoffs
contain secret-reference names only. Secret values are resolved at runtime from
approved providers and supplied through the narrowest supported driver or app
mechanism.

Secrets must not be typed into visible fields while unrestricted screenshots or
video are active. Evidence collection is suppressed, masked, or sanitized
around sensitive entry. The skill never searches device keychains, password
stores, browser storage, clipboard history, shell history, logs, or unrelated
files for credentials.

### 11.2 Test data

Use dedicated synthetic accounts, unique test namespaces, supported fixture
interfaces, or the existing shared database support capability. Database setup,
cleanup, and diagnostics remain auxiliary and never become mobile acceptance
oracles.

Personal contacts, photos, messages, health data, payment instruments,
production customer records, and unrelated app storage are prohibited as
fixtures.

### 11.3 Evidence

Mobile evidence may reference:

- screenshots;
- video;
- public accessibility snapshots;
- normalized driver results;
- lifecycle events;
- sanitized device and system logs;
- crash reports;
- install and cleanup results; and
- explicitly authorized sanitized network captures.

Artifacts remain outside the extension and are linked through core evidence
records.

Network capture is disabled by default and requires exact authorization. It is
diagnostic for a mobile journey and cannot replace externally observable UI
acceptance. Evidence collection must minimize unrelated apps, notifications,
status-bar data, personal content, identifiers, and secret exposure.

## 12. Environment and Production Safety

The shared target tiers remain authoritative:

| Tier | Mobile behavior |
| --- | --- |
| `local` | Dedicated simulator, emulator, or device; app-scoped mutations allowed within the declared lifecycle |
| `ephemeral` | Disposable virtual or remote target; declared snapshot reset may be allowed |
| `staging` | Explicit configured target, synthetic identity, and exact mutation authorization required |
| `production` | Explicitly configured, non-destructive observation on a dedicated device only |
| `unspecified` | No execution |

Production-connected app builds may launch and navigate only public or
read-only screens under an explicit allow-policy. The following are prohibited:

- account creation or account-state mutation;
- purchases, payments, messages, notifications, or external communications;
- backend data mutation;
- permission operations with external effects;
- production test-data setup or cleanup;
- customer data as fixture material; and
- any irreversible or third-party side effect.

Device-local launch and navigation state must still be cleaned up when
supported. A user approval cannot override a categorical production
prohibition.

Unexpected writes, target identity changes, personal-data exposure, credential
exposure, or unexplained device state stop the affected journey immediately.

## 13. Failure Handling

Failures are classified per selected check and lifecycle:

| Condition | Result |
| --- | --- |
| Installed-app boundary or ownership is ambiguous | `needs-clarification` |
| Target, credential, permission, capture, mutation, or bootstrap approval is missing | `authorization-required` |
| Driver or target cannot perform a required lifecycle operation | `capability-unavailable` |
| Installed `e2e.mobile` version is unsupported | `extension-incompatible` |
| Device disconnect, simulator/emulator failure, driver crash, signing/install failure, target drift, or infrastructure outage explains the failure | `environment` |
| Generated selector, wait, fixture, test support, or driver configuration is wrong with sufficient evidence | `test-defect` |
| Supported externally observable app behavior violates its expectation with sufficient evidence | `product-defect` |
| Evidence is incomplete, conflicting, stale, or cleanup cannot be verified | `inconclusive` |

The implementation maps these classifications to the existing Protocol 2
status and handoff vocabulary without changing core enums or meanings.

Retries are bounded by manifest budgets and permitted only for classified
transient environment or test failures. A retry never erases the original
attempt or evidence.

The following are never blindly replayed:

- destructive or state-losing setup;
- installs or uninstalls that could remove retained state;
- permission changes with external effects;
- upgrade transitions;
- real-device provisioning actions; and
- external side effects.

Independent platform journeys may continue only when they do not depend on the
failed state. A journey is verified only when every selected check succeeds and
required cleanup completes.

## 14. Packaging and Synchronization

The canonical mobile schema and catalog entry are sources of truth.
Synchronization produces:

- `e2e-mobile` with the Protocol 2 runtime, catalog helper, manifest schema,
  `e2e.mobile` schema, and a catalog containing only `e2e.mobile`;
- `e2e-testing` with web, service, and mobile schemas and catalog entries;
- the unchanged `e2e-web` projection containing only `e2e.web`; and
- the unchanged `e2e-service` projection containing only `e2e.service`.

The mobile skill bundles its shared workflow, safety, failure classification,
repair guardrails, Appium adapter, Maestro adapter, iOS profile, and Android
profile.

Packaging gates require byte-for-byte canonical schema equality, exact filtered
catalog ownership, release-native catalog discovery, standard-library-only
Protocol runtime behavior, and independent installation.

Repository documentation and installation guidance add the mobile skill without
removing or weakening v1/v2 behavior.

## 15. Testing Strategy

### 15.1 Protocol and packaging tests

Tests prove:

- strict `e2e.mobile@1.0` validation;
- exact extension ownership per bundle;
- valid application, driver, target, artifact, and lifecycle records;
- malformed mobile data fails typed validation;
- supported extension data can change across revisions;
- unsupported mobile versions report `extension-incompatible`;
- unknown extensions remain valid, preserved, and immutable;
- synchronized bundles use the canonical mobile schema; and
- no Protocol 2 core field, enum, or meaning changes.

### 15.2 Deterministic repository contracts

Contract tests enforce:

- mobile routing and embedded-WebView ownership;
- existing Appium and Maestro preservation;
- authorized bootstrap boundaries;
- protected application, build, signing, production, and device paths;
- mode outcomes and selected-check requirements;
- app-scoped cleanup;
- evidence sanitization;
- production refusal;
- bounded retry and repair; and
- durable failure actions and handoffs.

### 15.3 Hermetic mobile fixtures

Fixtures cover:

- native iOS;
- native Android;
- at least one cross-platform repository layout;
- existing Appium conventions;
- existing Maestro conventions; and
- greenfield mobile test setup.

Controlled driver and device shims expose deterministic simulator/emulator
capabilities and lifecycle outcomes. They cover install, launch, reset,
background, foreground, deep link, permission, upgrade, selected execution,
artifacts, cleanup, device failure, driver failure, and product behavior.

Fixture evidence is explicitly labeled. It validates workflow behavior but can
never substantiate a real-device or real-application verification claim.

### 15.4 Evaluation cases

Deterministic evaluator cases cover:

- Appium and Maestro setup preservation;
- authorized bootstrap and unauthorized-bootstrap refusal;
- iOS simulator and Android emulator generation for both drivers;
- selected verification with check-linked evidence;
- real and remote capability gating;
- native and embedded-WebView checks;
- optional prior-to-candidate upgrade;
- permission and app-state restoration;
- production mutation refusal;
- missing credentials, artifacts, or targets;
- product defect, test defect, environment failure, and inconclusive evidence;
- cleanup failure; and
- evidence and secret sanitization.

### 15.5 Behavioral host evaluations

Required Codex and Claude Code cases verify:

- orchestration routes installed-app journeys to `e2e-mobile`;
- both drivers produce repository-native generated work;
- mobile lifecycle decisions and capability gaps remain explicit;
- unsafe production, credential, permission, capture, and reset actions are
  refused;
- actions, handoffs, revisions, and outcomes remain durable; and
- resulting manifests validate as Protocol 2.

Paid host runs remain individually opt-in and require explicit reviewer
authorization.

### 15.6 Platform acceptance matrix

Before V3 exits, authorized environment-bound runs demonstrate:

| Driver | iOS simulator | Android emulator | Real or remote |
| --- | --- | --- | --- |
| Appium | Required | Required | One explicitly provisioned path required |
| Maestro | Required | Required | Capability-gated; not required for V3 exit |

Each run records the exact host, driver, adapter, operating-system, target, app
artifact, and command versions plus selected-check and cleanup evidence.
Unsupported combinations remain capability-gated and are not advertised.

## 16. Exclusions

- Mobile websites outside an installed application.
- Detox, Flutter `integration_test`, and other gray-box or
  implementation-coupled suites as supported V3 drivers.
- Coordination with web, service, or desktop execution units.
- Multi-device and multi-app composition.
- Device-farm account or infrastructure provisioning.
- Vendor-specific device-farm orchestration.
- Xcode, Android SDK, operating-system image, virtualization, or system-wide
  tool installation as ordinary bootstrap.
- Pairing, trusting, enrolling, rooting, jailbreaking, wiping, or generally
  administering real devices.
- Application source, build, signing, provisioning, public-contract, or
  production-configuration repair.
- Raw secret storage or discovery.
- Network evidence as a mobile acceptance oracle.
- Database state as a mobile acceptance oracle.
- Protocol 2 core migration.
- Fault injection and resilience profiles.

## 17. Acceptance Criteria

V3 is complete when:

1. `e2e-mobile` is independently installable and owns `e2e.mobile@1.0`.
2. `e2e-testing` routes installed iOS and Android app journeys to
   `e2e-mobile`.
3. Native and cross-platform repositories use the same black-box acceptance
   rules.
4. Appium and Maestro are first-class repository-native drivers with no
   automatic migration between them.
5. Existing supported driver conventions are preserved.
6. Greenfield bootstrap requires explicit authorization and changes only
   bounded test infrastructure.
7. iOS simulator and Android emulator behavior meets the deterministic baseline
   for both drivers.
8. Appium demonstrates one provisioned real-device or remote-device path.
9. Real and remote targets cannot execute without explicit provisioning,
   selection, and capability evidence.
10. App install, launch, reset, background/foreground, deep-link, permission,
    upgrade, and cleanup lifecycles are explicit and reproducible.
11. Upgrade journeys require separate prior and candidate artifacts and are not
    blindly replayed.
12. Whole-device real-device reset is prohibited.
13. Embedded WebViews remain mobile-owned while standalone mobile websites
    remain web-owned.
14. Credentials and sensitive device data remain outside manifests, generated
    tests, and unsanitized evidence.
15. Production-connected app verification is explicitly configured,
    non-destructive, and free of external side effects.
16. Selected checks produce revision-bound, target-bound, driver-specific,
    sanitized execution and cleanup evidence.
17. Fixture evidence cannot be mistaken for actual platform evidence.
18. Repair remains limited to tests, test configuration, fixtures, and
    dedicated test support.
19. The mobile extension requires no Protocol 2 core migration.
20. All v1 and v2 synchronization, packaging, protocol, safety, deterministic,
    and behavioral contracts continue to pass.
