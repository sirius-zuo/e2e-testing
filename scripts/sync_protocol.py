"""Synchronize the versioned protocol into standalone skill bundles."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_FILES = (
    (ROOT / "protocol/v2/manifest.schema.json", Path("references/manifest.schema.json")),
    (ROOT / "protocol/v2/e2e_protocol.py", Path("scripts/e2e_protocol.py")),
    (ROOT / "protocol/v2/extension_catalog.py", Path("scripts/extension_catalog.py")),
)
TARGETS = {
    ROOT / "skills/e2e-testing": frozenset({"e2e.web"}),
    ROOT / "skills/e2e-web": frozenset({"e2e.web"}),
}
CATALOG_PATH = ROOT / "protocol/v2/extensions/catalog.json"


def _catalog_projection(namespaces: frozenset[str]) -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "catalog_version": catalog["catalog_version"],
        "extensions": [
            entry for entry in catalog["extensions"] if entry["namespace"] in namespaces
        ],
    }


def _expected_files(namespaces: frozenset[str]) -> dict[Path, bytes]:
    expected = {relative: source.read_bytes() for source, relative in STATIC_FILES}
    projection = _catalog_projection(namespaces)
    expected[Path("references/extensions/catalog.json")] = (
        json.dumps(projection, indent=2, sort_keys=False) + "\n"
    ).encode()
    for entry in projection["extensions"]:
        for support in entry["versions"]:
            relative = Path(support["schema"])
            expected[Path("references/extensions") / relative] = (
                ROOT / "protocol/v2/extensions" / relative
            ).read_bytes()
    return expected


def sync(check: bool) -> list[str]:
    stale = []
    for target, namespaces in TARGETS.items():
        for relative, content in _expected_files(namespaces).items():
            destination = target / relative
            if not destination.exists() or destination.read_bytes() != content:
                stale.append(str(destination.relative_to(ROOT)))
                if not check:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report stale protocol copies without writing")
    args = parser.parse_args()
    stale = sync(args.check)
    if args.check:
        for path in stale:
            print(path)
        return int(bool(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
