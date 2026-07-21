"""Evaluate E2E skill output from durable workspace artifacts only."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
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


ROOT = Path(__file__).resolve().parents[1]
BUNDLED_PROTOCOL = ROOT / "skills" / "e2e-testing" / "scripts" / "e2e_protocol.py"
CHECKPOINT_RUN_ID = re.compile(r"run-[a-z0-9-]+$")


def _load_validator():
    spec = importlib.util.spec_from_file_location("bundled_e2e_protocol", BUNDLED_PROTOCOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load bundled protocol validator: {BUNDLED_PROTOCOL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.validate_manifest


VALIDATE_MANIFEST = _load_validator()


@contextmanager
def running_setup(case: dict[str, Any], workspace: Path):
    """Run a fixture's optional local server and always terminate it."""
    setup = case.get("setup")
    if not setup:
        yield
        return
    command = setup["command"]
    process = subprocess.Popen(shlex.split(command), cwd=workspace)
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
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


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


def _ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _check_required_ids(manifest: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    collections = {
        "journey": "journeys",
        "test": "tests",
        "evidence": "evidence",
        "handoff": "handoffs",
        "next_action": "next_actions",
        "attempt_history": "attempt_history",
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
    tests_by_journey = {
        item.get("journey_id")
        for item in manifest.get("tests", [])
        if isinstance(item, dict) and isinstance(item.get("journey_id"), str)
    }
    return [
        f"missing journey traceability: {journey_id}"
        for journey_id in required
        if journey_id not in tests_by_journey
    ]


def _check_files(workspace: Path, fixture: Path, expect: dict[str, Any]) -> list[str]:
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
    if manifest.get("run_id") != checkpoint.get("run_id"):
        diagnostics.append(
            f"run continuity: expected {checkpoint.get('run_id')}, found {manifest.get('run_id')}"
        )
    if not isinstance(manifest.get("revision"), int) or manifest["revision"] <= checkpoint.get("revision", -1):
        diagnostics.append(
            f"revision continuity: expected > {checkpoint.get('revision')}, found {manifest.get('revision')}"
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
        changed = [
            path.relative_to(fixture).as_posix()
            for path in fixture.rglob("*")
            if path.is_file() and path.name != ".fixture-baseline.json"
            and (expected_root / path.relative_to(fixture)).read_bytes() != path.read_bytes()
        ]
        diagnostics: list[str] = []
        for relative in sorted(changed):
            expected = expected_root / relative
            actual = workspace / relative
            if not actual.is_file() or actual.read_bytes() != expected.read_bytes():
                diagnostics.append(f"authorized patch not applied: {relative}")
        return diagnostics


def _save_checkpoint(state_dir: Path, case: dict[str, Any], phase: str, manifest: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(state_dir, case["id"], phase)
    checkpoint = {
        "run_id": manifest["run_id"],
        "revision": manifest["revision"],
        "handoff_ids": sorted(_ids(manifest.get("handoffs"))),
    }
    path.write_text(json.dumps(checkpoint, sort_keys=True), encoding="utf-8")


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

    diagnostics = _check_files(root, ROOT / "evals" / "fixtures" / case["fixture"], expect)
    manifest_path = root / ".e2e" / "manifest.json"
    manifest, manifest_errors = _read_json(manifest_path, "manifest")
    expected_status = expect.get("manifest_status")
    if manifest_errors:
        diagnostics.extend(manifest_errors)
        return sorted(dict.fromkeys(diagnostics))
    assert manifest is not None

    validation_errors = VALIDATE_MANIFEST(manifest)
    if validation_errors:
        diagnostics.append("invalid manifest: " + "; ".join(sorted(validation_errors)))
        return sorted(dict.fromkeys(diagnostics))
    if expected_status is not None and manifest.get("status") != expected_status:
        diagnostics.append(
            f"manifest status: expected {expected_status}, found {manifest.get('status')}"
        )
    diagnostics.extend(_check_required_ids(manifest, expect))
    diagnostics.extend(_check_traceability(manifest, expect))
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
