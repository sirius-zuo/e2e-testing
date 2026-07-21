"""Contract tests for the portable E2E skill bundles."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from protocol.v1.e2e_protocol import TARGET_TIERS, TRANSITIONS


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
        self.assertIn(
            "read-only browser-framework discovery before validating or bootstrapping a manifest",
            text,
        )
        self.assertIn("even when Playwright is also present", text)
        self.assertIn("without mutating Playwright or test infrastructure", text)
        self.assertIn("persist a valid `unsupported-framework` manifest/outcome", text)
        self.assertLess(
            text.index("read-only browser-framework discovery"),
            text.index("Validate a compatible `.e2e/manifest.json`"),
        )
        self.assertNotIn("You are a senior", text)
        self.assertNotIn("allowed-tools:", text)
        self.assert_relative_links_exist(ROOT / "skills/e2e-testing")
        self.assert_relative_links_exist(ROOT / "skills/e2e-web-playwright")

    def test_safety_tiers_and_portable_protocol_examples(self):
        safety = (ROOT / "skills/e2e-testing/references/safety.md").read_text()
        protocol = (ROOT / "skills/e2e-testing/references/protocol.md").read_text()

        self.assertIn("explicitly configured staging target", safety)
        self.assertIn("additional approval for mutation or destructive work", safety)
        self.assertIn("explicit configured production allow-policy", safety)
        self.assertIn("non-destructive observation only", safety)
        self.assertIn("categorically prohibited", safety)
        self.assertIn("one-off approval cannot override", safety)
        self.assertIn(
            "Every destructive data operation outside production requires exact-action approval",
            safety,
        )
        self.assertIn("including local and test reset endpoints", safety)
        self.assertIn(
            "In production, mutation, payment, irreversible deletion, and test-data mutation",
            safety,
        )
        self.assertIn("python3 scripts/e2e_protocol.py --help", protocol)
        self.assertIn("python3 scripts/e2e_protocol.py init --help", protocol)
        self.assertIn("python3 scripts/e2e_protocol.py validate --help", protocol)
        self.assertNotIn("skills/e2e-testing/scripts/e2e_protocol.py", protocol)

    def test_playwright_adapter_contract_and_orchestrator_boundary(self):
        adapter = ROOT / "skills/e2e-web-playwright/SKILL.md"
        adapter_text = adapter.read_text()
        orchestrator_text = (ROOT / "skills/e2e-testing/SKILL.md").read_text()

        self.assertLess(len(adapter_text.splitlines()), 500)
        self.assertIn("name: e2e-web-playwright", adapter_text)
        self.assertIn("description:", adapter_text)
        self.assertEqual(set(frontmatter(adapter_text)), {"name", "description"})
        self.assertIn("`plan`, `generate`, `verify`, or `repair`", adapter_text)
        self.assertIn("default to `generate`", adapter_text)
        self.assertIn("bootstrap one with the bundled utility", adapter_text)
        self.assertIn("read-only browser-framework detection", adapter_text)
        self.assertLess(
            adapter_text.index("read-only browser-framework detection"),
            adapter_text.index("Validate an existing manifest"),
        )
        self.assertIn("live inspection", adapter_text)
        self.assertIn("source/spec evidence", adapter_text)
        self.assertIn("unsupported-framework", adapter_text)
        self.assertIn("generated-unverified", adapter_text)
        self.assertIn("recorded test defect", adapter_text)
        self.assertIn("test/support files only", adapter_text)
        self.assertIn("Repair changes are bounded by manifest budgets", adapter_text)
        self.assertIn("Never modify application code", adapter_text)
        self.assertIn("Never weaken expected outcomes", adapter_text)
        self.assertIn("unconditional skips", adapter_text)
        self.assertIn("hardcoded sleeps", adapter_text)
        self.assertIn("product defects", adapter_text)
        self.assertIn("fix-product-defect capability handoff", adapter_text)
        self.assert_relative_links_exist(ROOT / "skills/e2e-web-playwright")

        for playwright_api in ("page.getByRole", "test.describe", "expect("):
            self.assertNotIn(playwright_api, orchestrator_text)

    def test_playwright_adapter_reference_safety_contract(self):
        references = ROOT / "skills/e2e-web-playwright/references"
        workflow = (references / "workflow.md").read_text()
        workflow_semantics = " ".join(workflow.split())
        failure = (references / "failure-classification.md").read_text()
        failure_semantics = " ".join(failure.split())
        repair = (references / "repair-guardrails.md").read_text()
        repair_semantics = " ".join(repair.split())
        protocol = (references / "protocol.md").read_text()
        protocol_semantics = " ".join(protocol.split())

        self.assertIn(
            "Perform read-only browser-framework detection before validating or bootstrapping a manifest",
            workflow,
        )
        self.assertIn("even when Playwright is also present", workflow)
        self.assertIn("unconditionally stop as `unsupported-framework`", workflow)
        self.assertIn("After detection, persist a valid `unsupported-framework` manifest", workflow)
        self.assertIn("durable manifest outcome after read-only detection", workflow_semantics)
        self.assertLess(
            workflow_semantics.index("Perform read-only browser-framework detection"),
            workflow_semantics.index("validate an existing manifest"),
        )
        self.assertIn("Use the protocol utility only to persist that outcome", protocol)

        self.assertIn(
            "`execution_environment` | distinct sanitized record with "
            "`browser_project`, `browser_version` when available, "
            "`os_platform`, `runtime`, `application_build_ref`, "
            "`target_reference`, and `target_tier`; never copy secrets",
            workflow_semantics,
        )
        self.assertIn("| `manifest_revision_consumed` | revision read before the evidence-producing run", workflow)
        self.assertNotIn("| `manifest_revision` |", workflow)
        self.assertIn("| `phase` | current evaluator phase name", workflow)
        for handoff_field in (
            "reproduction_steps", "expected_behavior", "actual_behavior", "artifact_refs",
            "evidence_ids", "journey_ids", "capability", "resume",
        ):
            self.assertIn(f"`{handoff_field}`", workflow)
        self.assertIn("Choose exactly one mutually exclusive primary outcome.", failure_semantics)
        self.assertIn(
            "only a `test-defect` at `0.80` or higher may enter repair.",
            failure_semantics,
        )
        self.assertIn(
            "use `inconclusive` and stop rather than repair.", failure_semantics
        )
        self.assertIn("an explicit allowed-path list.", repair_semantics)
        self.assertIn("must not include application source", repair_semantics)
        self.assertIn(
            "compare every changed test's assertions and journey comments",
            repair_semantics,
        )
        self.assertIn("Do not exceed either repair or wall-clock budget.", repair_semantics)
        self.assertIn("After every repair, invoke `verify`", repair_semantics)
        self.assertIn("Never hand-edit a manifest", protocol_semantics)
        self.assertLess(
            protocol_semantics.index("First perform the workflow's read-only framework gate."),
            protocol_semantics.index("It can otherwise run directly"),
        )
        self.assertIn(
            "after read-only detection, create the durable unsupported-framework outcome without adding Playwright infrastructure.",
            protocol_semantics,
        )

    def test_protocol_documents_use_exact_schema_vocabulary(self):
        schema = (ROOT / "protocol/v1/manifest.schema.json").read_text()
        orchestrator_protocol = (ROOT / "skills/e2e-testing/references/protocol.md").read_text()
        workflow = (ROOT / "skills/e2e-testing/references/workflow.md").read_text()
        safety = (ROOT / "skills/e2e-testing/references/safety.md").read_text()

        for status in TRANSITIONS:
            self.assertIn(f'"{status}"', schema)
        self.assertNotIn("discovery-in-progress", orchestrator_protocol)
        self.assertNotIn("failure-recorded", orchestrator_protocol)
        self.assertNotIn("handoff_id", workflow)
        self.assertIn("| `id` | stable identifier for this delegation |", workflow)
        self.assertEqual(TARGET_TIERS, {"local", "ephemeral", "staging", "production", "unspecified"})
        self.assertIn("`ephemeral`", safety)
        self.assertIn("`unspecified`", safety)
        self.assertNotIn("| test |", safety)
        self.assertNotIn("| unknown |", safety)

    def test_every_documented_transition_edge_exists_in_protocol(self):
        protocol = (ROOT / "skills/e2e-testing/references/protocol.md").read_text()
        table = protocol.split("| From | Event | To |", 1)[1].split("Never upgrade", 1)[0]
        edges: set[tuple[str, str]] = set()
        for line in table.splitlines():
            if not line.startswith("|") or line.startswith("| ---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            source = re.fullmatch(r"`([^`]+)`", cells[0])
            target = re.fullmatch(r"`([^`]+)`", cells[2])
            self.assertIsNotNone(source, f"transition source must be one exact status: {cells[0]}")
            self.assertIsNotNone(target, f"transition target must be one exact status: {cells[2]}")
            assert source is not None and target is not None
            edge = (source.group(1), target.group(1))
            self.assertIn(edge[0], TRANSITIONS)
            self.assertIn(edge[1], TRANSITIONS[edge[0]], f"illegal documented transition: {edge}")
            edges.add(edge)
        self.assertIn(("planned", "ready-for-adapter"), edges)
        self.assertIn(("ready-for-adapter", "generated-unverified"), edges)

    def test_documented_handoff_fields_match_evaluator_vocabulary(self):
        workflow = (ROOT / "skills/e2e-testing/references/workflow.md").read_text()
        table = workflow.split("| Field | Meaning |", 1)[1].split("The handoff must", 1)[0]
        documented = set(re.findall(r"^\| `([^`]+)` \|", table, re.MULTILINE))
        self.assertEqual(documented, {
            "id", "capability", "requested_at", "manifest_revision", "journey_ids",
            "reproduction_steps", "expected_behavior", "actual_behavior", "artifact_refs",
            "evidence_ids", "resume", "result",
        })


if __name__ == "__main__":
    unittest.main()
