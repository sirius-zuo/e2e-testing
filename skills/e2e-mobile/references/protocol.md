# Protocol 2 Mobile Usage

## Commands

```bash
python3 scripts/e2e_protocol.py --help
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json --replace-protocol-1
python3 scripts/e2e_protocol.py validate PROJECT/.e2e/manifest.json
```

## Mobile-specific behavior

- `e2e.mobile@1.0` stores mobile-only data: `application`, `drivers`,
  `targets`, `artifacts`, and `lifecycle_profiles`.
- Mobile execution units reference the bound `e2e.mobile@1.0` extension by ID.
- The evaluator normalizes driver, platform, target_kind, and evidence_origin
  into the mobile execution environment before running gates.

## Migration notes

Active skills never invoke the offline migrator. The migrator command is
available through the core protocol utility but is not called by any mobile
workflow.

## Portability

The protocol runtime uses only the Python standard library. The synchronized
copy in `scripts/e2e_protocol.py` and `scripts/extension_catalog.py` is fully
independent and requires no site-packages.
