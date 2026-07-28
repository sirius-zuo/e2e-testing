---
name: e2e-service
description: >-
  Use when the user needs to plan, generate, verify, or repair E2E coverage for
  confirmed supported external boundary in HTTP, GraphQL, gRPC, WebSocket, queue,
  or stream in a repository with native clients. Triggers include requests to
  test REST APIs, validate GraphQL schemas and operations, test gRPC unary and
  streaming calls, verify WebSocket connections, or test queue and stream
  boundaries.
---

# E2E Service Surface Skill

Use `e2e-service` to plan, generate, verify, and repair end-to-end coverage for
confirmed supported external service boundaries. default to generate mode and
one logical system per run.

## Recipe

1. **Resolve mode and requested service boundary.** Confirm the user's goal, the
   protocol module (HTTP, GraphQL, gRPC, WebSocket, queue, or stream), and the
   target tier.
2. **Perform read-only interface discovery before Protocol state.** Inventory
   specifications, client adapters, route handlers, schema definitions, and
   observed deployment behavior. Label evidence `live-observed`,
   `source-derived`, or `spec-derived`. Never assume a boundary is external
   without confirmed support.
3. **Confirm external support or stop with clarification.** If evidence is
   ambiguous, mark affected journeys `needs-clarification`. Persist the
   discovery outcome before proceeding.
4. **Validate or initialize Protocol 2.** Load an existing manifest, validate
   its revisions and state, initialize a fresh run when absent, or replace an
   exact Protocol 1 manifest only with `--replace-protocol-1`. Do not mutate
   test infrastructure as part of discovery.
5. **Preserve or minimally create repository-native setup.** Reuse existing
   client code, test support, and configuration. Create only when no existing
   adapter can serve the selected boundary. Record the adapter references in the
   manifest.
6. **Select protocol modules and mode flow.** Bind each journey to the protocol
   module that matches the confirmed external boundary. One logical system per
   run. The mode flow is `plan` → `generate` → `verify` → `repair` when
   applicable.
7. **Authorize target and mutation before execution.** Classify the target tier.
   Record whether the action mutates data. In production, mutations are
   prohibited. Confirm the user's authorization covers the exact action.
8. **Record selected-check evidence and classify failures.** Execute only the
   checks scoped to the selected journeys. Classify failures as
   `product-defect`, `test-defect`, `environment`, `inconclusive`, or
   `authorization-required`. Persist evidence with exact check IDs.
9. **Bound repair to tests and support.** Repair allowed paths include test
   files, test support, fixtures, and generated verification scripts. Never
   modify application source code, public contracts, or production configuration
   during repair.
10. **Complete only after cleanup.** Run cleanup actions for any setup data.
    Confirm cleanup succeeded. Mark the run complete only when all scoped
    journeys are verified or explicitly deferred.

## Surface contract

- `e2e-service` covers six protocol modules: HTTP, GraphQL, gRPC, WebSocket,
  queue, and stream. Every module references the same `e2e.service@1.0`
  extension.
- One logical system per run. Multi-system and multi-surface composition are
  excluded.
- Production service verification is read-only. No mutations, acknowledgements,
  or committed offsets are allowed during verification.
- Repository-native clients are preferred. Vendor libraries are acceptable only
  when no repository-native adapter exists.

## Modes

| Mode | Preconditions | Expected result |
| --- | --- | --- |
| `plan` | target root and enough evidence to describe journeys | validated plan and `run.revision`; stop |
| `generate` | valid plan or enough evidence to create one | route generation; mark output `generated-unverified` |
| `verify` | valid generated work, authorized target, and runnable verification action | route only after all are recorded |
| `repair` | a recorded verification failure tied to a journey and revision | route only to address that failure |

## Resources

- Read [workflow.md](references/workflow.md) for discovery and handoff details.
- Read [safety.md](references/safety.md) before accessing targets, credentials, or data operations.
- Read [protocol.md](references/protocol.md) before changing Protocol 2 state.
- Read [failure-classification.md](references/failure-classification.md) to classify verification results.
- Read [repair-guardrails.md](references/repair-guardrails.md) for allowed repair paths.
- Read [http.md](references/http.md) for REST/HTTP boundary coverage.
- Read [graphql.md](references/graphql.md) for schema and operation verification.
- Read [grpc.md](references/grpc.md) for gRPC unary and streaming calls.
- Read [websocket.md](references/websocket.md) for connection and message verification.
- Read [queue.md](references/queue.md) for publish-consume boundaries.
- Read [stream.md](references/stream.md) for append-read boundaries.
