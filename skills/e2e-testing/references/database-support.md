# Database support for E2E runs

## Purpose

Provide orchestrator-owned database setup, cleanup, and diagnostics that
support execution without becoming a surface, extension, execution unit, or
acceptance oracle. Database actions use existing core records and never
influence verification outcomes directly.

Mobile and desktop may request database setup, cleanup, and diagnostics through
persisted orchestrator actions, but database state never satisfies a mobile or
desktop check. Desktop test-data setup and cleanup operate within the declared
filesystem roots and scoped namespaces only.

## Allowed capabilities

- `database-setup`: insert disposable test data before selected execution.
- `database-cleanup`: remove setup data after execution or on every safe
  terminal path.
- `database-diagnostics`: observe diagnostic data only after an external
  verification failure. Production diagnostics require separate authorization
  and must be sanitized before recording.

## Action fields

Each database action uses the exact fields below:

```json
{
  "id": "action-database-setup",
  "capability": "database-setup",
  "journey_ids": ["journey-order"],
  "command_ref": "command-db-seed",
  "config_refs": ["test-support/database.js"],
  "target_tier": "local",
  "namespace_ref": "namespace-run-id",
  "mutation_class": "insert-disposable-test-data",
  "authorization_id": "authorization-db-setup"
}
```

## Rules

- Setup runs before selected execution and only for journeys that require it.
- Cleanup runs on every safe terminal path and blocks run completion when it
  fails; cleanup failure does not rewrite check outcomes.
- Diagnostics are read-only and allowed only after an external verification
  failure.
- Production setup and cleanup are prohibited.
- Separate authorization is required for narrow production diagnostics.
- Evidence must be sanitized before recording.
- Database rows never appear in `check_ids` or `outcomes`.
- Database support evidence carries `support_only: true`.
- The orchestrator never claims `e2e.support` as a namespace.
- Database support is cross-surface and never becomes a surface, extension,
  execution unit, or acceptance oracle.
