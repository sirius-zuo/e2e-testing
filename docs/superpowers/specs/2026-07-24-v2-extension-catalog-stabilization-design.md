# Protocol 2 Extension Catalog Stabilization Design

**Date:** 2026-07-24
**Status:** Approved for implementation planning
**Project:** `e2e-testing`

## 1. Purpose

PR #3 established the active Protocol 2 web baseline, but post-merge review found two defects that must be corrected before the service surface is added:

1. The active web workflow documents execution evidence with `test_ids`, while the Protocol 2 evaluator requires `check_ids` and `outcomes[].check_id`.
2. The `e2e.web@1.0` schema is packaged but is not registered by normal runtime operations. As a result, malformed web extension data is not typed-validated and an owned web extension cannot be updated safely across revisions.

This stabilization introduces one generic extension-catalog mechanism suitable for Protocol 2 surface extensions through V6, connects the active web extension to it, and corrects the evidence vocabulary. It is a prerequisite for the V2 service foundation so later surfaces do not copy a broken registration pattern.

## 2. Governing Constraints

- Protocol 2 core remains surface-neutral. It must not hard-code web, service, mobile, or desktop validation logic.
- Recognition follows installed capability ownership:
  - `e2e-web` recognizes only `e2e.web`;
  - future `e2e-service` recognizes only `e2e.service`;
  - `e2e-testing` recognizes every surface it can actively route.
- Normal public runtime operations automatically load the catalog packaged beside that runtime.
- Portable runtime validation uses only the Python standard library and must not require dependency installation in the target repository or skill host.
- Tests and advanced callers may explicitly provide a custom registry instead.
- Catalog or schema installation failures fail closed before manifest mutation.
- The Protocol 2 manifest structure does not change and no manifest migration is introduced.
- Unknown extension namespaces remain preserved unchanged.
- Historical specifications and the offline Protocol 1 migrator remain untouched.
- Work remains entirely within the `e2e-testing` repository.

## 3. Architecture

### 3.1 Surface-neutral catalog loader

The canonical Protocol 2 runtime gains a generic catalog loader. The loader knows how to validate catalog metadata, resolve schemas, compile validators, and build an `ExtensionRegistry`; it has no built-in knowledge of specific surface namespaces.

Canonical extension schemas and catalog metadata live under `protocol/v2/extensions/`. Portable skills bundle filtered release copies beneath their existing extension-reference directory. Each bundle includes only the extensions the installed skill owns or can route.

Automatic discovery checks only the release-native location for the runtime being executed:

- canonical runtime: `protocol/v2/extensions/catalog.json`;
- portable runtime: the sibling skill bundle's `references/extensions/catalog.json`.

The runtime does not search the target repository, current working directory, user directories, or environment-provided paths for a default catalog. This keeps validation independent of invocation location and prevents an untrusted project from shadowing release metadata.

For the current release:

| Bundle | Recognized namespaces |
| --- | --- |
| `e2e-web` | `e2e.web` |
| `e2e-testing` | `e2e.web` |

When the service surface ships, `e2e-service` will bundle `e2e.service`, while `e2e-testing` will bundle both `e2e.web` and `e2e.service` because it can route both.

### 3.2 Catalog contract

The catalog is strict release metadata, not project state. Its initial shape is:

```json
{
  "catalog_version": "1.0",
  "extensions": [
    {
      "namespace": "e2e.web",
      "owner": "e2e-web",
      "versions": [
        {
          "minimum": "1.0",
          "maximum": "1.0",
          "dialect": "draft2020-12-subset-1",
          "schema": "web.schema.json"
        }
      ]
    }
  ]
}
```

Each namespace appears exactly once. A namespace may declare multiple non-overlapping version ranges so later compatible and incompatible schema lines can coexist without changing the catalog format. `e2e.web` initially claims exactly version `1.0`; no unimplemented future compatibility is implied.

Each entry declares:

- the extension namespace;
- the owning capability;
- one or more inclusive minimum and maximum version pairs;
- the runtime schema dialect for each range; and
- a schema path relative to the catalog's extension directory.

Catalog versioning governs only release metadata parsing. It does not alter `protocol_version` or trigger project-manifest migration.

### 3.3 Packaging

The canonical catalog is the source of truth. The synchronization tool filters canonical entries using an explicit per-skill namespace allowlist and copies the referenced schemas with the filtered catalog. Packaging checks enforce:

- every bundled catalog matches its canonical filtered projection;
- every referenced bundled schema matches the canonical schema byte for byte;
- no bundle recognizes an unowned or unroutable namespace; and
- each portable runtime can locate its catalog without repository-relative assumptions.

This keeps skills independently installable while preventing hand-maintained catalog drift.

## 4. Runtime Behavior

### 4.1 Automatic registry loading

Normal public operations automatically load the catalog adjacent to their installed runtime:

- manifest validation;
- manifest initialization validation;
- persistence through `save_manifest`;
- state transitions;
- CLI `init`, `validate`, and `transition`; and
- evaluator validation paths.

The runtime distinguishes an omitted registry from an explicitly supplied custom registry. Omission selects the bundled catalog. Supplying a registry uses that registry intentionally and does not merge it with bundled capabilities.

This safe default prevents callers from accidentally bypassing typed extension validation by forgetting a registry argument.

### 4.2 Catalog loading flow

For a bundled operation, the runtime:

1. locates the catalog at the runtime's single permitted release-native location;
2. validates the catalog structure and supported catalog version;
3. validates namespace uniqueness, ownership, version syntax, range ordering, and non-overlap;
4. resolves each schema path within the catalog extension directory;
5. loads each schema, verifies that it conforms to its declared supported dialect, and rejects unknown keywords;
6. creates an `ExtensionSupport` validator for each declared range; and
7. uses the resulting registry for the complete operation.

The same registry instance is used for validation and persistence within one operation so classification cannot change mid-write.

### 4.3 Portable schema dialect

The initial runtime dialect is `draft2020-12-subset-1`. It is implemented with the Python standard library and supports exactly the JSON Schema features needed by the current web extension:

- annotations: `$schema`, `$id`, `title`, and `description`;
- structural validation: `type`, `required`, `properties`, and boolean `additionalProperties`;
- scalar constraints: `enum`, `const`, `pattern`, `minimum`, `maximum`, `minLength`, and `maxLength`;
- array constraints: `items`, `minItems`, and `maxItems`; and
- recursive use of the same supported keywords in property and item schemas.

`type` accepts either one JSON type name or an array of unique JSON type names. The supported JSON types are `null`, `boolean`, `integer`, `number`, `string`, `array`, and `object`; booleans are not treated as integers or numbers.

The loader self-validates schema structure for this dialect, including keyword value types, required-property names, regular-expression syntax, numeric and length bounds, and recursive child schemas. Any keyword outside the supported set is rejected. `$ref`, `$defs`, conditional schemas, composition keywords, custom formats, and remote references are intentionally unsupported in this initial dialect.

Later releases may add a new named dialect or expand the implementation behind a new dialect name. Existing catalog entries retain their declared semantics, so this evolution requires neither a catalog-format change nor a Protocol 2 manifest migration.

### 4.4 Manifest extension outcomes

The existing Protocol 2 semantics remain:

| Condition | Result |
| --- | --- |
| Namespace and version supported; data valid | Continue |
| Namespace and version supported; data invalid | Manifest validation error |
| Namespace known; version unsupported | `extension-incompatible` |
| Namespace unknown to installed bundle | Preserve unchanged; execution requiring it is `capability-unavailable` |

An owned supported extension may be updated through `save_manifest`. An unknown extension remains immutable during saves and transitions.

### 4.5 Evidence vocabulary

Protocol 2 execution evidence uses:

- `check_ids` for the immutable selected checks; and
- `outcomes[].check_id` for each per-check outcome.

The active web workflow, protocol reference, evaluator, fixtures, and contract tests must use this vocabulary consistently. `test_ids` is not a Protocol 2 execution-evidence field and must not appear in active guidance.

## 5. Failure Handling and Safety

Catalog failures are installation or protocol-runtime errors, not manifest outcomes. The runtime raises a stable `ProtocolError` and performs no project-state mutation when it encounters:

- an unsupported catalog version;
- an unsupported runtime schema dialect;
- a duplicate namespace or conflicting owner;
- an empty version list;
- a malformed, reversed, or overlapping version range;
- an absolute schema path;
- path traversal or symlink escape outside the extension directory;
- a missing or unreadable schema;
- malformed schema JSON; or
- an unsupported schema keyword or a schema that fails structural validation for the declared dialect.

Diagnostics identify the catalog entry and failure category. They must not include manifest secrets, arbitrary schema content, or unsafe filesystem contents.

Catalog failure is not written as `capability-unavailable`: that status means the installed capability does not support a manifest extension, not that its own release artifacts are corrupt. A failed catalog load does not change the manifest revision, state, evidence, actions, or extension records.

## 6. Testing Strategy

### 6.1 Runtime tests

Test-driven implementation begins with failing tests proving:

- valid bundled catalogs load automatically;
- malformed `e2e.web@1.0` data is rejected;
- a supported web extension can change across revisions;
- an unsupported web version resolves as `extension-incompatible`;
- an unknown extension is preserved and cannot be changed or removed;
- malformed catalogs fail without changing the manifest;
- unsafe absolute, traversal, and symlink-escape schema paths are rejected;
- missing, malformed, and invalid schemas are rejected;
- unsupported dialects and schema keywords are rejected;
- empty, reversed, and overlapping version ranges are rejected; and
- an explicit custom registry overrides bundled discovery.

### 6.2 Packaging and contract tests

Packaging tests verify filtered catalog projection, canonical schema equality, standalone runtime discovery, and namespace ownership for every portable bundle.

A contract test first demonstrates the current `test_ids` mismatch, then requires `check_ids` and `outcomes[].check_id` across the active web workflow and evaluator. A deterministic behavioral artifact built strictly from published workflow field names must be accepted by the evaluator.

Because this changes an existing Agent Skill, the implementation follows skill TDD: capture the current behavioral failure without the corrected guidance, apply the minimal guidance correction, and rerun the same scenario. No paid Codex or Claude Code host evaluation runs without separate user authorization.

### 6.3 Release verification

Completion requires fresh success from:

- canonical synchronization checks;
- portable skill validation;
- focused catalog, persistence, evaluator, packaging, and contract tests; and
- the full deterministic test suite.

## 7. Documentation Alignment

The active roadmap currently retains an older requirement for active lossless Protocol 1 migration. That conflicts with the later approved behavior: an exact Protocol 1 project manifest may be explicitly replaced by fresh Protocol 2 state, while the old migrator remains an offline historical utility.

This stabilization updates the active roadmap to reflect the current decision. It does not rewrite historical design or plan documents and does not remove the offline migration code or its tests.

## 8. Scope

### 8.1 Included

- Generic bundled extension catalog and loader.
- Automatic catalog use by active public runtime paths.
- Canonical and portable `e2e.web@1.0` registration.
- Typed validation and safe persistence of the web extension.
- Correct Protocol 2 execution-evidence vocabulary.
- Deterministic runtime, packaging, evaluator, and skill-contract coverage.
- Active roadmap correction for Protocol 1 replacement behavior.

### 8.2 Excluded

- `e2e.service` or REST/general HTTP implementation.
- New Protocol 2 manifest fields or a core-manifest migration.
- Protocol 1 runtime compatibility or active migration.
- Mobile, desktop, composition, or resilience behavior.
- Paid host-model evaluation.

## 9. Acceptance Criteria

This stabilization is complete when:

1. The core runtime contains no hard-coded surface namespace or surface schema behavior.
2. The portable runtime and its schema validation require only the Python standard library.
3. Each portable bundle recognizes only its owned or routable extension namespaces.
4. Normal validation, initialization, persistence, transitions, CLI, and evaluator operations automatically use the bundled registry.
5. Broken catalog release artifacts fail closed without modifying project state.
6. `e2e.web@1.0` data is typed-validated and can be updated across revisions.
7. Unsupported web versions produce `extension-incompatible`.
8. Unknown extensions remain preserved and immutable.
9. Active execution evidence uses `check_ids` and `outcomes[].check_id` consistently.
10. The active roadmap no longer claims active Protocol 1 migration compatibility.
11. Synchronization, skill validation, focused tests, and the full deterministic suite pass.

## 10. Delivery Boundary

This is a focused stabilization subproject between the completed V2 web migration and the service-surface work. It must be specified, planned, implemented, reviewed, and verified independently.

After it is merged, the next V2 cycle is the `e2e-service` foundation with REST/general HTTP. That later cycle will reuse this catalog mechanism to register `e2e.service` without changing the Protocol 2 manifest kernel.
