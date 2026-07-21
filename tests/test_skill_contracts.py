"""Contract tests for the portable E2E skill bundles."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def frontmatter(text: str) -> dict[str, str]:
    """Parse the simple frontmatter form used by these skill files."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}

    result: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return result
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip()
    return {}


class SkillContractTests(unittest.TestCase):
    def assert_relative_links_exist(self, skill_directory: Path) -> None:
        for markdown in skill_directory.rglob("*.md"):
            for target in MARKDOWN_LINK.findall(markdown.read_text()):
                target = target.split("#", 1)[0]
                if not target or "://" in target or target.startswith("/"):
                    continue
                self.assertTrue(
                    (markdown.parent / target).exists(),
                    f"{markdown.relative_to(ROOT)} links to missing {target}",
                )

    def test_orchestrator_contract(self):
        skill = ROOT / "skills/e2e-testing/SKILL.md"
        text = skill.read_text()
        self.assertLess(len(text.splitlines()), 500)
        self.assertIn("name: e2e-testing", text)
        self.assertIn("description:", text)
        self.assertEqual(set(frontmatter(text)), {"name", "description"})
        self.assertIn("Default to `generate`", text)
        self.assertIn("generated-unverified", text)
        self.assertIn("next_actions", text)
        self.assertIn("e2e-web-playwright", text)
        self.assertNotIn("You are a senior", text)
        self.assertNotIn("allowed-tools:", text)
        self.assert_relative_links_exist(ROOT / "skills/e2e-testing")
        self.assert_relative_links_exist(ROOT / "skills/e2e-web-playwright")


if __name__ == "__main__":
    unittest.main()
