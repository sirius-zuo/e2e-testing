# Repair guardrails

## Contents

- [Allowed paths](#allowed-paths)
- [Prohibited paths](#prohibited-paths)
- [Repair workflow](#repair-workflow)
- [Audit trail](#audit-trail)

## Allowed paths

Repair is bounded to the following paths only:

| Path | Description |
| --- | --- |
| `tests/` | Test files, fixtures, and generated verification scripts |
| `test-support/` | Client adapters, test utilities, and mock servers |
| `scripts/` | Build and test automation scripts owned by the test project |
| `.agents/skills/` | Skill guidance files in the test project |
| `evals/fixtures/` | Evaluation fixtures and contract sources |
| `evals/cases/` | Evaluation case definitions |
| `evals/evaluate_result.py` | Evaluator logic |
| `evals/run_host_eval.py` | Host evaluation harness |
| `tests/test_*.py` | Test contract files |
| `scripts/validate_skills.py` | Skill validation script |
| `scripts/sync_protocol.py` | Protocol sync script |
| `skills/e2e-service/references/` | Service skill guidance files |
| `skills/e2e-testing/` | Orchestrator skill files |
| `skills/e2e-web/` | Web skill files |
| `protocol/v2/extensions/` | Protocol extension schemas |
| `protocol/v2/manifest.schema.json` | Protocol manifest schema |
| `docs/roadmap.md` | Roadmap documentation |
| `README.md` | Project README |
| `evals/HOST_EVALUATION.md` | Host evaluation documentation |
| `tests/test_readmes.py` | Readme contract tests |
| `tests/test_skill_contracts.py` | Skill contract tests |
| `tests/test_packaging.py` | Packaging tests |

## Prohibited paths

The following paths are prohibited during repair:

| Path | Reason |
| --- | --- |
| `src/` | Application source code |
| `lib/` | Application libraries |
| `app/` | Application routes and handlers |
| `public/` | Public-facing static assets |
| `config/` | Application configuration |
| `contracts/` | Public API contracts |
| `schemas/` | Public schema definitions |
| `proto/` | Protobuf definitions |
| `Makefile` | Build configuration |
| `docker-compose.yml` | Infrastructure configuration |
| `.github/` | CI/CD configuration |

Never modify application code, public service contracts, schemas, protobuf
definitions, expected behavior, or production configuration during repair.

## Repair workflow

1. Classify the failure as `test-defect` before attempting repair.
2. Identify the exact file and line that needs correction.
3. Apply the minimum change to fix the test or test support code.
4. Record the repair in an `attempt` evidence record with the `allowed_paths`
   list and the `assertion_comparison` used.
5. Run the affected tests and verify the repair resolves the failure without
   regressing other checks.
6. If the repair introduces new failures, revert and reclassify as
   `inconclusive` or `product-defect` as appropriate.
7. Complete only after all scoped checks pass and cleanup actions succeed.

## Audit trail

Every repair attempt must record:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Unique identifier for this attempt |
| `check_ids` | array | Check IDs that triggered this repair |
| `allowed_paths` | array | Paths authorized for modification |
| `assertion_comparison` | string | How the repair was verified (e.g. `exact`, `regex`, `subset`) |
| `status` | string | `pending`, `in-progress`, `completed`, or `failed` |
| `result` | string | Outcome of the repair with evidence IDs |

The audit trail must be appended to the manifest `attempts` collection. Never
overwrite existing attempts.
