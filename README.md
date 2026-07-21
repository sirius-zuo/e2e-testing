# E2E Testing

Portable Agent Skills for planning, generating, verifying, and safely repairing browser end-to-end tests.

The project separates orchestration from framework execution:

- [`e2e-testing`](skills/e2e-testing/SKILL.md) discovers journeys, applies safety policy, and routes work through a portable manifest.
- [`e2e-web-playwright`](skills/e2e-web-playwright/SKILL.md) implements Playwright generation, verification, failure classification, and bounded test repair.

## Installation

Install both directories from `skills/` in the project-local skill directory supported by your agent:

- Cross-agent/Codex convention: `.agents/skills/`
- Claude Code convention: `.claude/skills/`

Keep each skill directory intact so its bundled references and protocol utility remain available.

## Quick start

Ask the orchestrator to generate browser E2E coverage for the current project. Generation is the default and ends as `generated-unverified`; request verification separately when the target and credentials are authorized.

Invoke `e2e-web-playwright` directly only when the repository is already known to use Playwright and orchestration is unnecessary.

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

- `skills/`: independently installable skills.
- `protocol/v1/`: canonical portable manifest schema and utility.
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
