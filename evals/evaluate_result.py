"""Evaluate E2E skill output from durable workspace artifacts only."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import shlex
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUNDLED_PROTOCOL = ROOT / "skills" / "e2e-testing" / "scripts" / "e2e_protocol.py"


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
    return diagnostics


def evaluate(case_path: str | Path, workspace: str | Path, phase: str | None = None) -> list[str]:
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

    diagnostics = _check_files(root, ROOT / "evals" / "fixtures" / case["fixture"], expect)
    manifest_path = root / ".e2e" / "manifest.json"
    manifest, manifest_errors = _read_json(manifest_path, "manifest")
    expected_status = expect.get("manifest_status")
    if manifest_errors:
        if expected_status != "unsupported-framework":
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
    return sorted(dict.fromkeys(diagnostics))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--phase")
    args = parser.parse_args()
    case, errors = _read_json(args.case_json, "case")
    if errors:
        print("\n".join(errors))
        return 1
    assert case is not None
    try:
        with running_setup(case, args.workspace):
            diagnostics = evaluate(args.case_json, args.workspace, args.phase)
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
