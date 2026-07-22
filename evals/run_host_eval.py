"""Run an isolated E2E behavioral case against a fresh Codex or Claude session."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
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
PATCHES = ROOT / "evals" / "patches"
SKILLS = ROOT / "skills"
RESULTS = ROOT / "evals" / "results"

CODEX = ["codex", "exec", "--full-auto", "-"]
CLAUDE = ["claude", "-p", "--permission-mode", "acceptEdits", "--no-session-persistence"]
HOSTS = {"codex": CODEX, "claude": CLAUDE}
SKILL_ROOTS = {"codex": Path(".agents/skills"), "claude": Path(".claude/skills")}
SKILL_NAMES = ("e2e-testing", "e2e-web")
CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
DEFAULT_HOST_TIMEOUT = 300.0
TERMINATE_TIMEOUT = 2.0


class HostUnavailableError(RuntimeError):
    """Raised when an authorized host CLI is not installed for a requested run."""


class HostTimeoutError(RuntimeError):
    """Raised after a host exceeds its bounded execution time."""

    def __init__(self, timeout: float, stdout: str, stderr: str):
        super().__init__(f"host timed out after {timeout:g} seconds")
        self.stdout = stdout
        self.stderr = stderr


def _safe_case_id(case_id: str) -> str:
    if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
        raise ValueError("invalid case ID")
    return case_id


def _contained_path(root: Path, reference: str, label: str, *, file_required: bool = False) -> Path:
    if not isinstance(reference, str):
        raise ValueError(f"invalid {label} path")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"invalid {label} path")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"invalid {label} path") from error
    if file_required and not candidate.is_file():
        raise ValueError(f"missing {label}: {reference}")
    return candidate


def _read_case(case_id: str) -> tuple[Path, dict[str, Any]]:
    safe_id = _safe_case_id(case_id)
    path = _contained_path(CASES, f"{safe_id}.json", "case", file_required=True)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid evaluation case: {safe_id}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("id"), str):
        raise ValueError(f"invalid evaluation case: {safe_id}")
    if value["id"] != safe_id:
        raise ValueError(f"case ID mismatch: requested {safe_id}, found {value['id']}")
    return path, value


def _fixture_path(case: dict[str, Any]) -> Path:
    fixture = case.get("fixture")
    path = _contained_path(FIXTURES, fixture, "fixture")
    if not path.is_dir():
        raise ValueError(f"missing fixture: {fixture}")
    return path


def _patch_path(reference: str) -> Path:
    if not isinstance(reference, str) or Path(reference).is_absolute() or ".." in Path(reference).parts:
        raise ValueError("invalid patch path")
    candidate = (ROOT / reference).resolve()
    try:
        candidate.relative_to(PATCHES.resolve())
    except ValueError as error:
        raise ValueError("invalid patch path") from error
    if not candidate.is_file():
        raise ValueError(f"missing patch: {reference}")
    return candidate


def _result_directory(host: str, case_id: str) -> Path:
    _safe_case_id(host)
    _safe_case_id(case_id)
    base = (RESULTS / host / case_id).resolve()
    try:
        base.relative_to(RESULTS.resolve())
    except ValueError as error:
        raise ValueError("invalid retained destination") from error
    base.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = base / timestamp
    suffix = 1
    while candidate.exists():
        candidate = base / f"{timestamp}-{suffix}"
        suffix += 1
    candidate.mkdir()
    return candidate


def _initialize_repository(workspace: Path) -> None:
    result = subprocess.run(["git", "init", "--quiet"], cwd=workspace, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"cannot initialize isolated workspace\n{result.stderr}")


@contextmanager
def _workspace(case: dict[str, Any]) -> Iterator[tuple[Path, Path, Path]]:
    fixture = _fixture_path(case)
    with tempfile.TemporaryDirectory(prefix="e2e-host-eval-") as temporary:
        root = Path(temporary).resolve()
        try:
            root.relative_to(ROOT.resolve())
        except ValueError:
            pass
        else:
            raise RuntimeError("temporary workspace must be outside repository")
        workspace = root / "workspace"
        state_dir = root / "evaluator-state"
        shutil.copytree(fixture, workspace)
        _initialize_repository(workspace)
        yield root, workspace, state_dir


def _install_skills(workspace: Path, host: str) -> None:
    destination_root = workspace / SKILL_ROOTS[host]
    for skill_name in SKILL_NAMES:
        source = SKILLS / skill_name
        if not (source / "SKILL.md").is_file():
            raise RuntimeError(f"missing portable skill: {skill_name}")
        shutil.copytree(source, destination_root / skill_name)


def _phase_runs(case: dict[str, Any]) -> list[tuple[str | None, str, Path | None]]:
    phases = case.get("phases")
    if not phases:
        prompt = case.get("prompt")
        if not isinstance(prompt, str):
            raise ValueError(f"invalid evaluation case: {case.get('id', 'unknown')}")
        return [(None, prompt, None)]
    runs: list[tuple[str | None, str, Path | None]] = []
    for phase in phases:
        if not isinstance(phase, dict) or not isinstance(phase.get("name"), str) or not isinstance(phase.get("prompt"), str):
            raise ValueError(f"invalid phase declaration in case: {case['id']}")
        patch = phase.get("apply_patch")
        if patch is not None and not isinstance(patch, str):
            raise ValueError(f"invalid phase patch in case: {case['id']}")
        runs.append((phase["name"], phase["prompt"], _patch_path(patch) if patch else None))
    return runs


def _apply_declared_patch(workspace: Path, patch: Path) -> None:
    result = subprocess.run(["git", "apply", str(patch)], cwd=workspace, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"authorized patch failed: {patch.relative_to(ROOT)}\n{result.stderr}")


def _write_transcript(artifact_dir: Path, stdout: list[str], stderr: list[str]) -> None:
    (artifact_dir / "stdout.txt").write_text("".join(stdout), encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text("".join(stderr), encoding="utf-8")


def _popen_kwargs(workspace: Path) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "cwd": workspace,
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return kwargs


def _spawn_host(command: list[str], workspace: Path) -> subprocess.Popen[str]:
    """Launch only the model host; tests can replace this without affecting Git."""
    return subprocess.Popen(command, **_popen_kwargs(workspace))


def _taskkill_tree(pid: int, *, force: bool) -> None:
    command = ["taskkill", "/PID", str(pid), "/T"]
    if force:
        command.append("/F")
    try:
        subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=TERMINATE_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        # A subsequent forced taskkill or the host timeout still bounds cleanup.
        pass


def _terminate_posix_process_group(process: subprocess.Popen[str], *, force: bool) -> None:
    if process.pid is None:
        return
    signal_number = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(process.pid, signal_number)
    except OSError:
        # The process group may already be gone; preserve the primary timeout.
        pass


def _signal_process_tree(process: subprocess.Popen[str], *, force: bool) -> None:
    if os.name == "posix":
        _terminate_posix_process_group(process, force=force)
        return
    if os.name == "nt" and process.pid is not None:
        _taskkill_tree(process.pid, force=force)
        return
    try:
        getattr(process, "kill" if force else "terminate")()
    except OSError:
        # Direct-process fallback is best effort and must not mask a timeout.
        pass


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    _signal_process_tree(process, force=False)
    try:
        process.wait(timeout=TERMINATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        _signal_process_tree(process, force=True)
        try:
            process.wait(timeout=TERMINATE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            # The kill signal has been sent; do not let an unresponsive child
            # extend or mask the host invocation's configured timeout.
            pass
    except OSError:
        # A child may already have been reaped; preserve the caller's timeout.
        pass


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def _combine_output(*values: str | bytes | None) -> str:
    merged = ""
    for value in values:
        next_value = _as_text(value)
        if not next_value:
            continue
        overlap = min(len(merged), len(next_value))
        while overlap and not merged.endswith(next_value[:overlap]):
            overlap -= 1
        merged += next_value[overlap:]
    return merged


def _run_host(command: list[str], workspace: Path, prompt: str, timeout: float) -> tuple[str, str]:
    process = _spawn_host(command, workspace)
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        partial_stdout = _as_text(error.output)
        partial_stderr = _as_text(error.stderr)
        _terminate_process_tree(process)
        try:
            drained_stdout, drained_stderr = process.communicate(timeout=TERMINATE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            drained_stdout, drained_stderr = "", ""
        raise HostTimeoutError(
            timeout,
            _combine_output(partial_stdout, drained_stdout),
            _combine_output(partial_stderr, drained_stderr),
        ) from error
    return _as_text(stdout), _as_text(stderr)


def _retain_artifacts(source: Path, host: str, case_id: str) -> None:
    destination = _result_directory(host, case_id)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def run_case(host: str, case_id: str, *, keep_results: bool = False, host_timeout: float = DEFAULT_HOST_TIMEOUT) -> int:
    """Run one case and return only the deterministic evaluator's exit status."""
    if host not in HOSTS:
        raise ValueError(f"unsupported host: {host}")
    if not isinstance(host_timeout, (int, float)) or isinstance(host_timeout, bool) or host_timeout <= 0:
        raise ValueError("host timeout must be positive")
    if shutil.which(host) is None:
        raise HostUnavailableError(f"{host} executable is required for host evaluation")

    case_path, case = _read_case(case_id)
    transcript_out: list[str] = []
    transcript_err: list[str] = []
    with _workspace(case) as (artifact_dir, workspace, state_dir):
        try:
            _install_skills(workspace, host)
            with running_setup(case, workspace):
                for index, (phase, prompt, patch) in enumerate(_phase_runs(case)):
                    if index and patch:
                        _apply_declared_patch(workspace, patch)
                    try:
                        stdout, stderr = _run_host(HOSTS[host], workspace, prompt, float(host_timeout))
                    except HostTimeoutError as error:
                        transcript_out.append(error.stdout)
                        transcript_err.append(error.stderr)
                        raise
                    transcript_out.append(stdout)
                    transcript_err.append(stderr)
                    diagnostics = evaluate(case_path, workspace, phase, state_dir)
                    if diagnostics:
                        print("\n".join(diagnostics))
                        return 1
        finally:
            _write_transcript(artifact_dir, transcript_out, transcript_err)
            if keep_results:
                _retain_artifacts(artifact_dir, host, case["id"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=sorted(HOSTS), required=True)
    parser.add_argument("--case", required=True, help="case ID from evals/cases")
    parser.add_argument("--keep-results", action="store_true", help="copy artifacts into evals/results after evaluation")
    parser.add_argument("--host-timeout", type=float, default=DEFAULT_HOST_TIMEOUT, help="maximum seconds per host invocation")
    args = parser.parse_args()
    try:
        return run_case(args.host, args.case, keep_results=args.keep_results, host_timeout=args.host_timeout)
    except (HostUnavailableError, HostTimeoutError, RuntimeError, ValueError) as error:
        print(error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
