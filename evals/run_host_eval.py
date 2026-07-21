"""Run an isolated E2E behavioral case against a fresh Codex or Claude session."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from evals.evaluate_result import evaluate, running_setup


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases"
FIXTURES = ROOT / "evals" / "fixtures"
SKILLS = ROOT / "skills"
RESULTS = ROOT / "evals" / "results"

CODEX = ["codex", "exec", "--full-auto", "-"]
CLAUDE = ["claude", "-p", "--permission-mode", "acceptEdits", "--no-session-persistence"]
HOSTS = {"codex": CODEX, "claude": CLAUDE}
SKILL_ROOTS = {"codex": Path(".agents/skills"), "claude": Path(".claude/skills")}
SKILL_NAMES = ("e2e-testing", "e2e-web-playwright")


class HostUnavailableError(RuntimeError):
    """Raised when an authorized host CLI is not installed for a requested run."""


def _read_case(case_id: str) -> tuple[Path, dict[str, Any]]:
    path = CASES / f"{case_id}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"unknown evaluation case: {case_id}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid evaluation case: {case_id}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid evaluation case: {case_id}")
    return path, value


def _result_directory(host: str, case_id: str) -> Path:
    base = RESULTS / host / case_id
    base.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = base / timestamp
    suffix = 1
    while candidate.exists():
        candidate = base / f"{timestamp}-{suffix}"
        suffix += 1
    candidate.mkdir()
    return candidate


@contextmanager
def _workspace(host: str, case: dict[str, Any], keep_results: bool) -> Iterator[tuple[Path, Path, Path]]:
    fixture = FIXTURES / str(case["fixture"])
    if not fixture.is_dir():
        raise ValueError(f"missing fixture: {case['fixture']}")

    if keep_results:
        retained = _result_directory(host, str(case["id"]))
        workspace = retained / "workspace"
        state_dir = retained / "evaluator-state"
        shutil.copytree(fixture, workspace)
        yield workspace, state_dir, retained
        return

    with tempfile.TemporaryDirectory(prefix="e2e-host-eval-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        state_dir = root / "evaluator-state"
        shutil.copytree(fixture, workspace)
        yield workspace, state_dir, root


def _install_skills(workspace: Path, host: str) -> None:
    destination_root = workspace / SKILL_ROOTS[host]
    for skill_name in SKILL_NAMES:
        source = SKILLS / skill_name
        if not (source / "SKILL.md").is_file():
            raise RuntimeError(f"missing portable skill: {skill_name}")
        shutil.copytree(source, destination_root / skill_name)


def _phase_runs(case: dict[str, Any]) -> list[tuple[str | None, str, str | None]]:
    phases = case.get("phases")
    if not phases:
        return [(None, str(case["prompt"]), None)]
    runs: list[tuple[str | None, str, str | None]] = []
    for phase in phases:
        if not isinstance(phase, dict) or not isinstance(phase.get("name"), str) or not isinstance(phase.get("prompt"), str):
            raise ValueError(f"invalid phase declaration in case: {case['id']}")
        patch = phase.get("apply_patch")
        if patch is not None and not isinstance(patch, str):
            raise ValueError(f"invalid phase patch in case: {case['id']}")
        runs.append((phase["name"], phase["prompt"], patch))
    return runs


def _apply_declared_patch(workspace: Path, patch: Path) -> None:
    result = subprocess.run(
        ["git", "apply", str(patch)], cwd=workspace, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"authorized patch failed: {patch.relative_to(ROOT)}\n{result.stderr}")


def _write_transcript(artifact_dir: Path, stdout: list[str], stderr: list[str]) -> None:
    (artifact_dir / "stdout.txt").write_text("".join(stdout), encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text("".join(stderr), encoding="utf-8")


def run_case(host: str, case_id: str, *, keep_results: bool = False) -> int:
    """Run one case and return only the deterministic evaluator's exit status.

    The host return code and prose are recorded as evidence but never decide pass or
    fail. A phase is evaluated before its authorized between-phase patch is applied.
    """
    if host not in HOSTS:
        raise ValueError(f"unsupported host: {host}")
    if shutil.which(host) is None:
        raise HostUnavailableError(f"{host} executable is required for host evaluation")

    case_path, case = _read_case(case_id)
    transcript_out: list[str] = []
    transcript_err: list[str] = []
    with _workspace(host, case, keep_results) as (workspace, state_dir, artifact_dir):
        try:
            _install_skills(workspace, host)
            with running_setup(case, workspace):
                for index, (phase, prompt, patch) in enumerate(_phase_runs(case)):
                    # A phase declares the patch that prepares it. This makes the
                    # mutation occur only after the preceding phase has passed its
                    # evaluator and before the resumed host invocation begins.
                    if index and patch:
                        _apply_declared_patch(workspace, ROOT / patch)
                    result = subprocess.run(
                        HOSTS[host], cwd=workspace, input=prompt, text=True, capture_output=True, check=False,
                    )
                    transcript_out.append(result.stdout or "")
                    transcript_err.append(result.stderr or "")
                    diagnostics = evaluate(case_path, workspace, phase, state_dir)
                    if diagnostics:
                        print("\n".join(diagnostics))
                        return 1
        finally:
            _write_transcript(artifact_dir, transcript_out, transcript_err)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=sorted(HOSTS), required=True)
    parser.add_argument("--case", required=True, help="case ID from evals/cases")
    parser.add_argument("--keep-results", action="store_true", help="retain workspace and transcript under evals/results")
    args = parser.parse_args()
    try:
        return run_case(args.host, args.case, keep_results=args.keep_results)
    except (HostUnavailableError, RuntimeError, ValueError) as error:
        print(error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
