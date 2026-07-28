"""Contract tests for the portable E2E skill bundles."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from protocol.v2.e2e_protocol import TARGET_TIERS, TRANSITIONS


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
        web = ROOT / "skills/e2e-web/SKILL.md"
        self.assertTrue(web.is_file())
        self.assertFalse((ROOT / "skills/e2e-web-playwright").exists())

        skill = ROOT / "skills/e2e-testing/SKILL.md"
        orchestrator_text = skill.read_text()
        self.assertLess(len(orchestrator_text.splitlines()), 500)
        self.assertIn("name: e2e-testing", orchestrator_text)
        self.assertIn("description:", orchestrator_text)
        self.assertEqual(set(frontmatter(orchestrator_text)), {"name", "description"})
        self.assertIn("Default to `generate`", orchestrator_text)
        self.assertIn("generated-unverified", orchestrator_text)
        self.assertIn("`actions`", orchestrator_text)
        self.assertNotIn("next_actions", orchestrator_text)
        self.assertIn(
            "read-only interface discovery before accessing or creating `.e2e/` state",
            orchestrator_text,
        )
        self.assertLess(
            orchestrator_text.index("read-only interface discovery"),
            orchestrator_text.index("Otherwise validate and resume Protocol 2"),
        )
        self.assertIn("Protocol 2", orchestrator_text)
        self.assertIn("`e2e-web`", orchestrator_text)
        self.assertIn("`e2e-service`", orchestrator_text)
        self.assertIn("needs-clarification", orchestrator_text)
        self.assertIn("one primary surface", orchestrator_text)
        self.assertIn("`e2e-mobile`", orchestrator_text)
        self.assertIn("mobile", orchestrator_text)
        self.assertNotIn("desktop", orchestrator_text)
        self.assertNotIn("You are a senior", orchestrator_text)
        self.assertNotIn("allowed-tools:", orchestrator_text)
        self.assert_relative_links_exist(ROOT / "skills/e2e-testing")
        self.assert_relative_links_exist(ROOT / "skills/e2e-web")

        web_text = web.read_text()
        self.assertIn("name: e2e-web", web_text)
        self.assertIn("Playwright remains the V2 execution driver", web_text)
        self.assertIn("Protocol 2", web_text)
        self.assertIn("`--replace-protocol-1`", web_text)
        self.assertNotIn("e2e-web-playwright", web_text)
        self.assertNotIn("unsupported-framework", web_text)

        for playwright_api in ("page.getByRole", "test.describe", "expect("):
            self.assertNotIn(playwright_api, orchestrator_text)

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
        self.assertIn(
            "python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json",
            protocol,
        )
        self.assertIn(
            "python3 scripts/e2e_protocol.py init --project-root PROJECT --output "
            "PROJECT/.e2e/manifest.json --replace-protocol-1",
            protocol,
        )
        self.assertIn("python3 scripts/e2e_protocol.py validate PROJECT/.e2e/manifest.json", protocol)
        self.assertNotIn("skills/e2e-testing/scripts/e2e_protocol.py", protocol)

    def test_orchestrator_routes_service_and_database_support(self):
        orchestrator_text = (ROOT / "skills/e2e-testing/SKILL.md").read_text()
        self.assertIn("`e2e-service`", orchestrator_text)
        self.assertIn("one primary surface", orchestrator_text)
        self.assertIn("needs-clarification", orchestrator_text)
        self.assertIn("database-support.md", orchestrator_text)
        database_support = (ROOT / "skills/e2e-testing/references/database-support.md").read_text()
        for capability in ("database-setup", "database-cleanup", "database-diagnostics"):
            self.assertIn(capability, database_support)
        self.assertIn("acceptance oracle", database_support)
        self.assertIn("never claims `e2e.support` as a namespace", database_support)
        # Database support should not be in the service extension schema
        service_schema = json.loads(
            (ROOT / "skills/e2e-service/references/extensions/service.schema.json").read_text()
        )
        schema_text = json.dumps(service_schema)
        self.assertNotIn("database", schema_text.lower())

    def test_web_contract_and_orchestrator_boundary(self):
        web = ROOT / "skills/e2e-web/SKILL.md"
        web_text = web.read_text()
        orchestrator_text = (ROOT / "skills/e2e-testing/SKILL.md").read_text()

        self.assertLess(len(web_text.splitlines()), 500)
        self.assertIn("name: e2e-web", web_text)
        self.assertIn("description:", web_text)
        self.assertEqual(set(frontmatter(web_text)), {"name", "description"})
        self.assertIn("`plan`, `generate`, `verify`, or `repair`", web_text)
        self.assertIn("default to `generate`", web_text)
        self.assertIn("Validate and resume an existing Protocol 2 run", web_text)
        self.assertIn("read-only browser-framework detection", web_text)
        self.assertLess(
            web_text.index("read-only browser-framework detection"),
            web_text.index("Validate and resume an existing Protocol 2 run"),
        )
        self.assertIn("live inspection", web_text)
        self.assertIn("source/spec evidence", web_text)
        self.assertIn("`capability-unavailable`", web_text)
        self.assertNotIn("unsupported-framework", web_text)
        self.assertIn("generated-unverified", web_text)
        self.assertIn("recorded test defect", web_text)
        self.assertIn("test/support files only", web_text)
        self.assertIn("Repair changes are bounded by manifest budgets", web_text)
        self.assertIn("Never modify application code", web_text)
        self.assertIn("Never weaken expected outcomes", web_text)
        self.assertIn("unconditional skips", web_text)
        self.assertIn("hardcoded sleeps", web_text)
        self.assertIn("product defects", web_text)
        self.assertIn("fix-product-defect capability handoff", web_text)
        self.assertNotIn("e2e-web-playwright", web_text)
        self.assert_relative_links_exist(ROOT / "skills/e2e-web")

        for playwright_api in ("page.getByRole", "test.describe", "expect("):
            self.assertNotIn(playwright_api, orchestrator_text)

    def test_web_reference_safety_contract(self):
        references = ROOT / "skills/e2e-web/references"
        workflow = (references / "workflow.md").read_text()
        workflow_semantics = " ".join(workflow.split())
        failure = (references / "failure-classification.md").read_text()
        failure_semantics = " ".join(failure.split())
        repair = (references / "repair-guardrails.md").read_text()
        repair_semantics = " ".join(repair.split())
        protocol = (references / "protocol.md").read_text()
        protocol_semantics = " ".join(protocol.split())

        self.assertIn(
            "Perform read-only browser-framework detection before validating, "
            "initializing, or resuming Protocol 2",
            workflow,
        )
        self.assertIn("even when Playwright is also present", workflow)
        self.assertIn("unconditionally stop as `capability-unavailable`", workflow)
        self.assertIn("After detection, persist a valid `capability-unavailable` outcome", workflow)
        self.assertIn("durable manifest outcome after read-only detection", workflow_semantics)
        self.assertLess(
            workflow_semantics.index("Perform read-only browser-framework detection"),
            workflow_semantics.index("validate and resume an existing Protocol 2 run"),
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
        self.assertIn('{"resume": {"command": "e2e-web verify"}}', workflow)
        self.assertIn("| `check_ids` | immutable selected check IDs |", workflow)
        self.assertIn("`outcomes[].check_id`", workflow)
        self.assertNotIn("`test_ids`", workflow)
        self.assertIn('{"resume": {"command": "e2e-web verify"}}', failure)
        self.assertNotIn("e2e-web-playwright verify", workflow)
        self.assertIn("do not repair application code", failure_semantics)
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
            "after read-only detection, create the durable capability-unavailable outcome "
            "without adding Playwright infrastructure.",
            protocol_semantics,
        )
        self.assertNotIn("unsupported-framework", protocol_semantics)
        self.assertNotIn("e2e-web-playwright", protocol_semantics)

    def test_protocol_documents_use_exact_schema_vocabulary(self):
        schema = (ROOT / "protocol/v2/manifest.schema.json").read_text()
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

    def test_active_surfaces_have_no_legacy_web_runtime_contract(self):
        active_files = [ROOT / "README.md", ROOT / "scripts/sync_protocol.py"]
        for directory in (ROOT / "skills", ROOT / "evals"):
            active_files.extend(
                path for path in directory.rglob("*")
                if path.is_file()
                and "fixtures" not in path.parts
                and "results" not in path.parts
                and "__pycache__" not in path.parts
            )
        legacy_name = "e2e-web-" + "playwright"
        for path in active_files:
            if path.suffix not in {".md", ".json", ".py"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(legacy_name, text, path.relative_to(ROOT))
            self.assertNotIn("Protocol 1.0 is the manifest contract", text, path.relative_to(ROOT))

    def test_service_skill_contract(self):
        service_text = (ROOT / "skills/e2e-service/SKILL.md").read_text()
        self.assertIn("name: e2e-service", service_text)
        self.assertIn("default to generate mode", service_text)
        self.assertIn("one logical system", service_text)
        self.assertIn("confirmed supported external boundary", service_text)
        self.assertIn("repository-native", service_text)
        self.assertIn("generated-unverified", service_text)
        repair = (ROOT / "skills/e2e-service/references/repair-guardrails.md").read_text()
        self.assertIn("Never modify application code", repair)
        for module in ("HTTP", "GraphQL", "gRPC", "WebSocket", "queue", "stream"):
            self.assertIn(module, service_text)
        for forbidden in ("e2e-http", "e2e-grpc", "database surface", "test_ids"):
            self.assertNotIn(forbidden, service_text)
        refs = (ROOT / "skills/e2e-service/references").iterdir()
        for ref in ("workflow.md", "protocol.md", "safety.md", "failure-classification.md",
                    "repair-guardrails.md", "http.md", "graphql.md", "grpc.md",
                    "websocket.md", "queue.md", "stream.md"):
            self.assertTrue((ROOT / "skills/e2e-service/references" / ref).exists(), ref)

    def test_active_bundles_publish_protocol_2_and_web_extension(self):
        for skill in ("e2e-testing", "e2e-web"):
            root = ROOT / "skills" / skill
            schema = json.loads((root / "references/manifest.schema.json").read_text())
            web = json.loads((root / "references/extensions/web.schema.json").read_text())
            self.assertEqual(schema["properties"]["protocol_version"]["const"], "2.0")
            self.assertEqual(web["$id"], "urn:e2e-testing:extension:web:1.0")
        service = ROOT / "skills" / "e2e-service"
        self.assertTrue((service / "SKILL.md").exists())
        self.assertTrue((service / "references/manifest.schema.json").exists())
        service_schema = json.loads((service / "references/manifest.schema.json").read_text())
        self.assertEqual(service_schema["properties"]["protocol_version"]["const"], "2.0")
        service_ext = json.loads((service / "references/extensions/service.schema.json").read_text())
        self.assertEqual(service_ext["$id"], "urn:e2e-testing:extension:service:1.0")

    def test_protocol_kernel_is_surface_neutral_and_portable(self):
        runtime = (ROOT / "protocol/v2/e2e_protocol.py").read_text()
        helper = (ROOT / "protocol/v2/extension_catalog.py").read_text()
        for forbidden in ("e2e.web", "e2e.service", "jsonschema"):
            self.assertNotIn(forbidden, runtime)
            self.assertNotIn(forbidden, helper)

    def test_active_bundles_publish_registered_web_catalogs(self):
        for skill in ("e2e-web",):
            root = ROOT / "skills" / skill
            catalog = json.loads((root / "references/extensions/catalog.json").read_text())
            self.assertEqual(
                {entry["namespace"] for entry in catalog["extensions"]},
                {"e2e.web"},
            )
            support = catalog["extensions"][0]["versions"]
            self.assertEqual(support, [{
                "minimum": "1.0", "maximum": "1.0",
                "dialect": "draft2020-12-subset-1", "schema": "web.schema.json",
            }])
            self.assertTrue((root / "scripts/extension_catalog.py").is_file())
        orchestrator = ROOT / "skills" / "e2e-testing"
        orchestrator_catalog = json.loads((orchestrator / "references/extensions/catalog.json").read_text())
        self.assertEqual(
            {entry["namespace"] for entry in orchestrator_catalog["extensions"]},
            {"e2e.web", "e2e.service", "e2e.mobile"},
        )
        service = ROOT / "skills" / "e2e-service"
        service_catalog = json.loads((service / "references/extensions/catalog.json").read_text())
        self.assertEqual(
            {entry["namespace"] for entry in service_catalog["extensions"]},
            {"e2e.service"},
        )
        self.assertTrue((service / "scripts/extension_catalog.py").is_file())


if __name__ == "__main__":
    unittest.main()
