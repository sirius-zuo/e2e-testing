# E2E Testing Roadmap

## Purpose

This roadmap makes future work explicit. Each version has a defined responsibility, prerequisites, exclusions, deliverables, and exit criteria. A later design may refine its version, but unfinished work must not disappear into an unspecified “future extension.”

## Shared direction

E2E tests treat a system as a black box behind supported external boundaries. Internal implementation details belong to unit and integration testing.

The roadmap distinguishes:

- **Interaction surfaces:** browser UI, service interface, mobile UI, and desktop UI.
- **Drivers:** technologies used within a surface, such as Playwright, REST, gRPC, or a mobile automation driver.
- **Composition:** one journey coordinating multiple systems or surfaces.
- **Profiles:** controlled conditions applied around a journey, such as infrastructure faults.

Protocol 2 is the stable kernel for V2 through V6. New surfaces, composition behavior, and resilience data use typed, versioned extensions without repurposing existing core fields.

## V1 — Web foundation

### Purpose

Prove the portable Agent Skill architecture with browser E2E testing.

### Deliverables

- Framework-neutral `e2e-testing` orchestration.
- Playwright generation, verification, classification, and bounded repair.
- Protocol 1 durable manifests, evidence, actions, and handoffs.
- Deterministic fixtures and Codex/Claude Code evaluation support.

### Exclusions

- Non-web surfaces.
- Cross-surface composition.
- Application-code repair.

### Exit criteria

- Generated work is never reported as verified without execution evidence.
- Existing Playwright conventions are preserved.
- Unsupported browser frameworks do not trigger infrastructure mutation.
- Repair remains test-only and bounded.

## V2 — Service interfaces and Protocol 2

### Purpose

Add black-box service-interface E2E testing and establish the long-lived protocol foundation for all later versions.

### Prerequisites

- V1 web workflows and safety behavior are stable.
- V1 manifests have deterministic validation and fresh Protocol 2 replacement behavior.

### Deliverables

- Protocol 2 stable kernel and typed surface extensions.
- Explicit, validated system boundaries.
- Fresh Protocol 2 state replacement of exact Protocol 1 manifests.
- Offline historical migration utility for archival of legacy manifests.
- Rename `e2e-web-playwright` to `e2e-web` and migrate it to Protocol 2.
- New `e2e-service` surface skill.
- Repository-native REST, GraphQL, gRPC, WebSocket, queue, and event-stream modules.
- Multi-protocol journeys within one declared service-system boundary.
- Authorized database setup, cleanup, and diagnostic observation as auxiliary capabilities only.
- Full deterministic and Codex/Claude Code evaluation coverage for every shipped protocol module.

### Exclusions

- Mobile and desktop applications.
- Multi-system or multi-surface composition.
- Fault injection and topology-aware resilience control.
- Database state as an E2E acceptance oracle.
- Protocol 1 runtime compatibility or active history migration.

### Exit criteria

- Active skills never invoke the offline migrator and replace exact Protocol 1 state only with explicit authorization.
- Web and service runs use the same Protocol 2 kernel.
- Every service protocol module meets the V1 quality bar.
- Public-versus-internal interface ambiguity is handled explicitly.
- Unknown extension data is preserved.
- Protocol 2 core semantics are suitable for the documented V3 through V6 extension path.

### Delivery decomposition

V2 is one release delivering one atomic `e2e-service` skill with six protocol modules (HTTP, GraphQL, gRPC, WebSocket, queue, stream), multi-protocol integration, and shared cross-surface database support. Database support is never an acceptance oracle. Protocol 2 kernel and offline historical migration utility are delivered alongside. All are required before V2 is complete.

## V3 — Mobile UI

### Purpose

Add black-box E2E testing for installed iOS and Android applications.

### Prerequisites

- Protocol 2 extension ownership and compatibility rules are proven by both web and service surfaces.
- Mobile target authorization can be represented without changing Protocol 2 core semantics.

### Required design work

- Select supported mobile automation drivers based on current ecosystem evidence.
- Define real-device, simulator, and emulator target policy.
- Define application install, launch, reset, backgrounding, deep-link, permission, and upgrade lifecycles.
- Define mobile artifact, accessibility, network, and platform evidence.
- Define safe credential and test-data handling on devices.

### Deliverables

- An independently installable mobile surface skill.
- A typed mobile extension.
- Repository-native mobile test generation and execution.
- Deterministic fixtures for iOS and Android lifecycle behavior.
- Required behavioral host evaluations.

### Exclusions

- Mobile websites, which remain in the web surface.
- Direct coordination with service, web, or desktop execution units.
- Multi-device composition.

### Exit criteria

- Generated mobile checks remain externally observable and implementation-independent.
- Device state and permissions are reproducible and safely cleaned up.
- The mobile extension requires no Protocol 2 core migration.
- Supported platforms meet the established packaging, safety, and behavioral acceptance bar.

## V4 — Desktop UI

### Purpose

Add black-box E2E testing for installed desktop applications, including native applications and Electron.

### Prerequisites

- Protocol 2 has supported three atomic surfaces without changing core meanings.
- Desktop target and operating-system authorization can be represented through extensions.

### Required design work

- Select supported desktop automation drivers based on current ecosystem evidence.
- Define application install, launch, update, reset, and teardown lifecycles.
- Define operating-system session, window, permission, filesystem, notification, and protocol-handler boundaries.
- Define platform-specific evidence and safe artifact handling.

### Deliverables

- An independently installable desktop surface skill.
- A typed desktop extension.
- Repository-native native-desktop and Electron workflows.
- Deterministic fixtures across supported operating systems.
- Required behavioral host evaluations.

### Exclusions

- Browser-rendered sites, even when used from a desktop computer.
- Cross-surface and cross-system orchestration.
- Unbounded control of the user's general desktop session.

### Exit criteria

- Desktop checks operate within an explicit application and OS-session boundary.
- Lifecycle and permission handling are deterministic and reversible.
- The desktop extension requires no Protocol 2 core migration.
- Supported platforms meet the established packaging, safety, and behavioral acceptance bar.

## V5 — Multi-system and multi-surface composition

### Purpose

Compose stable atomic execution units into full-stack and multi-system journeys.

### Prerequisites

- Web, service, mobile, and desktop surface contracts are stable.
- Each surface produces compatible core evidence, actions, handoffs, and statuses.
- Identity and authorization can be scoped across systems without sharing secret values.

### Required design work

- Define execution-unit dependency ordering and concurrency.
- Define actor identity and context transfer without leaking credentials.
- Define evidence correlation and causal ordering.
- Define partial success, compensation, cleanup, and resumption.
- Define ownership when failures occur at a boundary between systems.
- Define composition budgets and human approval gates.

### Deliverables

- A typed composition extension using existing Protocol 2 systems and execution units.
- Full-stack journeys spanning supported surfaces.
- Multi-system journeys spanning independently deployed systems through public interfaces.
- Deterministic partial-failure, resume, and evidence-correlation fixtures.
- Required behavioral host evaluations.

### Exclusions

- Infrastructure fault injection.
- Treating private cross-service implementation details as acceptance contracts.
- Replacing surface-owned execution logic with a monolithic composition runner.

### Exit criteria

- Atomic surface skills remain independently invocable.
- Composed journeys preserve per-unit and aggregate status without hiding partial failure.
- Interrupted compositions resume without replaying completed unsafe actions.
- Composition requires no Protocol 2 core migration.

## V6 — Resilience profiles

### Purpose

Evaluate externally observable system behavior while controlled infrastructure faults are applied around suitable atomic or composed E2E journeys.

### Prerequisites

- Atomic and composed journeys have deterministic steady-state outcomes.
- Environment control can be isolated from acceptance-oracle logic.
- Fault authorization, blast radius, and rollback can be represented safely.

### Required design work

- Define steady-state hypotheses and externally observable outcomes.
- Define versioned fault-controller capabilities.
- Define node, process, network, dependency, and resource-pressure fault classes.
- Define blast-radius policy, target-tier restrictions, abort conditions, and rollback guarantees.
- Define evidence correlation between faults and E2E outcomes.

### Deliverables

- A typed resilience-profile extension.
- Authorized, bounded fault scenarios applied around existing journeys.
- Deterministic fault-controller fixtures and rollback validation.
- Evidence linking fault timing to externally observable behavior.
- Required behavioral host evaluations.

### Exclusions

- Using internal implementation state as the journey's acceptance oracle.
- Unbounded chaos, production mutation by default, or faults without verified rollback.
- Reimplementing the atomic surface or composition layers.

### Exit criteria

- Fault controllers cannot run without explicit target and blast-radius authorization.
- Abort and rollback behavior is deterministic and verified.
- Acceptance remains based on supported external boundaries.
- Resilience profiles require no Protocol 2 core migration.

## Roadmap governance

Before implementation of V3 or later begins:

1. Write and approve a version-specific design.
2. Revalidate assumptions against the then-current ecosystem and project state.
3. Confirm the work fits the Protocol 2 extension model.
4. Update this roadmap when scope changes, preserving an explicit record of deferred or removed work.
5. Require the same deterministic, packaging, safety, and behavioral acceptance bar established by earlier versions.
