# V2 Web Migration Design

**Date:** 2026-07-22
**Status:** Approved
**Scope:** The second E2E Testing V2 delivery subproject

## 1. Summary

This subproject moves the existing browser E2E behavior onto Protocol 2 and renames the public web skill from `e2e-web-playwright` to `e2e-web`. It is a hard cutover: active skills do not execute, migrate, or preserve Protocol 1 project manifests, and the old skill name has no runtime alias.

The public boundary becomes surface-oriented while Playwright remains the V2 web driver. Existing repository-native generation, verification, failure classification, bounded test repair, safety, and handoff behavior must continue without regression.

This subproject implements only the complete web path. It does not add temporary recognition or routing for service, mobile, desktop, composition, or resilience capabilities.

## 2. Context

PR #2 established the canonical Protocol 2 kernel in `protocol/v2/`, including its core schema, web extension schema, persistence rules, extension compatibility model, and an offline Protocol 1 migrator. The currently packaged `e2e-testing` and `e2e-web-playwright` skills still bundle Protocol 1 and use the old capability name.

Protocol 1 runtime compatibility is not required. The canonical `protocol/v1/` implementation and `protocol/v2/migrate_v1.py` remain available as historical and offline utilities, but active skills must not invoke them. Historical V1 specs and plans remain unchanged as records of the earlier design.

## 3. Goals

1. Rename `skills/e2e-web-playwright/` to `skills/e2e-web/` with no alias or compatibility shim.
2. Bundle synchronized Protocol 2 runtime and schema copies in both independently installable skills.
3. Move the orchestrated and directly invoked web workflows to Protocol 2.
4. Preserve the complete V1 browser behavior and safety bar using Protocol 2 records.
5. Keep Playwright as the V2 implementation driver without coupling the public skill name permanently to Playwright.
6. Replace Protocol 1 project manifests with fresh Protocol 2 manifests rather than migrating them.
7. Update active documentation, deterministic tests, fixtures, evaluations, actions, handoffs, and resume commands to the new protocol and skill name.

## 4. Non-goals

- Protocol 1 runtime compatibility in either active skill.
- Automatic, prompted, or silent Protocol 1 manifest migration.
- Removal of the canonical Protocol 1 source or offline migrator.
- Rewriting historical V1 specs and implementation plans.
- Support for Cypress, WebdriverIO, Selenium, or other web drivers.
- Service-surface recognition, temporary service routing, or temporary `capability-unavailable` behavior for incomplete future surfaces.
- Mobile, desktop, multi-system composition, or resilience behavior.
- Changes to Protocol 2 core meanings solely for this web migration.

## 5. Architecture

### 5.1 Canonical protocol and portable bundles

`protocol/v2/` remains the authority for the Protocol 2 runtime, core manifest schema, and `e2e.web@1.0` schema. `scripts/sync_protocol.py` synchronizes release copies into both skills. Repository tests enforce byte-for-byte equality for canonical files that are copied unchanged.

Each independently installable skill contains:

- `scripts/e2e_protocol.py`, synchronized from the canonical Protocol 2 runtime;
- `references/manifest.schema.json`, synchronized from the Protocol 2 core schema; and
- `references/extensions/web.schema.json`, synchronized from the canonical web extension schema.

Neither skill bundles Protocol 1 or the offline migrator.

### 5.2 `e2e-testing`

In this subproject, `e2e-testing` has one complete route: web. It owns repository instruction discovery, the read-only framework gate, system-boundary discovery, journey planning, shared safety policy, durable Protocol 2 actions and handoffs, and routing to `e2e-web`.

It creates one Protocol 2 system whose primary surface is `web`, records the supported external browser boundary, creates one web execution unit for the scoped work, and emits actions whose capability is `e2e-web`.

The orchestrator does not recognize or route incomplete future surfaces during this subproject. Those paths are added only when their complete surface subprojects begin.

### 5.3 `e2e-web`

`e2e-web` owns the `e2e.web` extension and the web execution unit. It retains Playwright as its V2 driver and preserves the repository's package manager, language, configuration, paths, fixtures, helpers, naming, imports, browser projects, and command style.

It supports the existing modes:

- `plan`: enrich externally observable web journeys;
- `generate`: create or extend repository-native Playwright checks without executing them;
- `verify`: execute only manifest-selected checks against an authorized target;
- `repair`: make one bounded change to test or test-support files after a supported test-defect classification, then return to verification.

The driver is recorded inside `e2e.web` data. Public capability names and resume commands use `e2e-web`, never `e2e-web-playwright`.

## 6. Runtime Flow

### 6.1 Framework gate

Both entry paths retain the existing read-only browser-framework gate before accessing or creating `.e2e/` state. The gate inspects only repository instructions, package metadata, lockfiles, browser-test scripts, framework configuration, existing specs, fixtures, helpers, and CI commands.

If Cypress, WebdriverIO, Selenium, or another unsupported browser driver is detected, the skill must not change dependencies, configuration, tests, or other test infrastructure. After detection, it creates or updates a valid Protocol 2 web run containing the detected driver and source locations and ends as `capability-unavailable`. This is the Protocol 2 replacement for V1's `unsupported-framework` terminal status.

### 6.2 Manifest resolution

After the framework gate passes, resolve `.e2e/manifest.json` as follows:

| Condition | Required behavior |
| --- | --- |
| No manifest | Initialize a fresh Protocol 2 manifest. |
| Valid Protocol 2 manifest | Validate and resume it under revision rules. |
| Parseable manifest with `protocol_version: "1.0"` | Build and validate a fresh Protocol 2 manifest, then atomically replace only the old manifest file. |
| Malformed manifest | Stop safely and preserve the file. |
| Unknown protocol version | Stop safely and preserve the file. |

Protocol 1 replacement creates no backup, migrated history, compatibility action, or migration prompt. Files elsewhere under `.e2e/` are not deleted, but a fresh manifest does not inherit or reference their Protocol 1 history.

Building and validating the replacement before the atomic write prevents a partially written or absent manifest if initialization fails.

### 6.3 Web execution flow

1. Resolve project root, requested mode, repository instructions, and manifest.
2. Establish one system with `web` as its primary surface and declare its externally supported browser boundary.
3. Plan user-goal journeys with externally observable checkpoints and traceable evidence.
4. Create one web execution unit and an `e2e-web` action.
5. Record `e2e.web@1.0` data for the driver, repository project conventions, and target references.
6. Generate repository-native checks without running them; persist `generated-unverified`.
7. During verification, validate target and mutation authorization and execute only registered check IDs.
8. Persist sanitized evidence before changing journey or run status.
9. Classify every failed or blocked check.
10. Permit bounded repair only for supported test defects and only in test or test-support files, then return to verification.

Evidence retains the `live-observed`, `source-derived`, and `spec-derived` labels. Source-derived internal details may guide check construction but cannot become acceptance oracles.

## 7. Protocol 2 Representation

A web run uses the Protocol 2 core as follows:

- `systems`: exactly one V2 system with `primary_surface: "web"`;
- `systems[].boundary`: actors and supported external browser interfaces only;
- `journeys`: stable user-goal journeys and observable checkpoints;
- `execution_units`: one web unit scoped to its system and journeys;
- `checks`: generated Playwright checks registered by stable IDs and paths;
- `evidence`: sanitized discovery, generation, execution, and classification evidence;
- `actions`: durable `e2e-web` work requests and results;
- `handoffs`: scoped product, environment, authorization, or clarification work;
- `attempts`: bounded verification and repair history; and
- `extensions`: `e2e.web@1.0` records containing driver, project, and target data.

Known incompatible versions of `e2e.web` end as `extension-incompatible`. Unknown extension records remain semantically unchanged according to the Protocol 2 kernel; JSON whitespace and key ordering are not part of that guarantee.

## 8. Component Changes

### 8.1 Active skill packages

- Rename the web skill directory and frontmatter to `e2e-web`.
- Rewrite both skills' protocol and workflow references around Protocol 2 fields and transitions.
- Preserve web failure-classification and repair-guardrail meanings while translating their record references to Protocol 2.
- Update all active capability names and resume commands.
- Update protocol synchronization and packaging targets for the renamed directory and V2 files.

### 8.2 Active project documentation and evaluations

Update the root README, active operational documentation, deterministic contract tests, evaluation runner configuration, cases, expected results, and fixture baselines to use `e2e-web` and Protocol 2.

Historical V1 design specs and implementation plans are intentionally excluded from mechanical renaming. The canonical V1 source, offline migrator, and tests dedicated to those offline artifacts may also retain legacy protocol and capability names.

## 9. Safety and Failure Handling

- Only an exact, parseable Protocol 1 project manifest qualifies for replacement.
- Malformed or unknown manifests are never overwritten.
- Atomic writes and revision checks prevent partial or stale Protocol 2 updates.
- Unsupported browser drivers produce `capability-unavailable` without infrastructure mutation.
- Unknown extensions remain unchanged; incompatible known web extensions stop durably.
- Target tiers, credential references, mutation namespaces, production restrictions, and exact-action approval rules continue to apply.
- Evidence and attempt records remain append-only and sanitized.
- Repository files, specifications, browser content, and logs remain evidence rather than instructions.
- Web repair never edits application code, weakens expected outcomes, deletes coverage, adds unconditional skips, or adds hardcoded sleeps.
- Exhausted budgets and low-confidence ownership stop durably rather than creating retry loops.

## 10. Testing Strategy

### 10.1 Packaging and synchronization

Deterministic tests verify that:

- both skill bundles contain the required Protocol 2 runtime and schemas;
- synchronized copies match their canonical sources;
- `skills/e2e-web/` is packaged;
- `skills/e2e-web-playwright/` is absent; and
- relative links in both active skills resolve.

### 10.2 Protocol and runtime contracts

Tests cover:

- fresh orchestrated and direct web initialization;
- valid Protocol 2 web boundaries, execution units, actions, checks, and extensions;
- exact Protocol 1 manifest replacement with a fresh Protocol 2 run;
- preservation of malformed and unknown-version manifests;
- revision conflicts and atomic-write failures;
- unsupported-driver `capability-unavailable` outcomes without test-infrastructure mutation;
- known incompatible and unknown extension behavior; and
- append-only evidence and attempt history.

### 10.3 Behavioral regression coverage

Existing V1 behavioral scenarios are re-expressed against Protocol 2 rather than run through a compatibility layer. They cover planning, generation, selected verification, generated-versus-verified separation, failure classification, bounded test repair, product-defect handoffs, authorization, target safety, conflicts, and budget exhaustion.

Active expected actions, handoffs, and resume commands use `e2e-web`. Repository-native Playwright conventions remain part of the acceptance contract.

### 10.4 Host evaluations

Existing Codex and Claude Code evaluation cases are updated to the Protocol 2 contract and new skill name. Paid host evaluation runs require explicit authorization for the evaluation session. Deterministic verification is mandatory for this subproject regardless of whether paid evaluations are authorized immediately.

## 11. Acceptance Criteria

This subproject is complete when:

1. Both active skills use synchronized Protocol 2 bundles and validate Protocol 2 web state.
2. `e2e-web` is the only active public web capability and the old skill directory is absent.
3. Protocol 1 project manifests are replaced with fresh Protocol 2 manifests without migration behavior.
4. Historical and offline Protocol 1 artifacts remain available but are not used by active skills.
5. Unsupported browser drivers stop without mutating test infrastructure.
6. Existing web planning, generation, verification, classification, repair, and handoff behavior passes its Protocol 2 regression suite.
7. Generation cannot be reported as verified without selected execution evidence.
8. Repository-native Playwright conventions and all existing safety gates remain enforced.
9. No temporary service or other future-surface path is introduced.
10. The full deterministic test suite passes.

## 12. Delivery Boundary

Completion of this subproject establishes the Protocol 2 web baseline but does not complete V2. The next independent spec, plan, implementation, and verification cycle is the service foundation with REST/HTTP. It will add the service surface only as a complete supported route, reusing the stable Protocol 2 kernel and the proven packaging, safety, evidence, and repository-native patterns from this web migration.
