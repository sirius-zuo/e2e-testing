# Final corrections report

## Scope

This change binds the final whole-branch review findings for protocol defaults,
unsupported-framework outcomes, evaluator evidence, resume integrity, schema
vocabulary, and journey referential integrity.

## RED evidence

The first focused RED run was:

```text
python3 -m unittest tests.test_protocol tests.test_skill_contracts tests.test_evaluation_contracts.EvaluatorTests -v
```

It reported nine expected failures: automatic repair was enabled for auto mode;
the default wall-clock budget was one second; unknown journey references passed;
unsupported-framework instructions conflicted with the persisted-case contract;
the protocol documents used non-schema statuses and `handoff_id`; the evaluator
accepted an unsupported outcome with the wrong mode/no detection evidence and a
verified outcome with only a label; and resume accepted an unapproved source
addition.

A final focused RED test also confirmed that `auto-budget` accepted an
`evidence-budget-exhausted` label without budget/attempt details.

## GREEN evidence

```text
python3 -m unittest tests.test_protocol tests.test_skill_contracts tests.test_evaluation_contracts -v
68 tests: OK

python3 scripts/sync_protocol.py --check
exit 0

python3 scripts/validate_skills.py
validated: 2 skills

git diff --check
exit 0
```

## Changed files

- `protocol/v1/e2e_protocol.py` and both bundled utility copies: auto repair is
  opt-in, the usable bounded wall-clock default is 300 seconds, and tests,
  actions, and handoffs must reference registered journeys.
- `evals/evaluate_result.py` and all case contracts: required mode/autonomy,
  status-specific execution/classification/handoff/repair/budget evidence, and
  exact authorized-patch repository-state comparison.
- Both skills and their workflow/protocol/safety references: read-only framework
  detection now precedes a durable unsupported manifest outcome, while
  Playwright/test infrastructure remains immutable; docs use schema tier/status
  vocabulary and the exact `id` handoff field.
- Protocol, skill, and evaluator contract tests cover the above behavior.

## Self-review

- Unsupported Cypress now persists only the durable manifest outcome after
  read-only detection, with no Playwright or test-infrastructure mutation.
- `new_manifest(..., autonomy="auto")` leaves `auto_repair` false; a case may
  explicitly request it true.
- Verified status requires successful selected-test execution evidence, including
  command, exit code, duration, selected tests/outcomes, and environment.
- Product handoff and repair paths require meaningful classification and resume
  or bounded-attempt facts; auto-budget requires budget/attempt evidence.
- Resume compares the whole expected post-patch application state and rejects
  changed, deleted, or newly added application files while allowing only
  `.e2e` manifest/evidence/handoff artifacts.
- Protocol copies were synchronized and the diff has no whitespace errors.

## Commit

Commit is pending. `git add` could not create the linked-worktree index lock in
the filesystem sandbox; the required elevated staging request was rejected by
the environment because its usage limit was reached. No staging workaround was
attempted, and unrelated untracked files remain untouched.

## Concerns and deferred work

- Authorized live Codex/Claude model evaluations were deliberately not run;
  they remain user-deferred and no hosts were started.
- The validator rejects secret-like keys. A value-level secret scan is deferred:
  reliable generic detection would create false assurances and false positives
  without a repository-approved secret provider or detector.

---

# Second-pass review corrections — 2026-07-21

## Scope

The second pass hardens post-patch repository-state comparison, product-defect
handoff evidence and referential integrity, and the documented protocol/handoff
vocabulary. The harness test exercises both Codex and Claude workspace layouts
without launching either host.

## RED evidence

The initial focused run covered the new evaluator, two-phase harness, transition,
and handoff-vocabulary contracts. It ran five tests and produced six expected
failures: incomplete product evidence and handoffs were accepted; installed
Codex and Claude skill trees plus `.e2e/test-plan.md` were rejected; the
transition guide documented an invalid source; and the handoff table used stale
field names.

Separate focused RED runs confirmed that the Playwright guide omitted the exact
handoff fields, dangling evidence/artifact references passed protocol validation,
and non-string reference entries passed validation.

## GREEN evidence

```text
python3 -m unittest <seven focused second-pass contract tests> -v
7 tests: OK

python3 -m unittest tests.test_protocol.ProtocolTests.test_product_handoff_refs_must_resolve_to_manifest_evidence_and_artifacts -v
1 test: OK

python3 scripts/sync_protocol.py --check
exit 0

python3 scripts/validate_skills.py
validated: 2 skills

python3 -m unittest discover
74 tests: OK

git diff --check
exit 0
```

## Corrections and self-review

- Resume comparison now permits generated `.e2e/**` state and harness-installed
  `.agents/skills/**` or `.claude/skills/**` trees. Repository metadata remains
  harness-internal; all other unexpected application/repository additions are
  rejected, while the existing full-state comparison continues to reject
  unauthorized modifications and deletions.
- The harness-integrated two-phase test installs each host's skills, persists
  `.e2e/test-plan.md` and sanitized evidence, applies the declared product patch,
  resumes successfully, then proves an extra application file is rejected.
- Product handoff requires a nonzero selected-test execution with command or
  command reference, duration, failed outcomes, and execution environment. Its
  product-defect classification must reference that execution evidence.
- Handoffs require exact `journey_ids`, reproduction steps, expected and actual
  behavior, valid artifact/evidence references, capability, and resume command.
  Protocol validation rejects dangling and non-string references before semantic
  evaluation.
- Every transition table row is contract-checked against `TRANSITIONS`; the
  generation path is now `planned` -> `ready-for-adapter` ->
  `generated-unverified`.
- The handoff guide and Playwright workflow use the evaluator's exact vocabulary,
  including `journey_ids` instead of `journeys`.
- Both bundled protocol validators are synchronized, the complete suite passes,
  and the diff has no whitespace errors.

## Execution boundaries

No live Codex or Claude host was started. Existing unrelated untracked files and
cache directories were preserved.
