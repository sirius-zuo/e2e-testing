# E2E Testing Agentic Skill — Initial Proposal

> Superseded by `docs/superpowers/specs/2026-07-20-e2e-testing-design.md` after design review.

## Skill Metadata

- **Name**: `e2e-testing`
- **Description**: Generate and maintain comprehensive E2E test suites for software projects using codebase, wiki, specs, and architecture information. Triggered when users request end-to-end tests, test automation strategy, critical user journey coverage, or agentic test suite creation and maintenance for web, mobile, backend, or distributed systems.
- **Version**: 1.0
- **Type**: Workflow / Agentic Generator

---

## 1. Objectives and Scope

### Core Mission
Provide a structured, standardized, and agentic approach to creating and maintaining high-quality End-to-End (E2E) test collections that complements SDD and TDD practices in AI-driven development workflows.

### In Scope
- Test strategy definition
- User journey extraction and mapping from multiple sources
- Test suite architecture and directory structure
- High-quality test case generation with templates
- Change-driven test maintenance recommendations

### Out of Scope (Separate Skills)
- Test execution and running
- CI/CD pipeline orchestration
- Runtime test debugging and result analysis

---

## 2. Core Workflow

The skill follows a clear phased process:

### Phase 1: Project Analysis
1. Collect inputs from codebase, wiki, specs, and user descriptions.
2. Extract **User Journeys** (see Section 3.1).
3. Identify key components, services, APIs, and data flows.
4. Assess risks and prioritize.

### Phase 2: Test Strategy Definition
- Define test scope and layering strategy.
- Select appropriate frameworks and tools.
- Establish data, environment, and mocking strategies.
- Plan for maintainability and observability.

### Phase 3: Test Suite Generation
- Recommend directory structure.
- Generate configuration files.
- Produce test cases in priority order (start small, iterate).
- Create supporting utilities (helpers, fixtures, page objects).

### Phase 4: Maintenance & Evolution
- Impact analysis on code/spec changes.
- Update and augmentation recommendations.
- Coverage improvement plans.
- Refactoring suggestions.

---

## 3. Detailed Design Elements

### 3.1 User Journey Extraction
**Effective Extraction Methods**:
- **Codebase**: Analyze routes, controllers, service call graphs, main pages/components.
- **Wiki/Specs**: Extract User Stories, Acceptance Criteria, flow diagrams, sequence diagrams.
- **Output Format**: Standardized Journey Map including:
  - Actor / User Role
  - Trigger
  - Step-by-step flow
  - Involved components/APIs
  - Risk level
  - Traceability links to specs

**Skill Resource**: `references/journey-extraction-checklist.md` (framework-specific scanning guidelines).

### 3.2 Test Case Generation Prompt Templates
**Required**: Dedicated, high-quality prompt template library.

**Templates to Include** (`references/prompt-templates/`):
- Single Journey E2E Test Generation
- API-heavy / Backend Orchestration
- Change-driven Test Update
- Microservices / Distributed Flow

**Template Characteristics**:
- Strong role prompting ("You are a senior E2E Test Architect")
- Enforce best practices (POM, Given-When-Then, strong assertions)
- High readability (business language, comments)
- Anti-pattern avoidance

### 3.3 Differentiation by Project Type
The skill includes built-in decision logic:

| Project Type       | Recommended Framework          | Focus Areas                          | Strategy Adjustments |
|--------------------|--------------------------------|--------------------------------------|----------------------|
| Web (SPA/SSR)      | Playwright (preferred)         | UI interactions, visual, a11y        | Heavy UI + API verification |
| Mobile             | Playwright Mobile / Appium     | Gestures, devices, permissions       | Device-specific flows |
| Desktop            | Playwright / Electron          | Native menus, file system            | Window & shortcut handling |
| Backend-heavy      | Playwright + API / Supertest   | Business process orchestration       | Multi-service flows |
| Fullstack          | Playwright                     | End-to-end consistency               | UI → API → DB validation |

### 3.4 Microservices & Distributed Systems
**Layered Strategy** (Avoid monolithic E2E):
1. **Contract Testing** at service boundaries.
2. **Saga / Orchestration E2E** (core business flows spanning 2-4 services).
3. **Limited Full End-to-End** for highest-value user paths.

**Key Techniques**:
- Service virtualization and mocking.
- Distributed tracing (Trace ID / Correlation ID).
- Eventual consistency verification for async flows.
- Chaos engineering scenarios for resilience.
- Consumer-Driven Contract Testing (e.g., Pact) as complement.

---

## 4. Resource Structure

```bash
e2e-testing/
├── SKILL.md
├── references/
│   ├── best-practices.md
│   ├── journey-extraction-checklist.md
│   ├── prompt-templates/          # Multiple focused templates
│   └── project-type-guides/       # Web, Mobile, Microservices etc.
├── assets/
│   └── templates/                 # Boilerplates (Playwright, Cypress, etc.)
└── scripts/                       # Optional analysis helpers
```

## 5. Core Principles (Built-in)

-   **Progressive & Iterative**: Start with high-value journeys, expand based on feedback.
-   **Maintainability First**: Use Page Object / Component models, avoid fragility.
-   **Traceability**: Link every test to originating specs/user stories.
-   **Risk-Based Prioritization**.
-   **Flakiness Prevention**: Reliable waits, idempotency, no hardcoded sleeps.
-   **Human-in-the-Loop**: Confirm at major phases.

* * *

## 6\. Success Criteria

-   Generated tests are readable, maintainable, and business-oriented.
-   Strong coverage of critical user value paths.
-   Effective response to code and requirement changes.
-   Enables fast iteration of test suites by developers and agents.
