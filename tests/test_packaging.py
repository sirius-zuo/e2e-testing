import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "skills/e2e-testing", ROOT / "skills/e2e-web-playwright"]


class PackagingTests(unittest.TestCase):
    def test_protocol_copies_match_canonical_files(self):
        schema = (ROOT / "protocol/v1/manifest.schema.json").read_bytes()
        utility = (ROOT / "protocol/v1/e2e_protocol.py").read_bytes()
        for target in TARGETS:
            self.assertEqual((target / "references/manifest.schema.json").read_bytes(), schema)
            self.assertEqual((target / "scripts/e2e_protocol.py").read_bytes(), utility)

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
