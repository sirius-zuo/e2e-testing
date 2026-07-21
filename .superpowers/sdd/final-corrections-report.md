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

The first-pass corrections were subsequently committed as `74cd3d5`.

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

---

# Final targeted corrective pass — 2026-07-21

## Scope

This pass makes collection validation total for malformed collection types and
binds verified/reverified acceptance to the explicitly required successful
execution record for the current phase, manifest revision, and scoped tests.

## RED evidence

```text
python3 -m unittest tests.test_protocol.ProtocolTests.test_wrong_collection_types_return_stable_errors_without_iteration_failures -v
1 test: ERROR (journeys: null raised TypeError before collection validation)

python3 -m unittest tests.test_evaluation_contracts.EvaluatorTests.test_verified_case_rejects_required_label_with_unrelated_successful_execution tests.test_evaluation_contracts.EvaluatorTests.test_verified_case_accepts_required_execution_bound_to_phase_revision_and_scope -v
2 tests: 1 expected failure, 1 pass (the unrelated successful execution incorrectly satisfied the required label)

python3 -m unittest tests.test_evaluation_contracts.FixtureContractTests.test_verified_case_expectations_name_the_execution_evidence_to_bind -v
1 expected failure (verified cases did not declare required execution evidence IDs)

python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_playwright_adapter_reference_safety_contract -v
1 expected failure (execution evidence omitted the evaluator phase field)
```

## GREEN evidence

```text
python3 -m unittest <five focused final-pass contract tests> -v
5 tests: OK

python3 scripts/sync_protocol.py --check
exit 0

python3 scripts/validate_skills.py
validated: 2 skills

python3 -m unittest discover
78 tests: OK

git diff --check
exit 0
```

## Corrections and self-review

- The canonical validator first establishes which of all eight collection fields
  are arrays, emits one stable `<field> must be an array` diagnostic for every
  malformed field, and only then derives journey IDs or iterates records.
- The synchronized bundled validators inherit the same total validation path.
- Verified expectations explicitly name their required execution evidence IDs.
  Each named record must itself be a successful execution for the current phase
  and exact manifest revision, and its selected IDs must cover every test scoped
  by the required journeys.
- A separate successful execution for an unrelated registered journey cannot
  make an empty required evidence label pass.
- Verify, repair, and resumed product-fix cases carry explicit binding metadata;
  the Playwright evidence contract now records the current evaluator `phase`.
- No live Codex or Claude host was started. Existing unrelated untracked files
  and cache directories remain preserved.

---

# Atomic-save revision semantics — 2026-07-21

## Scope

This targeted pass aligns verification evidence with the protocol's atomic-save
semantics: an execution consumes manifest revision N and the resulting final
manifest is persisted as revision N+1.

## RED evidence

```text
python3 -m unittest tests.test_evaluation_contracts.EvaluatorTests.test_verified_case_accepts_execution_that_consumed_the_pre_save_revision tests.test_evaluation_contracts.EvaluatorTests.test_verified_case_rejects_final_or_unrelated_consumed_revision_claims -v
2 tests: 1 expected failure, 1 pass
```

The real `save_manifest` path persisted the setup manifest at revision 1 and the
final verified manifest at revision 2. Evidence correctly recording consumed
revision 1 was rejected because the evaluator incorrectly demanded revision 2.
The rejection test already rejected claims for the final revision and an
unrelated revision.

```text
python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_playwright_adapter_reference_safety_contract -v
1 expected failure (the guide still documented ambiguous `manifest_revision`)
```

## GREEN evidence

```text
python3 -m unittest <three focused atomic-save and workflow tests> -v
3 tests: OK

python3 -m unittest tests.test_evaluation_contracts
55 tests: OK

python3 scripts/sync_protocol.py --check
exit 0

python3 scripts/validate_skills.py
validated: 2 skills

python3 -m unittest discover
80 tests: OK

git diff --check
exit 0
```

## Corrections and self-review

- Successful execution records use the unambiguous
  `manifest_revision_consumed` field.
- Required execution binding accepts only a consumed revision exactly one less
  than the atomically persisted final manifest revision, while retaining the
  current phase and complete scoped-test checks.
- The regression uses `save_manifest` twice and therefore exercises revision
  checks, locking, validation, and the atomic writer instead of directly writing
  JSON.
- Claims for the persisted final revision or an unrelated revision are rejected.
- Existing verify, repair, resume, and harness evidence fixtures use consistent
  consumed-revision values, and the Playwright guide explains the N to N+1 save.
- No live host was started; unrelated untracked files remain preserved.

---

# Revision numeric guards — 2026-07-21

## Scope

This pass prevents Python numeric coercions from weakening atomic-save revision
binding. Final and consumed revisions must be exact integers with valid ranges
before the evaluator performs the N+1 relationship check.

## RED evidence

```text
python3 -m unittest <three numeric-guard tests plus the real-save acceptance test> -v
4 tests: 8 expected subtest failures, 1 pass
```

The failures showed that integral floats and booleans could compare equal to
integer revisions, malformed values produced only the general binding message,
and the impossible final revision 0 / consumed revision -1 pair was accepted.
The real atomic-save revision 1 to revision 2 case continued to pass.

## GREEN evidence

```text
python3 -m unittest <three numeric guards, real-save acceptance, and wrong-revision rejection> -v
5 tests: OK

python3 scripts/sync_protocol.py --check
exit 0

python3 scripts/validate_skills.py
validated: 2 skills

python3 -m unittest discover
83 tests: OK

git diff --check
exit 0
```

## Corrections and self-review

- Final manifest revision must have exact type `int`, excluding `bool`, and be
  at least 1.
- `manifest_revision_consumed` must have exact type `int`, excluding `bool`, and
  be at least 0.
- Type and range guards execute before addition or equality checks, so malformed
  values cannot exploit float/integer or boolean/integer equality.
- Stable diagnostics distinguish an invalid final revision from an invalid
  consumed revision; valid integers that do not satisfy final = consumed + 1
  retain the established binding diagnostic.
- Focused coverage includes integral floats, booleans, negatives, zero, the
  impossible 0/-1 pair, correct real-save behavior, and unrelated revisions.
- No live host was started; unrelated untracked files remain preserved.
