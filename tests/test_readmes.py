"""Contracts for tracked project onboarding documents."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeContractTests(unittest.TestCase):
    def test_active_protocol_and_roadmap_do_not_publish_runtime_migration(self):
        roadmap = (ROOT / "docs/roadmap.md").read_text()
        protocol = (ROOT / "protocol/v2/README.md").read_text()
        self.assertIn("fresh Protocol 2", roadmap)
        self.assertIn("offline historical", roadmap.lower())
        self.assertNotIn("Lossless Protocol 1 migration", roadmap)
        self.assertNotIn("V1 web history migrates losslessly", roadmap)
        self.assertIn("Offline historical utility", protocol)
        self.assertIn("--replace-protocol-1", protocol)
        self.assertNotIn("Migration is explicit and lossless", protocol)

    def test_project_readme_covers_user_and_contributor_entry_points(self):
        text = (ROOT / "README.md").read_text()
        for required in (
            "e2e-testing",
            "e2e-web",
            "e2e-service",
            "Protocol 2",
            "## Installation",
            "## Quick start",
            "## Modes",
            "## Safety boundaries",
            "## Repository layout",
            "## Contributing",
        ):
            self.assertIn(required, text)

        for relative in (
            "skills/e2e-testing/SKILL.md",
            "skills/e2e-web/SKILL.md",
            "skills/e2e-service/SKILL.md",
            "evals/fixtures/README.md",
            "evals/HOST_EVALUATION.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertIn(relative, text)

        self.assertNotIn("e2e-web-playwright", text)
        self.assertNotIn("Protocol 1.0", text)

    def test_roadmap_describes_one_atomic_service_delivery(self):
        roadmap = (ROOT / "docs/roadmap.md").read_text()
        self.assertIn("one atomic", roadmap)
        self.assertIn("e2e-service", roadmap)
        for module in ("REST", "GraphQL", "gRPC", "WebSocket", "queue", "stream"):
            self.assertIn(module, roadmap)
        self.assertNotIn("service foundation with REST/HTTP; GraphQL; gRPC", roadmap)
        for version, capability in (("V3", "Mobile"), ("V4", "Desktop"), ("V5", "composition"), ("V6", "Resilience")):
            self.assertIn(version, roadmap)
            self.assertIn(capability, roadmap)

    def test_fixture_readme_explains_tracked_integrity_manifests(self):
        text = (ROOT / "evals" / "fixtures" / "README.md").read_text()
        for required in (
            ".fixture-baseline.json",
            "SHA-256",
            "source-controlled",
            "preserved",
            "created",
            "changed",
            "python3 -m unittest tests.test_evaluation_contracts.FixtureContractTests -v",
        ):
            self.assertIn(required, text)

    def test_project_readme_publishes_mobile_surface(self):
        text = (ROOT / "README.md").read_text()
        for required in (
            "e2e-mobile",
            "Appium",
            "Maestro",
            "installed iOS and Android",
            "skills/e2e-mobile/SKILL.md",
        ):
            self.assertIn(required, text)

    def test_roadmap_records_atomic_v3_mobile_delivery(self):
        roadmap = (ROOT / "docs/roadmap.md").read_text()
        self.assertIn("V3 — Mobile UI", roadmap)
        self.assertIn("one atomic `e2e-mobile`", roadmap)
        self.assertIn("Appium", roadmap)
        self.assertIn("Maestro", roadmap)
        self.assertIn("iOS simulator", roadmap)
        self.assertIn("Android emulator", roadmap)
        self.assertIn("real or remote", roadmap)

    def test_mobile_platform_acceptance_is_explicitly_authorized(self):
        text = (ROOT / "evals/MOBILE_PLATFORM_ACCEPTANCE.md").read_text()
        for required in (
            "explicit reviewer authorization",
            "Appium",
            "Maestro",
            "iOS simulator",
            "Android emulator",
            "real or remote",
            "selected check IDs",
            "cleanup evidence",
            "fixture evidence cannot",
        ):
            self.assertIn(required, text)

    def test_host_evaluation_guide_preserves_existing_procedure_and_adds_mobile(self):
        text = (ROOT / "evals/HOST_EVALUATION.md").read_text()
        for required in (
            "Authorized host evaluation",
            "explicitly approved that individual evaluation session",
            "disposable fixture workspace",
            "review the retained transcript for secret leakage",
            "--host-timeout",
            "The source repository is never the host working directory",
            "greenfield-source",
            "service-multi-protocol",
            "mobile-generate-appium",
            "mobile-generate-maestro",
            "mobile-verify-lifecycle",
            "mobile-production-refusal",
            "Without `--keep-results`",
        ):
            self.assertIn(required, text)
        self.assertEqual(text.count("### Mobile cases"), 2)


if __name__ == "__main__":
    unittest.main()
