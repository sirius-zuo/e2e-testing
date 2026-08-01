"""Evaluate E2E skill output from durable workspace artifacts only."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import math
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from evals.desktop_contract import check_desktop_contract


ROOT = Path(__file__).resolve().parents[1]
BUNDLED_PROTOCOL = ROOT / "skills" / "e2e-testing" / "scripts" / "e2e_protocol.py"
CHECKPOINT_RUN_ID = re.compile(r"run-[a-z0-9-]+$")
WORKSPACE_BASELINE = "workspace-baseline.json"
PROTECTED_SKILL_ROOTS = (".agents/skills/", ".claude/skills/")


def _load_protocol():
    spec = importlib.util.spec_from_file_location("bundled_e2e_protocol", BUNDLED_PROTOCOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load bundled protocol validator: {BUNDLED_PROTOCOL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUNDLED_PROTOCOL_MODULE = _load_protocol()


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    return (
        BUNDLED_PROTOCOL_MODULE.validate_manifest(manifest)
        + BUNDLED_PROTOCOL_MODULE.validate_v2_policy(manifest)
    )


def _spawn_setup(command: str, workspace: Path) -> subprocess.Popen:
    """Launch fixture setup separately so host-process mocks do not affect it."""
    return subprocess.Popen(shlex.split(command), cwd=workspace)


@contextmanager
def running_setup(case: dict[str, Any], workspace: Path):
    """Run a fixture's optional local server and always terminate it."""
    setup = case.get("setup")
    if not setup:
        yield
        return
    command = setup["command"]
    process = _spawn_setup(command, workspace)
    deadline = time.monotonic() + setup["timeout_seconds"]
    try:
        while True:
            try:
                with urllib.request.urlopen(setup["ready_url"], timeout=0.25) as response:
                    if response.status < 500:
                        break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"fixture setup did not become ready: {setup['ready_url']}")
                time.sleep(0.05)
        yield
    finally:
        try:
            process.terminate()
        except OSError:
            force_kill = True
        else:
            force_kill = False
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                force_kill = True

        if force_kill:
            try:
                process.kill()
            except OSError:
                pass
            else:
                try:
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    # Cleanup must not mask a host timeout or evaluator error.
                    pass


def _read_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"missing {label}: {path.name}"]
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"invalid {label}: {error}"]
    if not isinstance(value, dict):
        return None, [f"invalid {label}: expected object"]
    return value, []


def _phase_expectation(case: dict[str, Any], phase: str | None) -> tuple[dict[str, Any], list[str]]:
    if phase is None:
        return case["expect"], []
    for item in case.get("phases", []):
        if item.get("name") == phase:
            expect = dict(case["expect"])
            expect.update(item.get("expect", {}))
            expect["_phase_name"] = phase
            if "checkpoint" in item:
                expect["_checkpoint"] = item["checkpoint"]
            if "resume_from" in item:
                expect["_resume_from"] = item["resume_from"]
            if "apply_patch" in item:
                expect["_apply_patch"] = item["apply_patch"]
            return expect, []
    return {}, [f"unknown phase: {phase}"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches(relative_path: str, pattern: str) -> bool:
    # ``**/`` means zero or more directories in the case contract, while
    # fnmatch treats it as requiring one directory.
    return (
        fnmatch.fnmatchcase(relative_path, pattern)
        or fnmatch.fnmatchcase(relative_path, pattern.replace("**/", ""))
    )


def _workspace_files(workspace: Path) -> list[tuple[str, Path]]:
    return sorted(
        (path.relative_to(workspace).as_posix(), path)
        for path in workspace.rglob("*")
        if path.is_file()
    )


def _workspace_baseline_digest(files: dict[str, str]) -> str:
    encoded = json.dumps(
        files,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _run(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("run")
    return value if isinstance(value, dict) else {}


def _systems(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    value = manifest.get("systems")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _run_value(manifest: dict[str, Any], field: str) -> Any:
    return _run(manifest).get(field)


def _check_required_ids(manifest: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    collections = {
        "journey": "journeys",
        "check": "checks",
        "evidence": "evidence",
        "handoff": "handoffs",
        "action": "actions",
        "attempt": "attempts",
    }
    for label, collection in collections.items():
        for required_id in expect.get(f"required_{label}_ids", []):
            if required_id not in _ids(manifest.get(collection)):
                diagnostics.append(f"missing {label.replace('_', ' ')} ID: {required_id}")
    return diagnostics


def _check_traceability(manifest: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    required = expect.get("journey_traceability", [])
    if isinstance(required, dict):
        required = list(required)
    checks_by_journey = {
        item.get("journey_id")
        for item in manifest.get("checks", [])
        if isinstance(item, dict) and isinstance(item.get("journey_id"), str)
    }
    return [
        f"missing journey traceability: {journey_id}"
        for journey_id in required
        if journey_id not in checks_by_journey
    ]


def _is_execution_evidence(item: Any, check_ids: set[str], surface: str) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("support_only") is True:
        return False
    command = item.get("command")
    if not isinstance(command, str) or not command.strip():
        return False
    exit_code = item.get("exit_code")
    duration = item.get("duration_ms")
    if (
        type(exit_code) is not int
        or exit_code != 0
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or (isinstance(duration, float) and not math.isfinite(duration))
        or duration < 0
    ):
        return False
    selected = item.get("check_ids")
    outcomes = item.get("outcomes")
    environment = item.get("execution_environment")
    if not isinstance(selected, list) or not selected or not all(isinstance(check_id, str) for check_id in selected):
        return False
    if not set(selected) <= check_ids or not isinstance(outcomes, list):
        return False
    outcome_ids = {
        outcome.get("check_id")
        for outcome in outcomes
        if isinstance(outcome, dict) and outcome.get("status") == "passed"
    }
    return (
        set(selected) <= outcome_ids
        and _execution_environment_is_valid(environment, surface)
    )


def _is_failed_execution_evidence(item: Any, check_ids: set[str], surface: str) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("support_only") is True:
        return False
    command = item.get("command")
    command_ref = item.get("command_ref")
    if not any(isinstance(value, str) and value.strip() for value in (command, command_ref)):
        return False
    exit_code = item.get("exit_code")
    duration = item.get("duration_ms")
    if (
        isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code == 0
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or (isinstance(duration, float) and not math.isfinite(duration))
        or duration < 0
    ):
        return False
    selected = item.get("check_ids")
    outcomes = item.get("outcomes")
    environment = item.get("execution_environment")
    if not isinstance(selected, list) or not selected or not all(isinstance(check_id, str) for check_id in selected):
        return False
    if not set(selected) <= check_ids or not isinstance(outcomes, list):
        return False
    failed_ids = {
        outcome.get("check_id")
        for outcome in outcomes
        if isinstance(outcome, dict) and outcome.get("status") == "failed"
    }
    return (
        set(selected) <= failed_ids
        and _execution_environment_is_valid(environment, surface)
    )


def _classification(item: Any, primary: str) -> bool:
    if not isinstance(item, dict) or not isinstance(item.get("classification"), dict):
        return False
    classification = item["classification"]
    confidence = classification.get("confidence")
    return (
        classification.get("primary") == primary
        and not isinstance(confidence, bool)
        and isinstance(confidence, (int, float))
        and 0.8 <= confidence <= 1.0
        and math.isfinite(confidence)
        and isinstance(classification.get("rationale"), str)
        and bool(classification["rationale"].strip())
        and isinstance(classification.get("evidence_ids"), list)
        and bool(classification["evidence_ids"])
    )


def _check_expected_classifications(
    manifest: dict[str, Any],
    expect: dict[str, Any],
) -> list[str]:
    evidence = manifest.get("evidence")
    records = evidence if isinstance(evidence, list) else []
    evidence_ids = _ids(records)
    required_evidence_ids = {
        item
        for item in expect.get("required_evidence_ids", [])
        if isinstance(item, str)
    }

    def is_bound_classification(item: Any, primary: str) -> bool:
        if not _classification(item, primary):
            return False
        references = item["classification"]["evidence_ids"]
        record_id = item.get("id")
        return (
            all(isinstance(reference, str) for reference in references)
            and set(references) <= evidence_ids
            and record_id not in references
            and (
                not required_evidence_ids
                or bool(set(references) & required_evidence_ids)
            )
        )

    return [
        f"missing evidence classification: {primary}"
        for primary in expect.get("required_classifications", [])
        if not any(is_bound_classification(item, primary) for item in records)
    ]


def _check_expected_action_capabilities(
    manifest: dict[str, Any],
    expect: dict[str, Any],
) -> list[str]:
    actions = manifest.get("actions")
    records = actions if isinstance(actions, list) else []
    evidence = manifest.get("evidence")
    evidence_records = evidence if isinstance(evidence, list) else []
    evidence_ids = _ids(evidence_records)
    required_evidence_ids = {
        item
        for item in expect.get("required_evidence_ids", [])
        if isinstance(item, str)
    }
    journey_ids = _ids(manifest.get("journeys"))
    required_journey_ids = {
        item
        for item in expect.get("required_journey_ids", [])
        if isinstance(item, str)
    }
    required_check_ids = {
        item
        for item in expect.get("required_check_ids", [])
        if isinstance(item, str)
    }
    required_journey_ids.update(
        item.get("journey_id")
        for item in manifest.get("checks", [])
        if isinstance(item, dict)
        and item.get("id") in required_check_ids
        and isinstance(item.get("journey_id"), str)
    )

    def has_bound_action(capability: str) -> bool:
        for action in records:
            if not isinstance(action, dict) or action.get("capability") != capability:
                continue
            scoped_journeys = action.get("journey_ids")
            if (
                not isinstance(scoped_journeys, list)
                or not all(isinstance(item, str) for item in scoped_journeys)
                or not set(scoped_journeys) <= journey_ids
                or (
                    required_journey_ids
                    and not required_journey_ids <= set(scoped_journeys)
                )
            ):
                continue
            if capability == "mobile-cleanup":
                if any(
                    isinstance(item, dict)
                    and item.get("cleanup_action_id") == action.get("id")
                    and (
                        not required_evidence_ids
                        or item.get("id") in required_evidence_ids
                    )
                    for item in evidence_records
                ):
                    return True
                continue
            references = action.get("evidence_ids")
            if (
                isinstance(references, list)
                and bool(references)
                and all(isinstance(reference, str) for reference in references)
                and set(references) <= evidence_ids
                and (
                    not required_evidence_ids
                    or bool(set(references) & required_evidence_ids)
                )
            ):
                return True
        return False

    return [
        f"missing action capability: {capability}"
        for capability in expect.get("required_action_capabilities", [])
        if not has_bound_action(capability)
    ]


def _check_forbidden_execution(
    evidence: Any,
    expect: dict[str, Any],
) -> list[str]:
    if expect.get("forbid_execution") is not True:
        return []
    records = evidence if isinstance(evidence, list) else []

    def is_attempt(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        if any(
            isinstance(item.get(field), str) and bool(item[field].strip())
            for field in ("command", "command_ref")
        ):
            return True
        if (
            ("exit_code" in item and type(item.get("exit_code")) is int)
            or (
                "duration_ms" in item
                and isinstance(item.get("duration_ms"), (int, float))
                and not isinstance(item.get("duration_ms"), bool)
            )
        ):
            return True
        for operation in ("build", "install", "launch", "driver"):
            for field in (
                f"{operation}_attempt",
                f"{operation}_attempted",
                f"attempted_{operation}",
            ):
                value = item.get(field)
                if value is True or isinstance(value, dict):
                    return True
        attempt = item.get("attempt")
        return (
            isinstance(attempt, dict)
            and attempt.get("kind") in {"build", "install", "launch", "driver"}
        )

    attempted_execution = any(
        is_attempt(item)
        for item in records
    )
    if attempted_execution:
        return ["mobile case forbids execution evidence"]
    return []


def _linked_classification(
    item: Any,
    primary: str,
    evidence_ids: set[str],
    required_evidence_ids: set[str],
) -> bool:
    if not _classification(item, primary):
        return False
    references = item["classification"]["evidence_ids"]
    return (
        all(isinstance(reference, str) for reference in references)
        and set(references) <= evidence_ids
        and bool(set(references) & required_evidence_ids)
    )


def _check_status_evidence(manifest: dict[str, Any], expect: dict[str, Any], surface: str) -> list[str]:
    status = _run_value(manifest, "status")
    evidence = manifest.get("evidence")
    checks = manifest.get("checks")
    handoffs = manifest.get("handoffs")
    actions = manifest.get("actions")
    if not isinstance(evidence, list):
        return []
    check_ids = _ids(checks)
    diagnostics: list[str] = []
    if status == "verified":
        successful_execution = any(_is_execution_evidence(item, check_ids, surface) for item in evidence)
        if not successful_execution:
            diagnostics.append("verified status requires successful selected-check execution evidence")
        scoped_journey_ids = set(expect.get("required_journey_ids", []))
        check_records = checks if isinstance(checks, list) else []
        scoped_check_ids = {
            item["id"]
            for item in check_records
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and (not scoped_journey_ids or item.get("journey_id") in scoped_journey_ids)
        }
        expected_phase = expect.get("_phase_name", _run_value(manifest, "mode"))
        expected_revision = _run_value(manifest, "revision")
        valid_final_revision = type(expected_revision) is int and expected_revision >= 1
        if not valid_final_revision:
            diagnostics.append(
                "verified status requires final manifest revision to be a non-boolean integer >= 1"
            )
        evidence_by_id = {
            item["id"]: item
            for item in evidence
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for required_id in expect.get("required_execution_evidence_ids", []):
            item = evidence_by_id.get(required_id)
            selected_ids = set(item.get("check_ids", [])) if isinstance(item, dict) else set()
            if not _is_execution_evidence(item, check_ids, surface) or not (
                item.get("phase") == expected_phase and scoped_check_ids <= selected_ids
            ):
                diagnostics.append(
                    "required execution evidence is not bound to this phase, revision, and scoped tests: "
                    f"{required_id}"
                )
                continue
            consumed_revision = item.get("manifest_revision_consumed")
            if type(consumed_revision) is not int or consumed_revision < 0:
                diagnostics.append(
                    "required execution evidence manifest_revision_consumed must be a non-boolean integer >= 0: "
                    f"{required_id}"
                )
                continue
            if valid_final_revision and expected_revision != consumed_revision + 1:
                diagnostics.append(
                    "required execution evidence is not bound to this phase, revision, and scoped tests: "
                    f"{required_id}"
                )
    if status == "capability-unavailable":
        if surface == "web":
            valid_capability_evidence = any(
                isinstance(item, dict)
                and isinstance(item.get("framework"), str)
                and item["framework"]
                and isinstance(item.get("source_locations"), list)
                and bool(item["source_locations"])
                and item.get("read_only") is True
                for item in evidence
            )
            if not valid_capability_evidence:
                diagnostics.append("missing capability-unavailable framework detection evidence")
        else:
            valid_capability_evidence = any(
                isinstance(item, dict)
                and item.get("surface") == surface
                and isinstance(item.get("adapter"), str)
                and item["adapter"]
                and isinstance(item.get("source_locations"), list)
                and bool(item["source_locations"])
                and item.get("read_only") is True
                for item in evidence
            )
            if not valid_capability_evidence:
                diagnostics.append("missing capability-unavailable adapter detection evidence")
    if status == "handoff-required":
        evidence_ids = _ids(evidence)
        failed_evidence_ids = {
            item["id"]
            for item in evidence
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and _is_failed_execution_evidence(item, check_ids, surface)
        }
        classification_ids = {
            item["id"]
            for item in evidence
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and _linked_classification(item, "product-defect", evidence_ids, failed_evidence_ids)
        }
        artifact_ids = {
            artifact["id"]
            for item in evidence
            if isinstance(item, dict) and isinstance(item.get("artifacts"), list)
            for artifact in item["artifacts"]
            if isinstance(artifact, dict) and isinstance(artifact.get("id"), str)
        }
        valid_handoff = any(
            isinstance(item, dict)
            and item.get("capability") == "fix-product-defect"
            and isinstance(item.get("journey_ids"), list)
            and bool(item["journey_ids"])
            and set(item["journey_ids"]) <= _ids(manifest.get("journeys"))
            and isinstance(item.get("resume"), dict)
            and isinstance(item["resume"].get("command"), str)
            and bool(item["resume"]["command"].strip())
            and isinstance(item.get("reproduction_steps"), list)
            and bool(item["reproduction_steps"])
            and all(isinstance(step, str) and step.strip() for step in item["reproduction_steps"])
            and isinstance(item.get("expected_behavior"), str)
            and bool(item["expected_behavior"].strip())
            and isinstance(item.get("actual_behavior"), str)
            and bool(item["actual_behavior"].strip())
            and isinstance(item.get("artifact_refs"), list)
            and bool(item["artifact_refs"])
            and set(item["artifact_refs"]) <= artifact_ids
            and isinstance(item.get("evidence_ids"), list)
            and bool(item["evidence_ids"])
            and set(item["evidence_ids"]) <= evidence_ids
            and bool(set(item["evidence_ids"]) & failed_evidence_ids)
            and bool(set(item["evidence_ids"]) & classification_ids)
            for item in handoffs if isinstance(handoffs, list)
        )
        if not failed_evidence_ids or not classification_ids:
            diagnostics.append(
                "handoff-required status requires failed selected-test execution and linked product-defect classification evidence"
            )
        if not valid_handoff:
            diagnostics.append(
                "handoff-required status requires complete product-defect handoff details with valid evidence and artifact refs"
            )
    if status == "needs-authorization":
        valid_action = any(
            isinstance(item, dict)
            and isinstance(item.get("capability"), str)
            and bool(item["capability"])
            and isinstance(item.get("journey_ids"), list)
            for item in actions if isinstance(actions, list)
        )
        if not any(_classification(item, "authorization-required") for item in evidence) or not valid_action:
            diagnostics.append("needs-authorization status requires authorization classification and actionable handoff evidence")
    if _run_value(manifest, "mode") == "repair" and status == "verified":
        attempts = manifest.get("attempts")
        valid_attempt = any(
            isinstance(item, dict)
            and isinstance(item.get("check_ids"), list)
            and bool(item["check_ids"])
            and isinstance(item.get("allowed_paths"), list)
            and bool(item["allowed_paths"])
            and isinstance(item.get("assertion_comparison"), str)
            and bool(item["assertion_comparison"].strip())
            for item in attempts if isinstance(attempts, list)
        )
        if not any(_classification(item, "test-defect") for item in evidence) or not valid_attempt:
            diagnostics.append("repair verification requires classified repair and bounded attempt evidence")
    if status == "blocked" and "evidence-budget-exhausted" in expect.get("required_evidence_ids", []):
        attempts = _ids(manifest.get("attempts"))
        valid_budget_evidence = any(
            isinstance(item, dict)
            and item.get("id") == "evidence-budget-exhausted"
            and item.get("budget_exhausted") is True
            and item.get("budget") in {"repair", "verification", "wall_clock_seconds"}
            and isinstance(item.get("attempt_id"), str)
            and item["attempt_id"] in attempts
            and isinstance(item.get("reason"), str)
            and bool(item["reason"].strip())
            for item in evidence
        )
        if not valid_budget_evidence:
            diagnostics.append("blocked budget outcome requires budget and attempt evidence")
    return diagnostics


def _check_files(
    workspace: Path,
    fixture: Path,
    expect: dict[str, Any],
    state_dir: Path | None = None,
) -> list[str]:
    diagnostics: list[str] = []
    baseline, baseline_errors = _read_json(fixture / ".fixture-baseline.json", "fixture baseline")
    if baseline_errors:
        return baseline_errors
    assert baseline is not None
    files = _workspace_files(workspace)
    names = {relative for relative, _ in files}

    for pattern in expect.get("unchanged_globs", []):
        matches = sorted(relative for relative in baseline if _matches(relative, pattern))
        if not matches:
            diagnostics.append(f"preserved glob matched no baseline files: {pattern}")
        for relative in matches:
            actual = workspace / relative
            if not actual.is_file() or _sha256(actual) != baseline[relative]:
                diagnostics.append(f"forbidden change: {relative}")

    for pattern in expect.get("absent_globs", []):
        for relative in sorted(name for name in names if _matches(name, pattern)):
            diagnostics.append(f"forbidden path present: {relative}")

    for pattern in expect.get("present_globs", []):
        if not any(_matches(name, pattern) for name in names):
            diagnostics.append(f"required path missing: {pattern}")
    for pattern in expect.get("created_globs", []):
        if not any(_matches(name, pattern) and name not in baseline for name in names):
            diagnostics.append(f"required new path missing: {pattern}")
    for pattern in expect.get("changed_globs", []):
        matches = [relative for relative in baseline if _matches(relative, pattern)]
        if not any(
            (workspace / relative).is_file() and _sha256(workspace / relative) != baseline[relative]
            for relative in matches
        ):
            diagnostics.append(f"required change missing: {pattern}")
    allowed_change_globs = expect.get("allowed_change_globs")
    if isinstance(allowed_change_globs, list):
        installed_baseline: dict[str, Any] = {}
        external_baseline_valid = True
        if state_dir is not None:
            snapshot, snapshot_errors = _read_json(
                state_dir / WORKSPACE_BASELINE,
                "workspace baseline",
            )
            if snapshot_errors:
                diagnostics.extend(snapshot_errors)
                external_baseline_valid = False
            elif (
                set(snapshot) != {
                    "version",
                    "file_count",
                    "files_digest",
                    "files",
                }
                or type(snapshot.get("version")) is not int
                or snapshot["version"] != 1
                or not isinstance(snapshot.get("files"), dict)
                or not all(
                    isinstance(relative, str)
                    and bool(relative)
                    and isinstance(digest, str)
                    and re.fullmatch(r"[0-9a-f]{64}", digest)
                    for relative, digest in snapshot.get("files", {}).items()
                )
            ):
                diagnostics.append(
                    "invalid workspace baseline: expected SHA-256 hash map envelope"
                )
                external_baseline_valid = False
            else:
                assert snapshot is not None
                installed_baseline = snapshot["files"]
                if (
                    type(snapshot.get("file_count")) is not int
                    or snapshot["file_count"] != len(installed_baseline)
                    or not isinstance(snapshot.get("files_digest"), str)
                    or snapshot["files_digest"]
                    != _workspace_baseline_digest(installed_baseline)
                ):
                    diagnostics.append(
                        "invalid workspace baseline: completeness check failed"
                    )
                    external_baseline_valid = False
        if external_baseline_valid:
            initial_baseline = dict(baseline)
            initial_baseline.update(installed_baseline)
            baseline_names = set(initial_baseline)
            current_names = {relative for relative, _ in files}
            changed_or_created = {
                relative
                for relative, path in files
                if (
                    relative not in baseline_names
                    or _sha256(path) != initial_baseline[relative]
                )
                and not relative.startswith(".e2e/")
                and relative != ".fixture-baseline.json"
            }
            changed_or_created.update(baseline_names - current_names)
            for relative in sorted(changed_or_created):
                protected = relative.startswith(PROTECTED_SKILL_ROOTS)
                if protected or not any(
                    _matches(relative, pattern)
                    for pattern in allowed_change_globs
                ):
                    diagnostics.append(
                        f"unauthorized mobile case change: {relative}"
                    )
    for relative, expected_hash in expect.get("expected_file_hashes", {}).items():
        actual = workspace / relative
        if not actual.is_file() or _sha256(actual) != expected_hash:
            diagnostics.append(f"unexpected repaired content: {relative}")
    return diagnostics


def _checkpoint_path(state_dir: Path, case_id: str, phase: str) -> Path:
    return state_dir / f"{case_id}-{phase}.json"


def _check_continuity(state_dir: Path | None, case: dict[str, Any], manifest: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    previous_phase = expect.get("_resume_from")
    if not previous_phase:
        return []
    if state_dir is None:
        return ["missing evaluator state directory"]
    checkpoint, errors = _read_json(_checkpoint_path(state_dir, case["id"], previous_phase), "phase checkpoint")
    if errors:
        return [
            f"missing phase checkpoint: {previous_phase}"
            if errors[0].startswith("missing") else f"invalid phase checkpoint: {previous_phase}"
        ]
    assert checkpoint is not None
    if (
        set(checkpoint) != {"run_id", "revision", "handoff_ids"}
        or not isinstance(checkpoint["run_id"], str)
        or not CHECKPOINT_RUN_ID.fullmatch(checkpoint["run_id"])
        or not isinstance(checkpoint["revision"], int)
        or isinstance(checkpoint["revision"], bool)
        or checkpoint["revision"] < 0
        or not isinstance(checkpoint["handoff_ids"], list)
        or not all(isinstance(item, str) for item in checkpoint["handoff_ids"])
    ):
        return [f"invalid phase checkpoint: {previous_phase}"]
    diagnostics: list[str] = []
    run_id = _run_value(manifest, "id")
    revision = _run_value(manifest, "revision")
    if run_id != checkpoint.get("run_id"):
        diagnostics.append(
            f"run continuity: expected {checkpoint.get('run_id')}, found {run_id}"
        )
    if not isinstance(revision, int) or revision <= checkpoint.get("revision", -1):
        diagnostics.append(
            f"revision continuity: expected > {checkpoint.get('revision')}, found {revision}"
        )
    handoffs = _ids(manifest.get("handoffs"))
    for handoff_id in checkpoint.get("handoff_ids", []):
        if handoff_id not in handoffs:
            diagnostics.append(f"handoff continuity: missing {handoff_id}")
    return diagnostics


def _check_authorized_patch(workspace: Path, fixture: Path, patch_reference: str) -> list[str]:
    patch = ROOT / patch_reference
    if not patch.is_file():
        return [f"missing authorized patch: {patch_reference}"]
    with tempfile.TemporaryDirectory() as directory:
        expected_root = Path(directory) / "expected"
        shutil.copytree(fixture, expected_root)
        result = subprocess.run(
            ["git", "apply", str(patch)], cwd=expected_root, text=True, capture_output=True, check=False,
        )
        if result.returncode:
            return [f"invalid authorized patch: {patch_reference}"]
        expected_files = {
            path.relative_to(expected_root).as_posix(): path
            for path in expected_root.rglob("*")
            if path.is_file() and path.name != ".fixture-baseline.json"
        }
        baseline_files = {
            path.relative_to(fixture).as_posix(): path
            for path in fixture.rglob("*")
            if path.is_file() and path.name != ".fixture-baseline.json"
        }
        changed = [
            relative for relative, path in baseline_files.items()
            if expected_files[relative].read_bytes() != path.read_bytes()
        ]
        diagnostics: list[str] = []
        for relative in sorted(changed):
            expected = expected_files[relative]
            actual = workspace / relative
            if not actual.is_file() or actual.read_bytes() != expected.read_bytes():
                diagnostics.append(f"authorized patch not applied: {relative}")
        for relative, expected in sorted(expected_files.items()):
            if relative in changed or relative.startswith(".git/"):
                continue
            actual = workspace / relative
            if not actual.is_file() or actual.read_bytes() != expected.read_bytes():
                diagnostics.append(f"unauthorized resume change: {relative}")
        actual_files = {
            relative: path for relative, path in _workspace_files(workspace)
            if not relative.startswith(".git/") and relative != ".fixture-baseline.json"
        }
        for relative in sorted(set(actual_files) - set(expected_files)):
            if (
                relative.startswith(".e2e/")
                or relative.startswith(".agents/skills/")
                or relative.startswith(".claude/skills/")
            ):
                continue
            diagnostics.append(f"unauthorized resume change: {relative}")
        return diagnostics


def _save_checkpoint(state_dir: Path, case: dict[str, Any], phase: str, manifest: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(state_dir, case["id"], phase)
    checkpoint = {
        "run_id": _run_value(manifest, "id"),
        "revision": _run_value(manifest, "revision"),
        "handoff_ids": sorted(_ids(manifest.get("handoffs"))),
    }
    path.write_text(json.dumps(checkpoint, sort_keys=True), encoding="utf-8")


EXECUTION_ENVIRONMENT_FIELDS = {
    "web": {
        "browser_project", "os_platform", "runtime", "application_build_ref",
        "target_reference", "target_tier",
    },
    "service": {
        "protocol", "client", "client_version", "os_platform", "runtime",
        "application_build_ref", "target_reference", "target_tier",
    },
    "mobile": {
        "driver", "driver_version", "platform", "os_version", "target_kind",
        "application_build_ref", "target_reference", "target_tier",
        "evidence_origin",
    },
}

MOBILE_DRIVERS = {"appium", "maestro"}
MOBILE_PLATFORMS = {"ios", "android"}
MOBILE_TARGET_KINDS = {"simulator", "emulator", "real", "remote"}
MOBILE_EVIDENCE_ORIGINS = {"platform", "fixture"}

SERVICE_PROTOCOLS = {"http", "graphql", "grpc", "websocket", "queue", "stream"}
DATABASE_CAPABILITIES = {"database-setup", "database-cleanup", "database-diagnostics"}


def _execution_environment_is_valid(environment: Any, surface: str) -> bool:
    required = EXECUTION_ENVIRONMENT_FIELDS.get(surface)
    return (
        required is not None
        and isinstance(environment, dict)
        and required <= set(environment)
        and all(isinstance(environment[key], str) and environment[key] for key in required)
    )


def _check_service_contract(manifest: dict[str, Any], expect: dict[str, Any], surface: str) -> list[str]:
    """Validate service module binding, production read-only behavior, and cleanup."""
    diagnostics: list[str] = []
    units = manifest.get("execution_units", [])
    evidence = manifest.get("evidence", [])
    actions = manifest.get("actions", [])
    checks = manifest.get("checks", [])
    check_ids = _ids(checks)
    status = _run_value(manifest, "status")

    # Require every service execution unit to use surface="service" and same service extension
    service_units = [u for u in units if isinstance(u, dict) and u.get("surface") == "service"]
    if not service_units:
        return diagnostics  # No service units - not an error for this gate

    # Require every service unit to bind the single shared e2e.service@1.0 extension
    extensions_by_id = {
        e["id"]: e for e in manifest.get("extensions", [])
        if isinstance(e, dict) and isinstance(e.get("id"), str)
    }
    bound_extension_ids: set[str] = set()
    for unit in service_units:
        ext_id = unit.get("extension_id")
        ext = extensions_by_id.get(ext_id) if isinstance(ext_id, str) else None
        if ext is None or ext.get("namespace") != "e2e.service" or ext.get("version") != "1.0":
            diagnostics.append(
                f"execution_unit {unit.get('id')} does not reference the e2e.service@1.0 extension"
            )
            continue
        bound_extension_ids.add(ext_id)
    if len(bound_extension_ids) > 1:
        diagnostics.append("service execution units must share a single e2e.service extension")

    # Validate execution evidence protocols match selected units
    for item in evidence:
        if not isinstance(item, dict):
            continue
        env = item.get("execution_environment")
        if not isinstance(env, dict):
            continue
        protocol = env.get("protocol")
        if protocol and protocol not in SERVICE_PROTOCOLS:
            diagnostics.append(f"execution evidence has invalid protocol: {protocol}")

    # Require all required multi-protocol checks to be covered by genuine, passing,
    # bound execution evidence (not merely by any outcome record, regardless of status).
    required_check_ids = expect.get("required_check_ids", [])
    if required_check_ids:
        passed_check_ids: set[str] = set()
        for item in evidence:
            if _is_execution_evidence(item, check_ids, surface):
                passed_check_ids.update(item.get("check_ids", []))
        for check_id in required_check_ids:
            if check_id not in passed_check_ids:
                diagnostics.append(f"missing check ID: {check_id}")

    # Production read-only checks (scoped to production-tier evidence only)
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("execution_environment"), dict):
            continue
        env = item["execution_environment"]
        if env.get("target_tier") != "production":
            continue
        if env.get("mutation_performed") is True:
            diagnostics.append("production mutation is not allowed in service verification")
        if env.get("acknowledged") is True:
            diagnostics.append("acknowledged is not allowed in service verification")
        if env.get("cursor_committed") is True:
            diagnostics.append("cursor_committed is not allowed in service verification")

    # Database support checks
    for item in evidence:
        if isinstance(item, dict) and item.get("support_only") is True:
            if item.get("check_ids"):
                diagnostics.append("database support evidence must not appear in check_ids")

    # Cleanup action checks
    cleanup_actions = [
        a for a in actions
        if isinstance(a, dict) and a.get("capability") == "database-cleanup"
    ]
    if cleanup_actions:
        cleanup_evidence = [
            e for e in evidence
            if isinstance(e, dict)
            and e.get("id") in [a.get("id") for a in cleanup_actions]
            and e.get("cleanup_successful") is True
        ]
        if not cleanup_evidence:
            diagnostics.append("cleanup incomplete: database-cleanup action without successful cleanup evidence")

    return diagnostics


def _mobile_extension_records(
    extension: dict[str, Any],
) -> tuple[
    str | None,
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    data = extension.get("data")
    if not isinstance(data, dict):
        return None, {}, {}, {}, [], []
    application = data.get("application")
    application_id = (
        application.get("id")
        if isinstance(application, dict) and isinstance(application.get("id"), str)
        else None
    )

    duplicate_ids: list[str] = []

    def index_records(name: str, label: str) -> dict[str, dict[str, Any]]:
        records = data.get(name)
        if not isinstance(records, list):
            return {}
        indexed: dict[str, dict[str, Any]] = {}
        for item in records:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            record_id = item["id"]
            if record_id in indexed:
                duplicate_ids.append(f"duplicate mobile {label} id: {record_id}")
                continue
            indexed[record_id] = item
        return indexed

    profiles = data.get("lifecycle_profiles")
    lifecycle_profiles = [
        item for item in profiles if isinstance(item, dict)
    ] if isinstance(profiles, list) else []
    profile_ids: set[str] = set()
    for profile in lifecycle_profiles:
        profile_id = profile.get("id")
        if not isinstance(profile_id, str):
            continue
        if profile_id in profile_ids:
            duplicate_ids.append(f"duplicate mobile lifecycle id: {profile_id}")
            continue
        profile_ids.add(profile_id)
    return (
        application_id,
        index_records("drivers", "driver"),
        index_records("targets", "target"),
        index_records("artifacts", "artifact"),
        lifecycle_profiles,
        duplicate_ids,
    )


def _check_mobile_expected_state(
    manifest: dict[str, Any],
    expect: dict[str, Any],
    *,
    drivers: dict[str, dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    lifecycle_profiles: list[dict[str, Any]],
    mobile_unit_ids: set[str],
) -> list[str]:
    diagnostics: list[str] = []
    evidence = manifest.get("evidence", [])
    evidence_records = evidence if isinstance(evidence, list) else []
    evidence_by_id = {
        item["id"]: item
        for item in evidence_records
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    checks_by_id = {
        item["id"]: item
        for item in manifest.get("checks", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    required_execution_ids = {
        item
        for item in expect.get("required_execution_evidence_ids", [])
        if isinstance(item, str)
    }
    required_evidence_ids = required_execution_ids | {
        item
        for item in expect.get("required_evidence_ids", [])
        if isinstance(item, str)
    }
    expected_evidence = [
        evidence_by_id[item]
        for item in required_evidence_ids
        if item in evidence_by_id
    ]
    required_check_ids = {
        item
        for item in expect.get("required_check_ids", [])
        if isinstance(item, str)
    }
    expected_check_ids = set(required_check_ids)
    expected_phase = expect.get(
        "_phase_name",
        _run_value(manifest, "mode"),
    )
    final_revision = _run_value(manifest, "revision")
    if not expected_check_ids:
        expected_check_ids.update(
            check_id
            for item in expected_evidence
            for check_id in item.get("check_ids", [])
            if check_id in checks_by_id
        )
    if not expected_check_ids:
        expected_check_ids.update(
            check_id
            for item in evidence_records
            if _is_execution_evidence(
                item,
                set(checks_by_id),
                "mobile",
            )
            and item.get("phase") == expected_phase
            and type(final_revision) is int
            and type(item.get("manifest_revision_consumed")) is int
            and final_revision == item["manifest_revision_consumed"] + 1
            for check_id in item.get("check_ids", [])
            if checks_by_id.get(check_id, {}).get("status") == "passed"
        )
    expected_unit_ids = {
        checks_by_id[check_id].get("execution_unit_id")
        for check_id in expected_check_ids
        if check_id in checks_by_id
    }
    bound_profiles = [
        profile
        for profile in lifecycle_profiles
        if profile.get("execution_unit_id") in mobile_unit_ids
    ]
    if (
        not expected_check_ids
        and len(mobile_unit_ids) == 1
        and len(bound_profiles) == 1
    ):
        expected_profiles = bound_profiles
    else:
        expected_profiles = [
            profile
            for profile in bound_profiles
            if profile.get("execution_unit_id") in expected_unit_ids
        ]

    profile_execution_evidence = (
        [
            evidence_by_id[item]
            for item in required_execution_ids
            if item in evidence_by_id
        ]
        if required_execution_ids
        else evidence_records
    )
    selected_execution_profiles: list[dict[str, Any]] = []
    for item in profile_execution_evidence:
        if not _is_execution_evidence(
            item,
            set(checks_by_id),
            "mobile",
        ):
            continue
        consumed_revision = item.get("manifest_revision_consumed")
        if (
            item.get("phase") != expected_phase
            or type(final_revision) is not int
            or type(consumed_revision) is not int
            or final_revision != consumed_revision + 1
        ):
            continue
        selected_units = {
            checks_by_id[check_id].get("execution_unit_id")
            for check_id in item.get("check_ids", [])
            if check_id in expected_check_ids and check_id in checks_by_id
        }
        environment = item.get("execution_environment")
        target_reference = (
            environment.get("target_reference")
            if isinstance(environment, dict)
            else None
        )
        artifact_reference = (
            environment.get("application_build_ref")
            if isinstance(environment, dict)
            else None
        )
        for unit_id in selected_units:
            matches = [
                profile
                for profile in expected_profiles
                if profile.get("execution_unit_id") == unit_id
                and profile.get("target_id") == target_reference
                and artifact_reference in profile.get("artifact_ids", [])
            ]
            if len(matches) == 1:
                selected_execution_profiles.append(matches[0])

    selected_target_drivers: list[
        tuple[str, dict[str, Any], dict[str, Any]]
    ] = []
    for profile in expected_profiles:
        target_id = profile.get("target_id")
        target = targets.get(target_id)
        driver = (
            drivers.get(target.get("driver_id"))
            if isinstance(target, dict)
            else None
        )
        if (
            isinstance(target_id, str)
            and isinstance(target, dict)
            and isinstance(driver, dict)
        ):
            selected_target_drivers.append((target_id, target, driver))

    required_target_tier = expect.get("required_target_tier")
    if isinstance(required_target_tier, str):
        units_by_id = {
            item["id"]: item
            for item in manifest.get("execution_units", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        systems_by_id = {
            item["id"]: item
            for item in _systems(manifest)
            if isinstance(item.get("id"), str)
        }
        selected_system_tiers = {
            systems_by_id.get(
                units_by_id.get(profile.get("execution_unit_id"), {}).get(
                    "system_id"
                ),
                {},
            ).get("target", {}).get("tier")
            for profile in expected_profiles
        }
        target_context_is_bound = any(
            required_evidence_ids
            & set(target.get("evidence_refs", []))
            for _, target, _ in selected_target_drivers
        )
        if (
            not expected_profiles
            or selected_system_tiers != {required_target_tier}
            or (required_evidence_ids and not target_context_is_bound)
        ):
            diagnostics.append(
                f"mobile case requires target tier {required_target_tier}"
            )

    cleanup_outcome = expect.get("required_cleanup_outcome")
    if cleanup_outcome in {"successful", "failed"}:
        expected = cleanup_outcome == "successful"
        required_journey_ids = {
            item
            for item in expect.get("required_journey_ids", [])
            if isinstance(item, str)
        }
        required_journey_ids.update(
            checks_by_id[check_id].get("journey_id")
            for check_id in expected_check_ids
            if check_id in checks_by_id
            and isinstance(
                checks_by_id[check_id].get("journey_id"),
                str,
            )
        )
        cleanup_actions_by_id = {
            item["id"]: item
            for item in manifest.get("actions", [])
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item.get("capability") == "mobile-cleanup"
        }
        selected_cleanup_action_ids = {
            action_id
            for profile in selected_execution_profiles
            for action_id in profile.get("cleanup_action_refs", [])
            if isinstance(action_id, str)
        }
        if not any(
            isinstance(item, dict)
            and item.get("cleanup_successful") is expected
            and isinstance(item.get("cleanup_action_id"), str)
            and item["cleanup_action_id"] in selected_cleanup_action_ids
            and item["cleanup_action_id"] in cleanup_actions_by_id
            and isinstance(
                cleanup_actions_by_id[item["cleanup_action_id"]].get(
                    "journey_ids"
                ),
                list,
            )
            and required_journey_ids <= set(
                cleanup_actions_by_id[item["cleanup_action_id"]][
                    "journey_ids"
                ]
            )
            for item in evidence_records
        ):
            diagnostics.append(
                "mobile cleanup success lacks explicit evidence"
                if expected
                else "mobile cleanup failure lacks explicit failed evidence"
            )

    required_roles = expect.get("required_artifact_roles", [])
    required_sequence = expect.get("required_lifecycle_sequence")
    upgrade_expected = bool(required_roles) or bool(required_sequence)
    upgrade_scope_profiles = expected_profiles
    if upgrade_expected and required_execution_ids:
        required_execution_evidence = [
            evidence_by_id[item]
            for item in required_execution_ids
            if item in evidence_by_id
        ]
        selected_profiles: list[dict[str, Any]] = []
        selection_valid = bool(required_execution_evidence)
        for item in required_execution_evidence:
            selected_units = {
                checks_by_id[check_id].get("execution_unit_id")
                for check_id in item.get("check_ids", [])
                if check_id in checks_by_id
            }
            environment = item.get("execution_environment")
            target_reference = (
                environment.get("target_reference")
                if isinstance(environment, dict)
                else None
            )
            artifact_reference = (
                environment.get("application_build_ref")
                if isinstance(environment, dict)
                else None
            )
            matches = [
                profile
                for profile in expected_profiles
                if profile.get("execution_unit_id") in selected_units
                and profile.get("target_id") == target_reference
                and artifact_reference in profile.get("artifact_ids", [])
            ]
            if len(matches) != 1:
                selection_valid = False
            else:
                selected_profiles.append(matches[0])
        selected_profile_ids = {
            profile.get("id")
            for profile in selected_profiles
        }
        if not selection_valid or len(selected_profile_ids) != 1:
            diagnostics.append(
                "mobile required lifecycle selection is ambiguous or unbound"
            )
            upgrade_scope_profiles = []
        else:
            upgrade_scope_profiles = [selected_profiles[0]]
    upgrade_profiles = [
        profile for profile in upgrade_scope_profiles
        if profile.get("upgrade") is True
    ]
    if upgrade_expected and not upgrade_profiles:
        diagnostics.append("mobile required lifecycle is not an upgrade")
    selected_upgrade_artifacts = [
        artifacts[artifact_id]
        for profile in upgrade_profiles
        for artifact_id in profile.get("artifact_ids", [])
        if artifact_id in artifacts
    ]
    present_roles = {
        item.get("role")
        for item in selected_upgrade_artifacts
        if isinstance(item.get("role"), str)
    }
    for role in required_roles:
        if role not in present_roles:
            diagnostics.append(f"missing mobile artifact role: {role}")

    forbidden_roles = set(expect.get("forbidden_artifact_roles", []))
    for artifact_id, artifact in artifacts.items():
        if artifact.get("role") in forbidden_roles:
            diagnostics.append(f"forbidden mobile artifact: {artifact_id}")

    bootstrap = expect.get("required_driver_bootstrap")
    if isinstance(bootstrap, dict):
        authorizations_by_id = {
            item["id"]: item
            for item in manifest.get("authorizations", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if not any(
            driver.get("kind") == bootstrap.get("kind")
            and driver.get("bootstrap_status") == bootstrap.get("status")
            and driver.get("authorization_ref") == bootstrap.get("authorization_ref")
            and isinstance(
                authorizations_by_id.get(driver.get("authorization_ref")),
                dict,
            )
            and authorizations_by_id[driver["authorization_ref"]].get(
                "status"
            ) == "approved"
            and authorizations_by_id[driver["authorization_ref"]].get(
                "capability"
            ) == "mobile-repository-bootstrap"
            and authorizations_by_id[driver["authorization_ref"]].get(
                "target_reference"
            ) == target_id
            for target_id, _, driver in selected_target_drivers
        ):
            diagnostics.append("mobile driver lacks required bootstrap authorization")

    systems = _systems(manifest)
    if expect.get("require_empty_credential_refs") is True and any(
        system.get("target", {}).get("credential_refs")
        for system in systems
        if isinstance(system, dict) and isinstance(system.get("target"), dict)
    ):
        diagnostics.append("mobile case expected missing credential references")

    commands = [
        item.get("command", "")
        for item in evidence_records
        if isinstance(item, dict) and isinstance(item.get("command"), str)
    ]
    for term in expect.get("forbidden_command_terms", []):
        if any(term.casefold() in command.casefold() for command in commands):
            diagnostics.append(f"forbidden mobile command term: {term}")

    if required_sequence:
        selected_profile_units = {
            profile.get("execution_unit_id")
            for profile in upgrade_profiles
        }
        lifecycle_evidence = (
            [
                item
                for item in expected_evidence
                if set(item.get("check_ids", [])) == expected_check_ids
            ]
            if required_execution_ids
            else [
                item
                for item in evidence_records
                if any(
                    checks_by_id.get(check_id, {}).get("execution_unit_id")
                    in selected_profile_units
                    for check_id in item.get("check_ids", [])
                )
            ]
        )
        if not any(
            isinstance(item, dict)
            and item.get("lifecycle") == required_sequence
            for item in lifecycle_evidence
        ):
            diagnostics.append(
                "mobile lifecycle evidence is missing the required sequence"
            )

    if expect.get("required_capability_target_evidence") is True and not any(
        isinstance(item, dict)
        and item.get("surface") == "mobile"
        and any(
            item.get("target_reference") == target_id
            and item.get("adapter") in {driver.get("id"), driver.get("kind")}
            for target_id, _, driver in selected_target_drivers
        )
        and isinstance(item.get("source_locations"), list)
        and bool(item["source_locations"])
        and item.get("read_only") is True
        for item in evidence_records
    ):
        diagnostics.append(
            "missing capability-unavailable mobile adapter and target evidence"
        )

    return diagnostics


def _check_mobile_contract(
    manifest: dict[str, Any],
    expect: dict[str, Any],
    surface: str,
) -> list[str]:
    diagnostics: list[str] = []
    units = manifest.get("execution_units", [])
    evidence = manifest.get("evidence", [])
    actions = manifest.get("actions", [])
    check_ids = _ids(manifest.get("checks"))
    mobile_units = [
        item for item in units
        if isinstance(item, dict) and item.get("surface") == "mobile"
    ]
    if not mobile_units:
        diagnostics.append("mobile case requires at least one mobile execution unit")
        return diagnostics

    extensions_by_id = {
        item["id"]: item
        for item in manifest.get("extensions", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    bound_ids: set[str] = set()
    for unit in mobile_units:
        extension_id = unit.get("extension_id")
        extension = extensions_by_id.get(extension_id)
        if (
            not isinstance(extension, dict)
            or extension.get("namespace") != "e2e.mobile"
            or extension.get("version") != "1.0"
        ):
            diagnostics.append(
                f"execution_unit {unit.get('id')} does not reference "
                "the e2e.mobile@1.0 extension"
            )
            continue
        bound_ids.add(extension_id)
    if len(bound_ids) > 1:
        diagnostics.append(
            "mobile execution units must share a single e2e.mobile extension"
        )

    bound_extensions = [
        extensions_by_id[extension_id]
        for extension_id in bound_ids
        if extension_id in extensions_by_id
    ]
    if len(bound_extensions) == 1:
        (
            application_id,
            drivers,
            targets,
            artifacts,
            lifecycle_profiles,
            duplicate_ids,
        ) = _mobile_extension_records(bound_extensions[0])
        if duplicate_ids:
            diagnostics.extend(duplicate_ids)
            return diagnostics
        mobile_unit_ids = {
            item["id"]
            for item in mobile_units
            if isinstance(item.get("id"), str)
        }
        diagnostics.extend(
            _check_mobile_expected_state(
                manifest,
                expect,
                drivers=drivers,
                targets=targets,
                artifacts=artifacts,
                lifecycle_profiles=lifecycle_profiles,
                mobile_unit_ids=mobile_unit_ids,
            )
        )

        for artifact_id, artifact in artifacts.items():
            if artifact.get("application_id") != application_id:
                diagnostics.append(
                    f"mobile artifact {artifact_id} does not reference "
                    f"application {application_id}"
                )

        for target_id, target in targets.items():
            driver_id = target.get("driver_id")
            if driver_id not in drivers:
                diagnostics.append(
                    f"mobile target {target_id} references unknown driver {driver_id}"
                )
            for evidence_id in target.get("evidence_refs", []):
                if evidence_id not in _ids(evidence):
                    diagnostics.append(
                        f"mobile target {target_id} references unknown "
                        f"evidence {evidence_id}"
                    )
            if (
                target.get("kind") in {"real", "remote"}
                and target.get("provisioning_status") != "ready"
            ):
                diagnostics.append(f"mobile target {target_id} is not provisioned")

        for profile in lifecycle_profiles:
            profile_id = profile.get("id")
            unit_id = profile.get("execution_unit_id")
            target_id = profile.get("target_id")
            if unit_id not in mobile_unit_ids:
                diagnostics.append(
                    f"mobile lifecycle {profile_id} references unknown "
                    f"execution unit {unit_id}"
                )
            target = targets.get(target_id)
            if target is None:
                diagnostics.append(
                    f"mobile lifecycle {profile_id} references unknown target {target_id}"
                )

            selected_artifacts = []
            for artifact_id in profile.get("artifact_ids", []):
                artifact = artifacts.get(artifact_id)
                if artifact is None:
                    diagnostics.append(
                        f"mobile lifecycle {profile_id} references unknown "
                        f"artifact {artifact_id}"
                    )
                else:
                    selected_artifacts.append(artifact)

            for field, label in (
                ("setup_action_refs", "setup action"),
                ("cleanup_action_refs", "cleanup action"),
            ):
                for action_id in profile.get(field, []):
                    if action_id not in _ids(actions):
                        diagnostics.append(
                            f"mobile lifecycle {profile_id} references "
                            f"unknown {label} {action_id}"
                        )

            if profile.get("upgrade") is True:
                roles = [artifact.get("role") for artifact in selected_artifacts]
                if roles.count("prior") != 1 or roles.count("candidate") != 1:
                    diagnostics.append(
                        f"mobile lifecycle {profile_id} upgrade requires "
                        "one prior and one candidate artifact"
                    )
                elif roles != ["prior", "candidate"]:
                    diagnostics.append(
                        f"mobile lifecycle {profile_id} upgrade requires "
                        "artifacts ordered prior then candidate"
                    )

            if (
                profile.get("reset_policy") == "virtual-snapshot"
                and (
                    not isinstance(target, dict)
                    or target.get("kind") not in {"simulator", "emulator"}
                    or target.get("disposable") is not True
                )
            ):
                diagnostics.append(
                    f"mobile lifecycle {profile_id} virtual-snapshot "
                    "requires a disposable virtual target"
                )

        units_by_id = {
            unit.get("id"): unit
            for unit in mobile_units
            if isinstance(unit.get("id"), str)
        }
        systems_by_id = {
            system.get("id"): system
            for system in _systems(manifest)
            if isinstance(system.get("id"), str)
        }
        for item in evidence:
            if not _is_execution_evidence(item, check_ids, surface):
                continue
            environment = item["execution_environment"]
            target_reference = environment.get("target_reference")
            artifact_reference = environment.get("application_build_ref")
            target = targets.get(target_reference)
            artifact = artifacts.get(artifact_reference)

            if target is None:
                diagnostics.append(
                    "mobile execution evidence references unknown target: "
                    f"{target_reference}"
                )
                continue
            if artifact is None:
                diagnostics.append(
                    "mobile execution evidence references unknown artifact: "
                    f"{artifact_reference}"
                )
                continue

            driver = drivers.get(target.get("driver_id"))
            if (
                not isinstance(driver, dict)
                or environment.get("driver") != driver.get("kind")
                or environment.get("driver_version") != driver.get("version")
                or environment.get("platform") != target.get("platform")
                or environment.get("os_version") != target.get("os_version")
                or environment.get("target_kind") != target.get("kind")
                or artifact.get("platform") != target.get("platform")
            ):
                diagnostics.append(
                    f"mobile execution evidence does not match target {target_reference}"
                )

            selected_units = {
                check.get("execution_unit_id")
                for check in manifest.get("checks", [])
                if isinstance(check, dict) and check.get("id") in item.get("check_ids", [])
            }
            for unit_id in selected_units:
                matching_profiles = [
                    profile
                    for profile in lifecycle_profiles
                    if profile.get("execution_unit_id") == unit_id
                    and profile.get("target_id") == target_reference
                    and artifact_reference in profile.get("artifact_ids", [])
                ]
                unit = units_by_id.get(unit_id)
                system = (
                    systems_by_id.get(unit.get("system_id"))
                    if isinstance(unit, dict)
                    else None
                )
                target_tier = (
                    system.get("target", {}).get("tier")
                    if isinstance(system, dict)
                    and isinstance(system.get("target"), dict)
                    else None
                )
                if (
                    len(matching_profiles) != 1
                    or environment.get("target_tier") != target_tier
                ):
                    diagnostics.append(
                        f"mobile execution evidence is not bound to lifecycle for {unit_id}"
                    )

    for item in evidence:
        if not isinstance(item, dict):
            continue
        environment = item.get("execution_environment")
        if not isinstance(environment, dict):
            continue
        if environment.get("driver") not in MOBILE_DRIVERS:
            diagnostics.append(
                f"mobile execution evidence has invalid driver: "
                f"{environment.get('driver')}"
            )
        if environment.get("platform") not in MOBILE_PLATFORMS:
            diagnostics.append(
                f"mobile execution evidence has invalid platform: "
                f"{environment.get('platform')}"
            )
        if environment.get("target_kind") not in MOBILE_TARGET_KINDS:
            diagnostics.append(
                f"mobile execution evidence has invalid target kind: "
                f"{environment.get('target_kind')}"
            )
        origin = environment.get("evidence_origin")
        if origin not in MOBILE_EVIDENCE_ORIGINS:
            diagnostics.append(
                f"mobile execution evidence has invalid evidence origin: {origin}"
            )
        elif origin == "fixture" and not expect.get("allow_fixture_evidence", False):
            diagnostics.append(
                "fixture evidence cannot satisfy live mobile acceptance"
            )
        if environment.get("target_tier") == "production":
            if (
                environment.get("external_effect_performed") is True
                or environment.get("backend_mutation_performed") is True
                or environment.get("permission_external_effect") is True
            ):
                diagnostics.append(
                    "production external effects are not allowed "
                    "in mobile verification"
                )

    required_check_ids = {
        item
        for item in expect.get("required_check_ids", [])
        if isinstance(item, str)
    }
    expected_phase = expect.get("_phase_name", _run_value(manifest, "mode"))
    final_revision = _run_value(manifest, "revision")
    passing_mobile_evidence = []
    for item in evidence:
        if not _is_execution_evidence(item, check_ids, surface):
            continue
        consumed_revision = item.get("manifest_revision_consumed")
        if (
            item.get("phase") == expected_phase
            and type(final_revision) is int
            and type(consumed_revision) is int
            and final_revision == consumed_revision + 1
        ):
            passing_mobile_evidence.append(item)
    manifest_passed_check_ids = {
        check.get("id")
        for check in manifest.get("checks", [])
        if isinstance(check, dict)
        and isinstance(check.get("id"), str)
        and check.get("status") == "passed"
    }
    passed_check_ids = {
        check_id
        for item in passing_mobile_evidence
        for check_id in item.get("check_ids", [])
        if check_id in manifest_passed_check_ids
    }
    for check_id in sorted(required_check_ids - passed_check_ids):
        diagnostics.append(
            f"required mobile check lacks passing execution evidence: {check_id}"
        )

    cleanup_actions = [
        item for item in actions
        if isinstance(item, dict)
        and item.get("capability") == "mobile-cleanup"
    ]
    if _run_value(manifest, "status") == "verified" and not cleanup_actions:
        diagnostics.append(
            "cleanup incomplete: verified mobile run lacks mobile-cleanup action"
        )
    for action in cleanup_actions:
        successful = any(
            isinstance(item, dict)
            and item.get("cleanup_action_id") == action.get("id")
            and item.get("cleanup_successful") is True
            for item in evidence
        )
        if not successful and _run_value(manifest, "status") == "verified":
            diagnostics.append(
                "cleanup incomplete: mobile-cleanup action lacks successful evidence"
            )
        if (
            not successful
            and _run_value(manifest, "status") == "blocked"
            and not any(
                isinstance(item, dict)
                and item.get("cleanup_action_id") == action.get("id")
                and item.get("cleanup_successful") is False
                for item in evidence
            )
        ):
            diagnostics.append(
                "blocked cleanup outcome requires explicit failed cleanup evidence"
            )
    diagnostics.extend(_check_expected_classifications(manifest, expect))
    diagnostics.extend(_check_expected_action_capabilities(manifest, expect))
    diagnostics.extend(_check_forbidden_execution(evidence, expect))
    return diagnostics


def evaluate(
    case_path: str | Path,
    workspace: str | Path,
    phase: str | None = None,
    state_dir: str | Path | None = None,
) -> list[str]:
    """Return stable acceptance diagnostics; an empty list means the case passes."""
    case_file = Path(case_path)
    root = Path(workspace)
    case, errors = _read_json(case_file, "case")
    if errors:
        return errors
    assert case is not None
    required = {"id", "entry_skill", "mode", "prompt", "fixture", "expect"}
    missing = sorted(required - set(case))
    if missing:
        return [f"invalid case: missing required field: {field}" for field in missing]
    surface = case.get("surface", "web")
    if surface not in EXECUTION_ENVIRONMENT_FIELDS:
        return [f"invalid case: unsupported surface: {surface}"]
    expect, phase_errors = _phase_expectation(case, phase)
    if phase_errors:
        return phase_errors
    evaluator_state = Path(state_dir) if state_dir is not None else None
    if evaluator_state is not None:
        try:
            evaluator_state.resolve().relative_to(root.resolve())
            return ["evaluator state must be outside workspace"]
        except ValueError:
            pass

    diagnostics = _check_files(
        root,
        ROOT / "evals" / "fixtures" / case["fixture"],
        expect,
        evaluator_state,
    )
    manifest_path = root / ".e2e" / "manifest.json"
    manifest, manifest_errors = _read_json(manifest_path, "manifest")
    expected_status = expect.get("manifest_status")
    if manifest_errors:
        diagnostics.extend(manifest_errors)
        return sorted(dict.fromkeys(diagnostics))
    assert manifest is not None

    validation_errors = _validate_manifest(manifest)
    if validation_errors:
        diagnostics.append("invalid manifest: " + "; ".join(sorted(validation_errors)))
        return sorted(dict.fromkeys(diagnostics))
    if expected_status is not None and _run_value(manifest, "status") != expected_status:
        diagnostics.append(
            f"manifest status: expected {expected_status}, found {_run_value(manifest, 'status')}"
        )
    expected_mode = expect.get("mode", case["mode"])
    if _run_value(manifest, "mode") != expected_mode:
        diagnostics.append(f"manifest mode: expected {expected_mode}, found {_run_value(manifest, 'mode')}")
    expected_autonomy = case.get("autonomy", {"mode": "explicit", "auto_repair": False})
    if _run_value(manifest, "autonomy") != expected_autonomy:
        diagnostics.append(f"manifest autonomy: expected {expected_autonomy}, found {_run_value(manifest, 'autonomy')}")
    diagnostics.extend(_check_required_ids(manifest, expect))
    diagnostics.extend(_check_traceability(manifest, expect))
    diagnostics.extend(_check_status_evidence(manifest, expect, surface))
    if surface == "service":
        diagnostics.extend(_check_service_contract(manifest, expect, surface))
    if surface == "mobile":
        diagnostics.extend(_check_mobile_contract(manifest, expect, surface))
    if surface == "desktop":
        diagnostics.extend(check_desktop_contract(manifest, expect, surface))
    if expect.get("_checkpoint") and evaluator_state is None:
        diagnostics.append("missing evaluator state directory")
    diagnostics.extend(_check_continuity(evaluator_state, case, manifest, expect))
    if expect.get("_apply_patch"):
        diagnostics.extend(_check_authorized_patch(root, ROOT / "evals" / "fixtures" / case["fixture"], expect["_apply_patch"]))
    diagnostics = sorted(dict.fromkeys(diagnostics))
    if not diagnostics and expect.get("_checkpoint"):
        assert evaluator_state is not None
        _save_checkpoint(evaluator_state, case, expect["_phase_name"], manifest)
    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--phase")
    parser.add_argument("--state-dir", type=Path, help="evaluator-owned directory outside the workspace")
    args = parser.parse_args()
    case, errors = _read_json(args.case_json, "case")
    if errors:
        print("\n".join(errors))
        return 1
    assert case is not None
    try:
        with running_setup(case, args.workspace):
            diagnostics = evaluate(args.case_json, args.workspace, args.phase, args.state_dir)
    except RuntimeError as error:
        print(str(error))
        return 1
    if diagnostics:
        print("\n".join(diagnostics))
        return 1
    suffix = f":{args.phase}" if args.phase else ""
    print(f"PASS {case['id']}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
