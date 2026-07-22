import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "skills/e2e-testing", ROOT / "skills/e2e-web"]
CANONICAL_FILES = {
    "references/manifest.schema.json": ROOT / "protocol/v2/manifest.schema.json",
    "references/extensions/web.schema.json": ROOT / "protocol/v2/extensions/web.schema.json",
    "scripts/e2e_protocol.py": ROOT / "protocol/v2/e2e_protocol.py",
}


class PackagingTests(unittest.TestCase):
    def test_protocol_copies_match_canonical_files(self):
        for target in TARGETS:
            for relative, canonical in CANONICAL_FILES.items():
                self.assertEqual(
                    (target / relative).read_bytes(),
                    canonical.read_bytes(),
                    f"stale bundle: {target.relative_to(ROOT) / relative}",
                )

    def test_old_web_skill_directory_is_absent(self):
        self.assertFalse((ROOT / "skills/e2e-web-playwright").exists())

    def test_each_bundled_utility_runs_standalone(self):
        for target in TARGETS:
            result = subprocess.run(
                [sys.executable, str(target / "scripts/e2e_protocol.py"), "--help"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("transition", result.stdout)


if __name__ == "__main__":
    unittest.main()
