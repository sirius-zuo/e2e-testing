"""Synchronize the versioned protocol into standalone skill bundles."""

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_FILES = (
    (ROOT / "protocol/v2/manifest.schema.json", "references/manifest.schema.json"),
    (ROOT / "protocol/v2/extensions/web.schema.json", "references/extensions/web.schema.json"),
    (ROOT / "protocol/v2/e2e_protocol.py", "scripts/e2e_protocol.py"),
)
TARGETS = (ROOT / "skills/e2e-testing", ROOT / "skills/e2e-web")


def sync(check: bool) -> list[str]:
    """Copy canonical protocol files, or report stale standalone copies."""
    stale = []
    for target in TARGETS:
        for source, relative_destination in CANONICAL_FILES:
            destination = target / relative_destination
            if not destination.exists() or destination.read_bytes() != source.read_bytes():
                stale.append(str(destination.relative_to(ROOT)))
                if not check:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
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
