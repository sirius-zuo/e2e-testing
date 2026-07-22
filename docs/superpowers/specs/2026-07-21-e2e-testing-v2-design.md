# E2E Testing V2 Design

**Date:** 2026-07-21
**Status:** Approved for implementation planning
**Project:** `e2e-testing`

## 1. Purpose

V2 expands the project from browser-only end-to-end testing to black-box testing through supported service interfaces. It also replaces Protocol 1 with a long-lived Protocol 2 kernel intended to support the planned V2 through V6 evolution without repeated core-manifest migrations.

V2 delivers:

1. A stable Protocol 2 kernel with versioned surface extensions.
2. An explicit, validated system-boundary model.
3. A lossless Protocol 1 to Protocol 2 migration path.
4. Migration of the existing orchestrator and web adapter to Protocol 2.
5. Renaming `e2e-web-playwright` to the surface-oriented `e2e-web`.
6. A new `e2e-service` skill for repository-native service-interface E2E testing.
7. Service protocol modules for REST, GraphQL, gRPC, WebSockets, queues, and event streams.
8. A committed V1 through V6 roadmap with explicit prerequisites, exclusions, deliverables, and exit criteria.

## 2. Governing Principle

E2E tests treat the system as a black box behind supported external boundaries. Internal implementation details belong to unit and integration testing.

Source code, schemas, repository configuration, and authorized runtime inspection may be used as discovery evidence. They may identify how to start the system, locate a public contract, or prepare controlled data. Generated checks must not couple their acceptance criteria to private functions, internal modules, database layouts, or internal-only messaging.

An interaction technology is not automatically public or internal. A Kafka topic, for example, is a supported external boundary only when publishing or consuming it is part of the system's declared product contract. The same technology used as implementation plumbing remains outside the E2E acceptance boundary.

## 3. Scope

### 3.1 Included in V2

- Protocol 2 core schema, validators, transitions, and utilities.
- Typed, versioned extension records owned by surface capabilities.
- Explicit system-boundary discovery and validation.
- One system and one primary interaction surface per V2 run.
- The `web` and `service` surfaces.
- Lossless migration of Protocol 1 manifests.
- Migration of existing browser functionality to `e2e-web` and Protocol 2.
- Repository-native service-interface planning, generation, verification, classification, and bounded test repair.
- REST, GraphQL, gRPC, WebSocket, queue, and event-stream support.
- Multi-protocol journeys within one declared service-system boundary.
- Optional database setup, cleanup, and diagnostic observation under authorization.
- Deterministic validation and behavioral evaluation on Codex and Claude Code.
- A durable roadmap for V1 through V6.

### 3.2 Deferred

- Installed mobile application testing: V3.
- Installed desktop application testing: V4.
- Multi-system and multi-surface composition: V5.
- Controlled topology-aware resilience profiles: V6.
- Browser drivers other than Playwright.
- Mandatory vendor-specific packaging or routing.

### 3.3 Non-goals

- Backward runtime compatibility with Protocol 1.
- Silent Protocol 1 manifest upgrades.
- Treating transports or protocols as execution surfaces.
- Treating databases or internal messaging as E2E acceptance oracles.
- Application-code repair.
- Direct validation of private implementation details.
- Fault injection or resilience orchestration in V2.
- Cross-system or cross-surface journey coordination in V2.

## 4. Taxonomy

Protocol 2 distinguishes three concepts that V1 future-work notes did not separate clearly:

- **Interaction surface:** where an external actor controls or observes the system.
- **Protocol or driver:** how an interaction crosses that surface.
- **Topology or profile:** the environment shape or conditions under which a journey runs.

The planned atomic interaction surfaces are:

- `web`: a browser-rendered application or site.
- `service`: a supported machine-facing service interface.
- `mobile`: an installed mobile application controlled through a device or emulator.
- `desktop`: an installed desktop application controlled through an operating-system session.

REST, GraphQL, gRPC, WebSockets, queues, and event streams are drivers within the `service` surface. Playwright is a driver within the `web` surface. Full-stack behavior is composition, not a surface. Distributed deployment is a topology; multi-system behavior belongs to composition, while controlled faults belong to a resilience profile.

## 5. Architecture

V2 uses a stable Protocol 2 kernel with typed, versioned surface extensions.

### 5.1 `e2e-testing`

The primary surface-neutral orchestrator:

- resolves the project, mode, target, and repository instructions;
- detects or migrates an existing manifest;
- discovers and validates the system boundary;
- classifies the primary interaction surface;
- applies shared safety and mutation policy;
- creates durable Protocol 2 actions and handoffs; and
- routes work to the matching surface capability.

### 5.2 `e2e-web`

The renamed successor to `e2e-web-playwright`:

- owns the `web` surface extension;
- retains Playwright as the V2 execution driver;
- preserves existing project Playwright conventions;
- supports planning, generation, verification, classification, and bounded test repair; and
- does not imply that the public skill boundary is permanently coupled to Playwright.

Other web drivers are future work and are not claimed by V2.

### 5.3 `e2e-service`

The new service-interface surface skill:

- owns the `service` surface extension;
- treats the declared system as a black box;
- preserves repository-native language, package manager, test runner, clients, fixtures, and conventions;
- loads guidance only for protocols declared as supported public interfaces;
- permits multiple public protocols in one service journey; and
- applies shared service authentication, data-lifecycle, evidence, timing, and repair rules.

Its progressively disclosed protocol modules cover:

- REST and general HTTP;
- GraphQL queries, mutations, and subscriptions;
- unary and streaming gRPC;
- WebSocket sessions;
- queue publishing and consumption; and
- event-stream production and consumption.

These modules are internal components of `e2e-service`, not independently installable surface skills.

### 5.4 Shared protocol and tooling

`protocol/v2/` contains the canonical kernel schema, deterministic validator, transition rules, revision logic, extension compatibility checks, and migration support. Skills that must remain independently installable bundle synchronized release copies, with repository tests enforcing equality.

## 6. Protocol 2 Model

Protocol 2 contains a strict surface-neutral core and namespaced surface extensions.

### 6.1 Stable core records

- `run`: run identity, mode, autonomy policy, revision, aggregate status, and timestamps.
- `systems[]`: systems under test, declared boundaries, actors, authorized targets, and public interfaces.
- `journeys[]`: externally observable goals, checkpoints, risks, source evidence, and status.
- `execution_units[]`: routable units declaring a system, surface, adapter capability, and extension reference.
- `checks[]`: executable artifacts linked to journeys and execution units.
- `evidence[]`: immutable discovery, execution, artifact, classification, and environment records.
- `actions[]`: ordered resumable work.
- `handoffs[]`: external capability requests and results.
- `authorizations[]`: explicit target, credential, and mutation authority.
- `attempts[]`: bounded execution and repair history.
- `extensions`: namespaced, versioned surface-specific records.

Every durable object has a stable ID. History and evidence are append-only. A mutating operation consumes a known revision and atomically writes the next revision.

### 6.2 Structural readiness for later versions

The Protocol 2 kernel permits multiple systems and execution units. V2 policy constrains a run to exactly one system and one primary surface. V5 may relax that policy and add optional composition extension data without changing existing core meanings.

Core fields remain additive through V6. An existing field's meaning must not be repurposed. A core migration is justified only when a shared invariant cannot be preserved.

### 6.3 Extension contract

Every extension record declares:

- a namespace;
- an extension schema version;
- its owning capability; and
- its typed data.

Adapters declare supported Protocol 2 and extension-version ranges. Unknown extension records are preserved unchanged. When no installed capability supports an extension, the result is `capability-unavailable`; the manifest is not rejected solely for containing future extension data.

Extension evolution should be additive when possible. A surface-specific migration affects that extension's records rather than unrelated runs.

## 7. System Boundary

A validated system boundary is a precondition for generation. It records:

- the system under test;
- external actors;
- supported public interfaces and their evidence;
- authorized targets;
- allowed mutation classes and test-data namespace; and
- explicit uncertainties that affect journey planning.

The skill may derive the boundary from authoritative repository evidence when unambiguous. If it cannot determine whether an interface is public or internal, it marks affected journeys `needs-clarification` and continues independent work.

The number of services, processes, containers, databases, or queues inside the system does not determine whether a test is E2E. An E2E check crosses a supported external boundary and evaluates an externally observable result. Internal topology remains hidden unless a later authorized profile deliberately controls it.

## 8. Operating Modes and Data Flow

V2 retains `plan`, `generate`, `verify`, and `repair`, with `generate` as the default and auto as an orchestration policy.

1. Resolve the project, requested mode, repository instructions, and manifest.
2. Require explicit migration when the manifest uses Protocol 1.
3. Perform read-only discovery of the system, actors, public interfaces, repository-native tooling, and target policy.
4. Create or validate the Protocol 2 system boundary.
5. Plan journeys around external goals and observable checkpoints.
6. Create one V2 execution unit and route it to `e2e-web` or `e2e-service`.
7. Load only the driver modules required by the declared public interfaces.
8. Generate repository-native checks without executing them; record `generated-unverified`.
9. During verification, validate authorization and execute only registered checks.
10. Atomically persist sanitized evidence before changing journey or run status.
11. Classify every failure.
12. Repair only test and support files when a supported test defect and remaining budget permit it, then return to verification.

Evidence keeps the V1 labels `live-observed`, `source-derived`, and `spec-derived`. Source-derived evidence may guide generation but cannot make internal state an acceptance criterion.

## 9. Failure Classification and Handoffs

V2 retains these primary outcomes:

- `test-defect`
- `product-defect`
- `environment-failure`
- `requirements-conflict`
- `authorization-required`
- `inconclusive`

A product defect creates a scoped product-fix handoff and never authorizes application-code edits by an E2E surface skill. A test defect permits bounded edits to test and support files only. Environment and authorization failures create their respective handoffs. Low-confidence ownership or exhausted budgets end durably as `blocked`.

Unknown protocols or missing drivers produce `capability-unavailable`. Unsupported extension versions produce `extension-incompatible`. Revision conflicts preserve stale results as evidence but do not apply their state transitions.

## 10. Safety and Mutation Policy

### 10.1 Target tiers

- Local and ephemeral targets permit scoped, reversible test-data creation and cleanup within a declared namespace.
- Staging requires explicit target authorization and allowed mutation classes.
- Production permits non-mutating observation only.

Always prohibited:

- irreversible deletion;
- real payments;
- uncontrolled event publication;
- privilege escalation;
- writes outside the test namespace; and
- mutation whose cleanup or blast radius cannot be bounded.

### 10.2 Database access

Database access is optional supporting infrastructure, never an E2E surface or acceptance oracle. Under explicit authorization it may be used for:

- controlled fixture setup;
- namespaced seeding;
- cleanup; and
- diagnostic observation during failure classification.

Database state must not determine journey pass or fail. Success criteria must be observable through a supported external interface.

### 10.3 Secrets and artifacts

Manifests and artifacts may store secret-reference names but never secret values. Commands, connection details, message payloads, traces, logs, screenshots, and session artifacts must be sanitized. Artifacts should be content-addressed where practical and referenced instead of embedded.

## 11. Protocol 1 Migration

V2 does not execute Protocol 1 manifests directly. The migration utility performs an explicit, lossless conversion:

1. Validate the source Protocol 1 manifest.
2. Preserve an immutable copy or integrity-addressed reference as migration evidence.
3. Preserve all stable IDs, action history, evidence, budgets, handoffs, statuses, and verification outcomes.
4. Translate the web project and target into Protocol 2 system-boundary, execution-unit, check, and web-extension records.
5. Validate the complete Protocol 2 result.
6. Atomically publish the migrated manifest only after validation succeeds.

A failed migration leaves the source untouched and writes diagnostics separately. Repeating migration against the same source must yield an equivalent Protocol 2 state rather than duplicate records.

## 12. Validation Strategy

### 12.1 Deterministic validation

Tests cover:

- Protocol 2 schema and semantic validation;
- legal state transitions and revision conflicts;
- atomic writes and rollback behavior;
- extension registration and version ranges;
- preservation of unknown extensions;
- V2's one-system and one-surface policy;
- lossless, repeatable Protocol 1 migration;
- secret redaction and artifact integrity;
- synchronized packaged protocol copies; and
- existing web behavior after migration and renaming.

### 12.2 Service fixtures

The deterministic fixture matrix includes:

1. Repository-native REST and general HTTP.
2. GraphQL queries, mutations, and subscriptions.
3. Unary and streaming gRPC.
4. WebSocket session behavior.
5. Queue publishing and consumption contracts.
6. Event-stream production, consumption, offsets, and bounded waiting.
7. A multi-protocol journey within one declared system boundary.
8. Ambiguous public-versus-internal interface evidence.
9. Missing credentials and forbidden target mutation.
10. Authorized fixture setup and cleanup.
11. Database diagnostics that support classification but cannot determine pass or fail.
12. Repairable test defects.
13. Product-defect handoffs.
14. Environment failures and exhausted budgets.
15. Unknown and unsupported extension versions.

### 12.3 Behavioral hosts

Every shipped service protocol module must meet the same packaging, safety, deterministic, and behavioral acceptance bar. Codex and Claude Code remain required evaluation hosts. Host evaluations consume paid model usage and run only after explicit authorization for that evaluation session.

## 13. Acceptance Criteria

V2 is complete when:

- Protocol 2 core and extension contracts pass deterministic validation.
- Existing Protocol 1 web fixtures migrate losslessly.
- `e2e-web` provides the existing verified V1 web behavior on Protocol 2.
- `e2e-service` supports all six declared protocol modules at the full acceptance bar.
- A service journey may use multiple declared public protocols within one black-box system boundary.
- Internal interfaces and database state cannot become acceptance oracles.
- Repository-native tooling and conventions are preserved.
- Generated checks remain `generated-unverified` until selected execution evidence exists.
- Target mutation follows the tiered policy.
- Unknown extension data survives validation and resumption.
- Interrupted work resumes without duplicating completed records.
- The V1 through V6 roadmap is committed and consistent with the implemented Protocol 2 extension model.

## 14. Delivery Decomposition

This document is the V2 umbrella architecture. V2 is too large for one safe implementation plan, so delivery is decomposed into dependent subprojects. Every subproject receives a focused spec, plan, implementation, and verification cycle. Completion of an early subproject does not reduce the V2 release acceptance criteria.

The required order is:

1. **Protocol 2 kernel and lossless migration:** specify and test the core, extensions, compatibility rules, and Protocol 1 migrator. This is the first implementation-planning target.
2. **Web migration:** migrate the orchestrator and browser behavior, including the `e2e-web` rename, without regressing V1 acceptance behavior.
3. **Service foundation and REST/HTTP:** establish the shared black-box workflow, repository-native execution contract, safety rules, and first driver.
4. **GraphQL driver:** add query, mutation, and subscription behavior against the proven service foundation.
5. **gRPC driver:** add unary and streaming RPC behavior.
6. **WebSocket driver:** add session lifecycle and realtime behavior.
7. **Queue driver:** add public publish/consume contract behavior.
8. **Event-stream driver:** add public production, consumption, offset, and bounded-wait behavior.
9. **Multi-protocol and release integration:** validate journeys using several public protocols, complete failure workflows, run authorized cross-host evaluations, and reconcile the release with the roadmap.

All nine subprojects are required for V2. Protocol drivers after REST/HTTP may be developed in parallel only after the service foundation and their focused designs are approved. Detailed tasks belong to each subproject's implementation plan.
