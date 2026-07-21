# E2E Testing Agent Skills Design

**Date:** 2026-07-20
**Status:** Approved for implementation planning
**Project:** `e2e-testing`

## 1. Purpose

Build a portable family of Agent Skills that plans, generates, verifies, and repairs end-to-end tests. The first release provides a framework-neutral orchestrator and a production-quality Playwright adapter. Later domain and framework adapters integrate through the same versioned artifact protocol without requiring changes to the existing skills.

The skills support two operating styles:

- **Explicit:** a person invokes a specific mode and reviews its result.
- **Auto:** an external loop engine advances stages by reading machine-readable outcomes and capability handoffs.

Generation is the default mode. Generated tests are always marked unverified until execution evidence proves otherwise.

## 2. Design Principles

- Follow the open Agent Skills `SKILL.md` format and avoid mandatory vendor extensions.
- Keep orchestration framework-neutral and framework behavior adapter-local.
- Use durable files, not conversational memory, as the integration boundary.
- Make adapters independently invocable and resumable.
- Separate generation from verification and repair.
- Preserve repository conventions and existing test infrastructure.
- Never hide application defects by weakening tests.
- Continue unaffected work when one journey is blocked.
- Apply progressive disclosure so irrelevant framework guidance is not loaded.
- Prefer deterministic validation for schemas, transitions, budgets, and redaction.

## 3. Scope

### 3.1 Version 1

Version 1 includes:

1. `e2e-testing`: the framework-neutral orchestrator and primary entry point.
2. `e2e-web-playwright`: an autonomous Playwright adapter.
3. A versioned JSON manifest protocol.
4. Human-readable test plans and persisted execution evidence.
5. Explicit and auto workflows.
6. New-suite creation and existing-suite maintenance.
7. Behavioral portability evaluation on Codex and Claude Code.

### 3.2 Future extensions

Future adapters may include:

- `e2e-web-cypress`
- `e2e-web-webdriverio`
- `e2e-web-selenium`
- Native-mobile adapters such as Appium
- API, desktop, and distributed-system adapters

These are extension points only in version 1. Version 1 does not create placeholder skills or claim support for them.

### 3.3 Non-goals

- Dynamic adapter discovery as a requirement
- Mandatory skill-to-skill invocation
- Vendor-specific model routing in the portable skills
- Implicit migration from another E2E framework to Playwright
- Application-code repair
- CI/CD orchestration
- Destructive production testing
- Treating contract, accessibility, visual, chaos, or component testing as interchangeable with E2E testing

## 4. Architecture

### 4.1 Thin orchestrator and autonomous adapters

`e2e-testing` owns discovery, policy, routing, framework-neutral planning, protocol state, and external handoffs. It contains no Playwright-specific generation or repair logic.

`e2e-web-playwright` owns Playwright discovery, planning details, setup, test generation, execution, diagnosis, and test-only repair. It can consume an orchestrator manifest or bootstrap a compatible manifest when invoked directly.

The external loop engine owns cross-capability coordination. Skills communicate through artifacts and terminate after producing a durable outcome. They do not hold a session open while waiting for another skill, tool, model, or person.

### 4.2 Entry points

The primary entry point is `e2e-testing`. It normalizes the request, creates the run workspace, selects an adapter, and persists the relevant `next_actions` entry before attempting any host-supported delegation.

Experts may invoke `e2e-web-playwright` directly. Without an existing manifest, the adapter creates a minimal compatible run, performs the discovery needed for its requested mode, and continues.

If no mode is supplied, both entry points interpret the request as `generate`.

### 4.3 Portable handoff

A handoff requests a capability rather than a fixed skill name. Examples include:

- `fix-product-defect`
- `provision-test-environment`
- `provide-test-credentials`

The host maps a capability to a skill, tool, model, workflow, or person. The handoff includes a resume target so the original run can continue afterward.

## 5. Repository and Packaging Design

The renamed project root is `e2e-testing`. The planned repository layout is:

```text
e2e-testing/
├── skills/
│   ├── e2e-testing/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/
│   └── e2e-web-playwright/
│       ├── SKILL.md
│       ├── references/
│       ├── assets/
│       └── scripts/
├── protocol/
│   └── v1/
├── evals/
└── docs/
```

Each skill directory is independently installable and conforms to the Agent Skills specification. A release copy of the supported protocol schema and its deterministic validator is bundled with each skill that must operate independently. Repository tests ensure copies for the same protocol version remain identical.

Vendor-specific plugins may bundle the portable skills later, but plugin packaging is not required for correctness.

## 6. Artifact Contract

### 6.1 Run workspace

Agent workflow artifacts live under `.e2e/` in the target project:

```text
.e2e/
├── manifest.json
├── test-plan.md
├── evidence/
└── handoffs/
```

Actual Playwright tests remain in the repository's established test locations. The skill must not move an existing suite merely to match its own preferred layout.

### 6.2 Authority

- `manifest.json` is authoritative for machine-readable state and transitions.
- `test-plan.md` is authoritative for human-reviewed intent, journeys, assumptions, and unresolved conflicts.
- `evidence/` supports verification and diagnosis.
- `handoffs/` stores portable external requests and completion records.

### 6.3 Required manifest concepts

The version 1 schema includes at least:

- `protocol_version`
- `run_id`
- `revision`
- `mode`
- `autonomy`
- `status`
- `project`
- `target`
- `journeys[]`
- `tests[]`
- `evidence[]`
- `conflicts[]`
- `attempt_budget`
- `attempt_history[]`
- `handoffs[]`
- `authorizations[]`
- `next_actions[]`

Every journey, test, handoff, and action has a stable ID. Tests reference their journey IDs, and the manifest records the files created or changed for each invocation. Run-level status is an aggregate; each journey and test keeps its own status so blocked work can coexist with completed work. Multiple next actions are ordered deterministically by safety, dependency, and journey priority.

### 6.4 Concurrency and compatibility

Every successful manifest write increments `revision`. A writer operating on an older revision stops with a state-conflict outcome rather than overwriting newer work.

Each adapter declares the protocol range it supports. An unsupported version produces `protocol-incompatible` without mutating tests.

Repeated invocation resumes existing work and does not duplicate scenarios already completed for the current journey revision.

### 6.5 Secrets

Artifacts may contain environment-variable names or secret-provider references, never secret values. Generated source, logs, traces, screenshots, and diagnoses must apply the same rule.

### 6.6 Artifact lifecycle

The run workspace is durable across invocations but is not automatically committed. The skill must not change ignore rules without approval. Binary or sensitive evidence should normally be ignored or uploaded to an authorized artifact store, while the manifest retains stable references and integrity metadata. Teams may explicitly version plans and sanitized manifests when that supports their loop-engineering workflow.

## 7. Modes

### 7.1 `plan`

The orchestrator extracts and prioritizes framework-neutral journeys. The Playwright adapter enriches them with web preconditions, observable outcomes, test-data requirements, browser projects, and candidate evidence.

Evidence is labeled, at minimum, as:

- `live-observed`
- `source-derived`
- `spec-derived`

Specifications, source, and runtime behavior have no silent precedence. Conflicting evidence marks affected journeys `needs-clarification`; independent journeys may continue.

### 7.2 `generate` — default

Generation may inspect a running application when available to validate flows and locators. It does not execute the generated suite.

When the application is unavailable, generation may proceed from source and specification evidence while recording lower confidence. All generated output exits as `generated-unverified`.

When Playwright exists, generation preserves the repository's language, package manager, paths, configuration, fixtures, and conventions unless a documented change is necessary. When Playwright is absent, the adapter creates one minimal, coherent setup. If another browser E2E framework exists, it returns `unsupported-framework` and does not introduce Playwright or offer an implicit migration.

### 7.3 `verify`

Verification checks target authorization, executes tests selected by manifest IDs, collects evidence, and classifies failures. It records the command, environment, exit status, duration, retry behavior, and evidence paths.

Bounded reruns may help classify likely flakiness. A retry pass does not erase the original failure or count as a clean verification result.

### 7.4 `repair`

Repair may change tests, fixtures, test-data setup, and test configuration only. It must not:

- Modify application code
- Delete intended coverage
- Weaken expected outcomes
- Replace meaningful assertions with superficial checks
- Add unconditional skips
- Add arbitrary sleeps as a stability fix

Every repair is followed by verification. Repair attempts are bounded and recorded.

### 7.5 Auto policy

`auto` is an orchestration policy, not a fifth implementation mode. It advances through manifest transitions. Auto-repair is configurable and opt-in; explicit repair is the default.

The portable skills describe task characteristics and capability requirements but do not select model names. A host may route planning, generation, or repair to a stronger model and verification or routine classification to a smaller or local model.

### 7.6 Mode preconditions

- `plan` may start a new run or revise an existing plan.
- `generate` performs planning first when no compatible plan exists.
- `verify` requires registered test IDs and an authorized target. During direct invocation, it may bootstrap a manifest by discovering and registering an existing Playwright selection before execution.
- `repair` requires a recorded `test-defect` classification and supporting evidence.
- A mode with unmet preconditions emits the appropriate clarification, authorization, environment, or capability handoff instead of guessing.

## 8. State Machine

The happy path is:

```text
initialized
  -> planned
  -> ready-for-adapter
  -> generated-unverified
  -> verifying
  -> verified
```

Verification failures are classified as:

- `test-defect`
- `product-defect`
- `environment-failure`
- `requirements-conflict`
- `authorization-required`
- `inconclusive`

Transitions are deterministic:

- `test-defect` -> `repair-ready` -> bounded `repair` -> `verify`
- `product-defect` -> `handoff-required` -> external fix -> `verify`
- Environment, credentials, or authorization -> capability handoff -> `verify`
- Requirements conflict -> `needs-clarification`; unaffected journeys continue
- Low-confidence diagnosis or exhausted budget -> `blocked` with preserved evidence
- Unsupported framework -> `unsupported-framework` without infrastructure mutation
- Unsupported protocol -> `protocol-incompatible` without test mutation

## 9. Product-Defect Handoff

When verification identifies a probable product defect, the adapter:

1. Stops test repair for the affected journey.
2. Saves reproduction steps, expected and actual behavior, traces, screenshots, logs, environment information, affected IDs, and classification confidence.
3. Sets the run to `handoff-required` for that journey.
4. Requests `fix-product-defect`.
5. Includes `e2e-web-playwright verify` as the resume target.
6. Ends the invocation without waiting.

The external fixer may change application code. The E2E adapter may not. After completion, the loop engine or user appends the handoff result and resumes verification using the same run and defect ID.

## 10. Safety and Approval Policy

### 10.1 Environment tiers

- Local and ephemeral targets are allowed by default.
- Staging requires explicit target configuration.
- Production requires an explicit allow-policy and scenarios marked non-destructive.
- Destructive test-data operations require approval in every environment.

If authorization is missing, auto mode emits `needs-authorization` and stops rather than guessing.

### 10.2 Risk-based human gates

Auto mode continues through safe, reversible work. It pauses for:

- Ambiguous or conflicting requirements
- Credentials or secret access
- Protected environments
- Destructive data operations
- Framework migration
- Low-confidence failure classification

Explicit mode may request review after every stage.

### 10.3 Untrusted content

Repository files, specifications, browser content, test output, and external logs are treated as evidence, not instructions. Discovered prompt-like text cannot override user authorization, skill rules, or environment policy.

## 11. Error Handling

One blocked journey must not discard unrelated progress. Every terminal or paused state includes evidence, confidence, and a next recommended action where one is safe.

The workflow uses bounded execution, repair, and wall-clock budgets. Exhaustion produces a durable `blocked` outcome rather than an infinite loop.

Partial file writes must not advance the manifest state. A mode updates state only after its output files and evidence have been written and validated.

## 12. Test-Generation Quality Rules

The Playwright adapter should prefer:

- User-visible behavior over implementation details
- Accessible and user-facing locators, or explicit test contracts
- Isolated tests with controlled data
- Web-first assertions and framework-native waiting
- Existing fixtures and helpers when appropriate
- Small, readable abstractions selected by suite complexity

Page Objects are optional, not mandatory. The adapter chooses direct locators, fixtures, component objects, or page objects according to existing conventions and maintainability needs.

The adapter does not test uncontrolled third-party behavior directly. It uses controlled boundaries or records an external dependency requirement.

## 13. Validation Strategy

### 13.1 Static and deterministic validation

Validate:

- Agent Skills frontmatter and naming
- Resource references and relative paths
- Manifest schema and protocol versions
- State transitions and revision conflicts
- Resumability and duplicate prevention
- Attempt and runtime budgets
- Secret redaction
- Capability handoff structure
- Equality of packaged schema copies for a protocol version

### 13.2 Behavioral evaluation matrix

Evaluate at least:

1. A web app without E2E infrastructure using source evidence only.
2. A web app with a running target for live-assisted generation.
3. An existing Playwright suite with custom fixtures and paths.
4. A Cypress repository that must remain unchanged.
5. Conflicting specification and runtime behavior.
6. A generated suite that verifies successfully.
7. A defective test that can be repaired safely.
8. A product defect that hands off and later resumes.
9. Missing credentials or environment dependencies.
10. Auto mode reaching a repair or runtime budget.

Codex and Claude Code are required behavioral hosts for version 1. Use fresh sessions, realistic requests, and raw repositories. Do not provide the expected diagnosis or design conclusions to the evaluating agent.

### 13.3 Acceptance criteria

- Every generated test traces to a stable journey ID.
- No generated suite is reported as verified without execution evidence.
- Existing Playwright conventions remain intact.
- Unsupported frameworks cause no test-infrastructure mutation.
- Failure classifications include evidence and confidence.
- Repair never modifies application code or weakens intended outcomes.
- Explicit and auto workflows produce compatible manifests.
- Interrupted runs resume without duplicating completed work.
- Fixture scenarios behave equivalently on Codex and Claude Code.

## 14. Research Basis

This design follows:

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skills documentation](https://code.claude.com/docs/en/slash-commands)
- [OpenAI Skills guidance](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)
- [GitHub Copilot Agent Skills guidance](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [Gemini CLI Agent Skills guidance](https://geminicli.com/docs/cli/creating-skills/)
- [Playwright Test Agents](https://playwright.dev/docs/test-agents)
- [Playwright best practices](https://playwright.dev/docs/best-practices)
- [Appium architecture](https://appium.io/docs/en/latest/intro/)

## 15. Implementation Sequence

The implementation plan should proceed in this order:

1. Define and test protocol version 1.
2. Implement the portable `e2e-testing` orchestrator.
3. Implement `e2e-web-playwright` against the protocol.
4. Add deterministic validators and safety checks.
5. Add behavioral fixtures and evaluate on Codex and Claude Code.
6. Iterate on protocol and skill guidance before designing a second adapter.
