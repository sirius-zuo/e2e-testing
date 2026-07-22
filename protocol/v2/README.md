# Protocol 2

Protocol 2 is the stable manifest kernel for E2E Testing V2 through V6. Surface-specific data belongs in namespaced, versioned extensions.

## Canonical commands

```sh
python3 protocol/v2/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json
python3 protocol/v2/e2e_protocol.py validate PROJECT/.e2e/manifest.json
python3 -m protocol.v2.migrate_v1 PROJECT/.e2e/manifest-v1.json --output PROJECT/.e2e/manifest.json
```

Migration is explicit and lossless. It never overwrites its source. An identical rerun is accepted; a divergent existing target is rejected.

## Compatibility

- The core accepts Protocol `2.0` only.
- Adapters declare supported ranges for their extension namespaces.
- Unknown extensions remain valid and unchanged, while routing reports `capability-unavailable`.
- A known namespace outside every supported range reports `extension-incompatible`.
- The core permits multiple systems and surfaces; V2 applies a separate one-system/one-primary-surface policy.

## Authority

`manifest.schema.json` defines core shape. `e2e_protocol.py` additionally enforces references, revisions, append-only evidence and attempts, secret safety, and extension-preservation rules.

Secret safety is a best-effort heuristic keyed on field names (e.g. `password`, `token`, `secret`, `api_key`, `credential`); it does not inspect values, so an unconventionally named secret field will not be flagged.
