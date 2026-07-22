# E2E Testing

Portable Agent Skills for repository-native web end-to-end testing on Protocol 2.

- [`e2e-testing`](skills/e2e-testing/SKILL.md) plans externally observable web journeys, applies shared safety policy, and coordinates durable Protocol 2 actions and handoffs.
- [`e2e-web`](skills/e2e-web/SKILL.md) implements Playwright-backed planning, generation, selected verification, failure classification, and bounded test repair behind a surface-oriented public boundary.

## Installation

Install both directories from `skills/` in the project-local skill directory supported by your agent:

- Cross-agent/Codex convention: `.agents/skills/`
- Claude Code convention: `.claude/skills/`

Keep each skill directory intact so its bundled references and protocol utility remain available.

## Quick start

Ask `e2e-testing` to generate web E2E coverage for the current project. Generation is the default and always ends `generated-unverified`; verification is a separate step that requires selected-check evidence and target/credential authorization before it may run.

Invoke `e2e-web` directly only when the repository's web E2E boundary is already known and orchestration is unnecessary.

## Modes

- `plan`: discover and record journeys without generating tests.
- `generate`: create coverage without claiming it was executed.
- `verify`: execute selected tests and record environment-bound evidence.
- `repair`: repair classified test defects within explicit budgets, then reverify.

Explicit mode reports the next capability invocation. Automatic mode follows ordered manifest actions; automatic repair remains separately opt-in.

## Safety boundaries

The skills never repair application code, weaken expected outcomes, add unconditional skips, or run destructive target operations without the required authorization. Product defects produce a capability handoff instead of an application change.

Read each skill's safety and workflow references before using credentials or non-local targets.

## Repository layout

- `skills/e2e-testing/`: orchestration skill — discovers journeys, applies safety policy, and routes work through Protocol 2.
- `skills/e2e-web/`: Playwright-backed execution skill — generation, selected verification, failure classification, and bounded repair.
- `protocol/v2/`: canonical portable manifest schema and utility.
- `evals/cases/`: behavioral case contracts.
- [`evals/fixtures/`](evals/fixtures/README.md): deterministic fixture repositories and integrity baselines.
- [`evals/HOST_EVALUATION.md`](evals/HOST_EVALUATION.md): authorized host-harness procedure.
- `tests/`: deterministic protocol, packaging, skill, evaluator, and harness contracts.

## Contributing

Run before opening a pull request:

```sh
python3 scripts/sync_protocol.py --check
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
git diff --check
```

Update the canonical protocol first, then run `python3 scripts/sync_protocol.py` when bundled copies must change.
