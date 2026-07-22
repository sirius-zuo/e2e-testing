# Repair guardrails

## Preconditions

Repair is allowed only when the current manifest records a `test-defect` primary
classification at confidence `0.80` or higher, links its supporting evidence,
and retains a positive repair budget. Product, environment, requirements,
authorization, protocol, and inconclusive outcomes are handoffs or stops, never
repair candidates.

Before editing, record the selected test IDs, defect evidence IDs, intended
outcome, remaining repair and wall-clock budgets, and an explicit allowed-path
list. The list may contain only existing Playwright test specs, test fixtures,
test-data setup, test helpers, or Playwright test configuration required by the
selected tests. It must not include application source, production configuration,
package manifests, lockfiles, generated runtime output, credentials, or unrelated
test files. Recheck the final changed-file list against this allowlist.

## Preserve the intended outcome

Capture the original meaningful assertions and journey coverage before editing.
After editing, compare every changed test's assertions and journey comments with
the pre-edit version. The expected user-visible outcome, test ID, and journey ID
must remain present and equally specific. Stop if a change:

- modifies application code;
- weakens an expected outcome or replaces it with a superficial check;
- deletes intended coverage or a journey traceability comment;
- adds an unconditional skip, focused-only marker, or arbitrary hardcoded sleep;
- broadens the selected test scope or changes an unapproved target/data action.

Permitted repairs correct a test-owned locator, synchronization using a
web-first observable condition, fixture/setup defect, controlled test data, or
test configuration necessary for the selected test. They must not disguise a
product regression.

## Bound, record, and reverify

Consume exactly one repair attempt before making the change and append an attempt
record containing its ID, test IDs, allowed paths, assertion comparison, reason,
and evidence IDs. Do not exceed either repair or wall-clock budget. If the repair
does not leave enough verification budget, stop as blocked rather than edit.

After every repair, invoke `verify` for the manifest-selected IDs on the
authorized target. Preserve the new execution evidence and classify the result.
Do not report a repair as successful, update it to verified, or start another
repair based on a source-only inspection. A failed or low-confidence recheck
returns to the appropriate handoff, clarification, or blocked outcome.
