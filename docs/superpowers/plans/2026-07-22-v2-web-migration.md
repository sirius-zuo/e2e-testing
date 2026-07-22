# V2 Web Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-cut the active web E2E skills from Protocol 1 and `e2e-web-playwright` to independently installable Protocol 2 skills named `e2e-testing` and `e2e-web`, while preserving the complete repository-native browser behavior and safety contract.

**Architecture:** `protocol/v2/` remains canonical. A new atomic initialization operation replaces only a parseable `protocol_version: "1.0"` project manifest with a fresh Protocol 2 run; it never imports or invokes the offline migrator. Both portable skills bundle synchronized copies of the Protocol 2 runtime, core schema, and `e2e.web@1.0` schema. Active skill instructions, deterministic evaluators, cases, host installation, and onboarding documentation use the Protocol 2 model and `e2e-web` name exclusively.

**Tech Stack:** Python 3 standard library, `unittest`, JSON Schema documents, Markdown Agent Skills, JSON evaluation cases, Playwright fixture repositories, Git.

## Global Constraints

- Work only in `/Users/jinzuo/projects/skills/e2e-testing`; never modify `/Users/jinzuo/projects/skills/generate-e2e`.
- At execution time, use `superpowers:using-git-worktrees` before changing implementation files; use branch prefix `codex/`.
- Use test-driven development for every behavior change: failing test, observed failure, minimal implementation, passing test, then commit.
- `protocol/v2/` remains canonical for the runtime, core schema, and web extension schema.
- `protocol/v1/` and `protocol/v2/migrate_v1.py` remain unchanged as historical/offline utilities.
- Historical V1 specs and plans under `docs/` remain unchanged.
- Active skills do not execute, migrate, archive, or preserve Protocol 1 project-manifest history.
- Replace only a parseable object declaring `protocol_version: "1.0"`; malformed and unknown-version manifests remain untouched.
- Rename `skills/e2e-web-playwright/` directly to `skills/e2e-web/`; provide no alias or compatibility shim.
- Playwright remains the V2 internal web driver; other browser drivers end as `capability-unavailable` without test-infrastructure mutation.
- Do not add service, mobile, desktop, composition, or resilience routing in this subproject.
- Preserve repository-native package manager, language, configuration, paths, fixtures, helpers, browser projects, and command style.
- Generation remains `generated-unverified` until selected-check execution evidence exists.
- Never edit application code during web repair.
- Paid Codex or Claude host evaluations require explicit authorization; deterministic tests do not.

## File and Responsibility Map

| Area | Files | Responsibility |
| --- | --- | --- |
| Atomic initialization | `protocol/v2/e2e_protocol.py`, `protocol/v2/__init__.py`, `tests/test_protocol_v2.py` | Create fresh Protocol 2 state and atomically replace only exact Protocol 1 project manifests. |
| Portable bundles | `scripts/sync_protocol.py`, `tests/test_packaging.py`, `skills/e2e-testing/{scripts,references}/`, `skills/e2e-web/{scripts,references}/` | Keep independently installable skills synchronized with canonical Protocol 2 files. |
| Orchestrator contract | `skills/e2e-testing/SKILL.md`, `skills/e2e-testing/references/workflow.md`, `skills/e2e-testing/references/protocol.md` | Discover a web boundary, manage Protocol 2 state, and route only to `e2e-web`. |
| Web contract | `skills/e2e-web/SKILL.md`, `skills/e2e-web/references/workflow.md`, `skills/e2e-web/references/protocol.md`, `skills/e2e-web/references/failure-classification.md` | Run the Playwright-backed web workflow using Protocol 2 records and names. |
| Skill contracts | `tests/test_skill_contracts.py` | Enforce ordering, naming, protocol, safety, extension, and link requirements. |
| Evaluator model | `evals/evaluate_result.py`, `tests/test_evaluation_contracts.py` | Validate Protocol 2 artifacts and enforce selected-check evidence, continuity, budgets, and handoffs. |
| Behavioral cases | `evals/cases/*.json`, `evals/run_host_eval.py`, `evals/HOST_EVALUATION.md` | Express all active behavioral scenarios using Protocol 2 and install the renamed skill. |
| Onboarding | `README.md`, `tests/test_readmes.py` | Describe active V2 web skills and their public names. |

---

### Task 1: Atomic fresh Protocol 2 initialization over exact Protocol 1

**Files:**
- Modify: `protocol/v2/e2e_protocol.py`
- Modify: `protocol/v2/__init__.py`
- Test: `tests/test_protocol_v2.py`

**Interfaces:**
- Consumes: `new_manifest(project_root: str, mode: str = "generate", autonomy: str = "explicit", timestamp: str | None = None) -> dict[str, Any]`, `_manifest_lock(path: Path)`, `_atomic_write(path: Path, data: dict[str, Any])`, `validate_manifest(data: Any, registry: Any = None) -> list[str]`, and `validate_v2_policy(data: Any) -> list[str]`.
- Produces: `initialize_manifest(path: str | Path, project_root: str, mode: str = "generate", autonomy: str = "explicit", replace_protocol_1: bool = False, timestamp: str | None = None) -> dict[str, Any]` and CLI flag `init --replace-protocol-1`.

- [ ] **Step 1: Write failing initialization tests**

Add imports and a focused test class to `tests/test_protocol_v2.py`:

```python
from unittest import mock

from protocol.v2.e2e_protocol import (
    ProtocolError,
    initialize_manifest,
    load_manifest,
    validate_manifest,
    validate_v2_policy,
)


class Protocol2InitializationTests(unittest.TestCase):
    def test_initializes_when_manifest_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".e2e" / "manifest.json"
            saved = initialize_manifest(path, str(root), timestamp="2026-07-22T00:00:00Z")
            self.assertEqual(saved["protocol_version"], "2.0")
            self.assertEqual(saved["run"]["revision"], 1)
            self.assertEqual(load_manifest(path), saved)

    def test_replaces_exact_protocol_1_without_migrating_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".e2e" / "manifest.json"
            path.parent.mkdir()
            path.write_text(json.dumps({
                "protocol_version": "1.0",
                "run_id": "run-legacy",
                "evidence": [{"id": "evidence-legacy"}],
            }))
            saved = initialize_manifest(
                path,
                str(root),
                replace_protocol_1=True,
                timestamp="2026-07-22T00:00:00Z",
            )
            self.assertEqual(saved["protocol_version"], "2.0")
            self.assertEqual(saved["run"]["revision"], 1)
            self.assertNotEqual(saved["run"]["id"], "run-legacy")
            self.assertNotIn("evidence-legacy", json.dumps(saved))
            self.assertEqual(validate_manifest(saved) + validate_v2_policy(saved), [])

    def test_refuses_protocol_1_without_explicit_replacement_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "manifest.json"
            original = b'{"protocol_version":"1.0"}\n'
            path.write_bytes(original)
            with self.assertRaisesRegex(ProtocolError, "existing Protocol 1 manifest requires replacement"):
                initialize_manifest(path, str(root))
            self.assertEqual(path.read_bytes(), original)

    def test_preserves_malformed_and_unknown_manifests(self):
        for original in (b"{not-json\n", b'{"protocol_version":"9.0"}\n'):
            with self.subTest(original=original):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    path = root / "manifest.json"
                    path.write_bytes(original)
                    with self.assertRaises((json.JSONDecodeError, ProtocolError)):
                        initialize_manifest(path, str(root), replace_protocol_1=True)
                    self.assertEqual(path.read_bytes(), original)

    def test_atomic_write_failure_preserves_protocol_1_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "manifest.json"
            original = b'{"protocol_version":"1.0"}\n'
            path.write_bytes(original)
            with mock.patch("protocol.v2.e2e_protocol._atomic_write", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    initialize_manifest(path, str(root), replace_protocol_1=True)
            self.assertEqual(path.read_bytes(), original)
```

- [ ] **Step 2: Run the focused tests and observe the missing interface**

Run:

```bash
python3 -m unittest tests.test_protocol_v2.Protocol2InitializationTests -v
```

Expected: import failure because `initialize_manifest` does not exist.

- [ ] **Step 3: Implement the atomic initializer**

Add this function immediately before `save_manifest` in `protocol/v2/e2e_protocol.py`:

```python
def initialize_manifest(
    path: str | Path,
    project_root: str,
    mode: str = "generate",
    autonomy: str = "explicit",
    replace_protocol_1: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Create fresh Protocol 2 state, optionally replacing exact Protocol 1 state."""
    manifest_path = Path(path)
    fresh = new_manifest(project_root, mode, autonomy, timestamp)
    with _manifest_lock(manifest_path):
        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                raise ProtocolError("existing manifest must be an object")
            version = existing.get("protocol_version")
            if version == "1.0":
                if not replace_protocol_1:
                    raise ProtocolError("existing Protocol 1 manifest requires replacement")
            else:
                raise ProtocolError(f"refusing to replace existing manifest with protocol_version {version!r}")

        saved = json.loads(json.dumps(fresh))
        saved["run"]["revision"] = 1
        saved["run"]["updated_at"] = timestamp or _utc_now()
        errors = validate_manifest(saved) + validate_v2_policy(saved)
        if errors:
            raise ProtocolError("invalid input: " + "; ".join(errors))
        _atomic_write(manifest_path, saved)
        return saved
```

Export `initialize_manifest` from `protocol/v2/__init__.py`. Change the `init` CLI parser and branch in `protocol/v2/e2e_protocol.py`:

```python
init.add_argument(
    "--replace-protocol-1",
    action="store_true",
    help="atomically discard an existing Protocol 1 manifest and initialize Protocol 2",
)
```

```python
result = initialize_manifest(
    output,
    args.project_root,
    args.mode,
    args.autonomy,
    replace_protocol_1=args.replace_protocol_1,
)
```

Do not import `protocol.v1` or `protocol.v2.migrate_v1`.

- [ ] **Step 4: Add a CLI regression test**

Add to `Protocol2InitializationTests`:

```python
def test_cli_replaces_protocol_1_only_with_flag(self):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / ".e2e" / "manifest.json"
        path.parent.mkdir()
        path.write_text('{"protocol_version":"1.0"}\n')
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "protocol/v2/e2e_protocol.py"),
                "init",
                "--project-root", str(root),
                "--output", str(path),
                "--replace-protocol-1",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["protocol_version"], "2.0")
```

- [ ] **Step 5: Run Protocol 2 tests**

Run:

```bash
python3 -m unittest tests.test_protocol_v2 tests.test_protocol_v2_schema tests.test_protocol_v2_extensions tests.test_protocol_v2_migration -v
```

Expected: all Protocol 2 tests pass; offline migration tests remain unchanged.

- [ ] **Step 6: Commit the atomic initializer**

```bash
git add protocol/v2/e2e_protocol.py protocol/v2/__init__.py tests/test_protocol_v2.py
git commit -m "feat: initialize fresh protocol 2 over protocol 1"
```

---

### Task 2: Hard rename and synchronize portable Protocol 2 bundles

**Files:**
- Modify: `tests/test_packaging.py`
- Modify: `scripts/sync_protocol.py`
- Rename: `skills/e2e-web-playwright/` to `skills/e2e-web/`
- Replace: `skills/e2e-testing/scripts/e2e_protocol.py`
- Replace: `skills/e2e-testing/references/manifest.schema.json`
- Create: `skills/e2e-testing/references/extensions/web.schema.json`
- Replace: `skills/e2e-web/scripts/e2e_protocol.py`
- Replace: `skills/e2e-web/references/manifest.schema.json`
- Create: `skills/e2e-web/references/extensions/web.schema.json`

**Interfaces:**
- Consumes: canonical `protocol/v2/e2e_protocol.py`, `protocol/v2/manifest.schema.json`, and `protocol/v2/extensions/web.schema.json`.
- Produces: two independently runnable bundles at `skills/e2e-testing` and `skills/e2e-web`, plus `sync(check: bool) -> list[str]` over the Protocol 2 file set.

- [ ] **Step 1: Rewrite packaging tests first**

Replace the constants and copy assertion in `tests/test_packaging.py` with:

```python
TARGETS = [ROOT / "skills/e2e-testing", ROOT / "skills/e2e-web"]
CANONICAL_FILES = {
    "references/manifest.schema.json": ROOT / "protocol/v2/manifest.schema.json",
    "references/extensions/web.schema.json": ROOT / "protocol/v2/extensions/web.schema.json",
    "scripts/e2e_protocol.py": ROOT / "protocol/v2/e2e_protocol.py",
}


class PackagingTests(unittest.TestCase):
    def test_protocol_copies_match_canonical_files(self):
        for target in TARGETS:
            for relative, canonical in CANONICAL_FILES.items():
                self.assertEqual(
                    (target / relative).read_bytes(),
                    canonical.read_bytes(),
                    f"stale bundle: {target.relative_to(ROOT) / relative}",
                )

    def test_old_web_skill_directory_is_absent(self):
        self.assertFalse((ROOT / "skills/e2e-web-playwright").exists())
```

Retain `test_each_bundled_utility_runs_standalone` and make it iterate over the new `TARGETS`.

- [ ] **Step 2: Run the packaging tests and observe the old package failure**

Run:

```bash
python3 -m unittest tests.test_packaging -v
```

Expected: failure because `skills/e2e-web` and the synchronized Protocol 2 files do not exist.

- [ ] **Step 3: Rename the package and update the synchronizer**

Run:

```bash
git mv skills/e2e-web-playwright skills/e2e-web
```

Replace the synchronization constants in `scripts/sync_protocol.py`:

```python
CANONICAL_FILES = (
    (ROOT / "protocol/v2/manifest.schema.json", "references/manifest.schema.json"),
    (ROOT / "protocol/v2/extensions/web.schema.json", "references/extensions/web.schema.json"),
    (ROOT / "protocol/v2/e2e_protocol.py", "scripts/e2e_protocol.py"),
)
TARGETS = (ROOT / "skills/e2e-testing", ROOT / "skills/e2e-web")
```

Keep `sync()` responsible for creating missing parent directories before copying.

- [ ] **Step 4: Generate the portable copies**

Run:

```bash
python3 scripts/sync_protocol.py
```

Expected: both skills contain the canonical Protocol 2 utility, core schema, and web schema.

- [ ] **Step 5: Verify synchronization and standalone execution**

Run:

```bash
python3 scripts/sync_protocol.py --check
python3 -m unittest tests.test_packaging -v
```

Expected: the sync check prints nothing and exits 0; packaging tests pass.

- [ ] **Step 6: Commit the rename and synchronized bundles**

```bash
git add scripts/sync_protocol.py tests/test_packaging.py skills/e2e-testing skills/e2e-web
git commit -m "feat: rename and package the protocol 2 web skill"
```

---

### Task 3: Rewrite active skill contracts for the Protocol 2 web path

**Files:**
- Modify: `tests/test_skill_contracts.py`
- Modify: `skills/e2e-testing/SKILL.md`
- Modify: `skills/e2e-testing/references/workflow.md`
- Modify: `skills/e2e-testing/references/protocol.md`
- Modify: `skills/e2e-web/SKILL.md`
- Modify: `skills/e2e-web/references/workflow.md`
- Modify: `skills/e2e-web/references/protocol.md`
- Modify: `skills/e2e-web/references/failure-classification.md`

**Interfaces:**
- Consumes: `initialize_manifest` CLI behavior from Task 1 and bundle paths from Task 2.
- Produces: active Agent Skill contracts that create/resume Protocol 2 web runs and route using `e2e-web` only.

- [ ] **Step 1: Change skill contract expectations before documentation**

Update `tests/test_skill_contracts.py` so the orchestrator and web assertions require these exact phrases and paths:

```python
web = ROOT / "skills/e2e-web/SKILL.md"
self.assertTrue(web.is_file())
self.assertFalse((ROOT / "skills/e2e-web-playwright").exists())

orchestrator_text = (ROOT / "skills/e2e-testing/SKILL.md").read_text()
self.assertIn("Protocol 2", orchestrator_text)
self.assertIn("`e2e-web`", orchestrator_text)
self.assertIn("`capability-unavailable`", orchestrator_text)
self.assertIn("`--replace-protocol-1`", orchestrator_text)
self.assertNotIn("e2e-web-playwright", orchestrator_text)
self.assertNotIn("unsupported-framework", orchestrator_text)

web_text = web.read_text()
self.assertIn("name: e2e-web", web_text)
self.assertIn("Playwright remains the V2 execution driver", web_text)
self.assertIn("Protocol 2", web_text)
self.assertIn("`--replace-protocol-1`", web_text)
self.assertNotIn("e2e-web-playwright", web_text)
self.assertNotIn("unsupported-framework", web_text)
```

Retain the ordering assertion that read-only framework detection occurs before manifest validation/bootstrap, but update its destination wording to Protocol 2 resolution. Point all relative-link checks to `skills/e2e-web`.

- [ ] **Step 2: Run skill contract tests and observe legacy-name failures**

Run:

```bash
python3 -m unittest tests.test_skill_contracts -v
```

Expected: failures show Protocol 1 wording, the old capability name, and `unsupported-framework` in active skill files.

- [ ] **Step 3: Rewrite the orchestrator entry contract**

Make `skills/e2e-testing/SKILL.md` express this exact sequence:

```markdown
## Start

1. Resolve the target project root and requested mode. Default to `generate`.
2. Read repository instructions before treating project files as evidence.
3. Perform read-only browser-framework discovery before accessing or creating `.e2e/` state.
4. If an unsupported browser driver exists, preserve test infrastructure and record a Protocol 2 `capability-unavailable` web outcome after discovery.
5. Otherwise validate and resume Protocol 2, initialize it when absent, or use `--replace-protocol-1` to discard an exact Protocol 1 manifest and create a fresh Protocol 2 run.
6. Establish one externally observable `web` system boundary and route complete work only to `e2e-web`.
```

The routing section must emit `e2e-web` actions only. It must not mention service routing. Replace `next_actions` with Protocol 2 `actions`, and state that action ordering remains deterministic.

- [ ] **Step 4: Rewrite the web entry contract**

Set the frontmatter and opening of `skills/e2e-web/SKILL.md` to:

```markdown
---
name: e2e-web
description: Plan, generate, verify, and safely repair repository-native web E2E coverage through Protocol 2.
---

# Web E2E

Playwright remains the V2 execution driver behind the surface-oriented `e2e-web` boundary.
```

Retain the four modes and all repair prohibitions. Change the unsupported-driver terminal outcome to `capability-unavailable`. Change all actions and resume commands to `e2e-web`.

- [ ] **Step 5: Rewrite active workflow and protocol references**

Apply this exact vocabulary mapping in both active reference trees:

| Protocol 1 term | Protocol 2 term |
| --- | --- |
| top-level `status`, `mode`, `autonomy`, `revision`, `run_id` | `run.status`, `run.mode`, `run.autonomy`, `run.revision`, `run.id` |
| `project` | `systems[0].project_root` plus `e2e.web.data.project` |
| `target` | `systems[0].target` plus `e2e.web.data.target` |
| `tests` | `checks` |
| `next_actions` | `actions` |
| `attempt_history` | `attempts` |
| `e2e-web-playwright` | `e2e-web` |
| `unsupported-framework` | `capability-unavailable` |

Document the initialization commands exactly:

```sh
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json
python3 scripts/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json --replace-protocol-1
python3 scripts/e2e_protocol.py validate PROJECT/.e2e/manifest.json
```

State that malformed and unknown-version manifests are preserved. State that only an exact parseable Protocol 1 object may be replaced. Do not describe migration or history preservation.

- [ ] **Step 6: Update classification resume commands**

In `skills/e2e-web/references/failure-classification.md` and `skills/e2e-web/references/workflow.md`, require:

```json
{"resume": {"command": "e2e-web verify"}}
```

Retain the product-defect rule that application code is never edited by the web skill.

- [ ] **Step 7: Validate both skill bundles**

Run:

```bash
python3 scripts/validate_skills.py
python3 -m unittest tests.test_skill_contracts -v
```

Expected: validator exits 0 with no output; skill contract tests pass.

- [ ] **Step 8: Commit the active skill contracts**

```bash
git add skills/e2e-testing skills/e2e-web tests/test_skill_contracts.py
git commit -m "docs: migrate web skill contracts to protocol 2"
```

---

### Task 4: Port the deterministic evaluator to the Protocol 2 data model

**Files:**
- Modify: `evals/evaluate_result.py`
- Modify: `tests/test_evaluation_contracts.py`

**Interfaces:**
- Consumes: bundled Protocol 2 functions `validate_manifest` and `validate_v2_policy`.
- Produces: evaluator helpers over `run`, `checks`, `actions`, and `attempts`; evidence fields `check_ids` and `outcomes[].check_id`; unchanged public `evaluate(case_path, workspace, phase=None, state_dir=None) -> list[str]`.

- [ ] **Step 1: Create a valid Protocol 2 evaluator fixture first**

Change `tests/test_evaluation_contracts.py` to import `new_manifest` and `save_manifest` from `protocol.v2.e2e_protocol`. Replace `_manifest` with:

```python
def _manifest(workspace: Path, status: str = "generated-unverified") -> dict:
    data = new_manifest(str(workspace), timestamp="2026-07-22T00:00:00Z")
    data["run"]["status"] = status
    data["systems"][0]["primary_surface"] = "web"
    data["systems"][0]["boundary"] = {
        "status": "declared",
        "actors": ["user"],
        "public_interfaces": [{
            "id": "interface-web-primary",
            "kind": "web",
            "endpoint_ref": None,
            "evidence_ids": ["evidence-source"],
        }],
        "evidence_ids": ["evidence-source"],
    }
    data["journeys"] = [{
        "id": "journey-checkout",
        "system_id": "system-primary",
        "status": "covered",
    }]
    data["execution_units"] = [{
        "id": "execution-web-primary",
        "system_id": "system-primary",
        "surface": "web",
        "capability": "e2e-web",
        "extension_id": "extension-web-primary",
        "status": status,
    }]
    data["checks"] = [{
        "id": "check-checkout",
        "journey_id": "journey-checkout",
        "execution_unit_id": "execution-web-primary",
        "status": "generated",
    }]
    data["evidence"] = [{"id": "evidence-source", "kind": "source-derived"}]
    data["extensions"] = [{
        "id": "extension-web-primary",
        "namespace": "e2e.web",
        "version": "1.0",
        "owner": "e2e-web",
        "data": {"driver": "playwright", "project": {}, "target": {}},
    }]
    return data
```

Change test evidence helpers from `test_ids`/`test_id` to `check_ids`/`check_id`, and use `check-checkout` as the default ID.

- [ ] **Step 2: Run evaluator tests and observe Protocol 1 assumptions**

Run:

```bash
python3 -m unittest tests.test_evaluation_contracts.EvaluatorContractTests -v
```

Expected: failures reference top-level `status`, `mode`, `revision`, `tests`, `next_actions`, or `attempt_history`.

- [ ] **Step 3: Load both Protocol 2 validators**

Replace `_load_validator` in `evals/evaluate_result.py` with:

```python
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
```

- [ ] **Step 4: Add strict Protocol 2 accessors**

Add after `_ids`:

```python
def _run(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("run")
    return value if isinstance(value, dict) else {}


def _systems(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    value = manifest.get("systems")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _run_value(manifest: dict[str, Any], field: str) -> Any:
    return _run(manifest).get(field)
```

Use these accessors rather than accepting Protocol 1 fallbacks.

- [ ] **Step 5: Translate evaluator collections and traceability**

Replace `_check_required_ids` and `_check_traceability` collection access with:

```python
collections = {
    "journey": "journeys",
    "check": "checks",
    "evidence": "evidence",
    "handoff": "handoffs",
    "action": "actions",
    "attempt": "attempts",
}
```

```python
checks_by_journey = {
    item.get("journey_id")
    for item in manifest.get("checks", [])
    if isinstance(item, dict) and isinstance(item.get("journey_id"), str)
}
```

Change diagnostic labels and case expectation keys to `required_check_ids`, `required_action_ids`, and `required_attempt_ids`.

- [ ] **Step 6: Translate status, evidence, budgets, and continuity**

Apply these exact evaluator mappings throughout `evals/evaluate_result.py`:

```python
status = _run_value(manifest, "status")
mode = _run_value(manifest, "mode")
revision = _run_value(manifest, "revision")
run_id = _run_value(manifest, "id")
autonomy = _run_value(manifest, "autonomy")
budget = _run_value(manifest, "attempt_budget")
checks = manifest.get("checks")
actions = manifest.get("actions")
attempts = manifest.get("attempts")
```

Update execution evidence validation to read `check_ids` and `outcomes[].check_id`. Update repair attempts to read `check_ids`. Keep checkpoint files shaped as `{"run_id": ..., "revision": ..., "handoff_ids": [...]}`, but populate and compare them through `run.id` and `run.revision`.

Change the unsupported-driver branch to:

```python
if status == "capability-unavailable" and not any(
    isinstance(item, dict)
    and isinstance(item.get("framework"), str)
    and item["framework"]
    and isinstance(item.get("source_locations"), list)
    and bool(item["source_locations"])
    and item.get("read_only") is True
    for item in evidence
):
    diagnostics.append("missing capability-unavailable framework detection evidence")
```

In `evaluate()`, validate with `_validate_manifest(manifest)` and compare expected status, mode, and autonomy through `_run_value`.

- [ ] **Step 7: Translate evaluator tests mechanically and preserve assertions**

Apply this exact test mapping throughout `tests/test_evaluation_contracts.py`:

| Old test expression | New expression |
| --- | --- |
| `manifest["status"]` | `manifest["run"]["status"]` |
| `manifest["mode"]` | `manifest["run"]["mode"]` |
| `manifest["autonomy"]` | `manifest["run"]["autonomy"]` |
| `manifest["revision"]` | `manifest["run"]["revision"]` |
| `manifest["run_id"]` | `manifest["run"]["id"]` |
| `manifest["tests"]` | `manifest["checks"]` |
| `manifest["next_actions"]` | `manifest["actions"]` |
| `manifest["attempt_history"]` | `manifest["attempts"]` |
| `test-*`, `test_ids`, `test_id` | `check-*`, `check_ids`, `check_id` |
| `e2e-web-playwright verify` | `e2e-web verify` |

Every constructed journey must include `system_id: "system-primary"`; every constructed check must include `execution_unit_id: "execution-web-primary"`.

- [ ] **Step 8: Run the evaluator contract suite**

Run:

```bash
python3 -m unittest tests.test_evaluation_contracts -v
```

Expected: all evaluator, fixture-integrity, continuity, repair, and host-harness contract tests pass.

- [ ] **Step 9: Commit the Protocol 2 evaluator**

```bash
git add evals/evaluate_result.py tests/test_evaluation_contracts.py
git commit -m "test: evaluate web behavior through protocol 2"
```

---

### Task 5: Update behavioral cases and host installation

**Files:**
- Modify: `evals/cases/auto-budget.json`
- Modify: `evals/cases/conflicting-evidence.json`
- Modify: `evals/cases/existing-playwright.json`
- Modify: `evals/cases/greenfield-source.json`
- Modify: `evals/cases/live-assisted-generation.json`
- Modify: `evals/cases/missing-credentials.json`
- Modify: `evals/cases/product-defect-handoff.json`
- Modify: `evals/cases/repair-test-defect.json`
- Modify: `evals/cases/unsupported-cypress.json`
- Modify: `evals/cases/verify-pass.json`
- Modify: `evals/run_host_eval.py`
- Modify: `evals/HOST_EVALUATION.md`
- Modify: `tests/test_evaluation_contracts.py`

**Interfaces:**
- Consumes: Protocol 2 evaluator expectation keys from Task 4 and portable skill directory `skills/e2e-web` from Task 2.
- Produces: ten Protocol 2 behavioral cases and host workspaces containing `e2e-testing` plus `e2e-web`.

- [ ] **Step 1: Change case-contract tests first**

In `tests/test_evaluation_contracts.py`, update the case assertions to require:

```python
self.assertEqual(case["entry_skill"], "e2e-testing")
self.assertNotIn("e2e-web-playwright", json.dumps(case))
```

Update the host installation assertion to:

```python
self.assertTrue((workspace / skill_root / "e2e-testing" / "SKILL.md").is_file())
self.assertTrue((workspace / skill_root / "e2e-web" / "SKILL.md").is_file())
self.assertFalse((workspace / skill_root / "e2e-web-playwright").exists())
```

- [ ] **Step 2: Run case and host-harness tests and observe failures**

Run:

```bash
python3 -m unittest tests.test_evaluation_contracts.CaseContractTests tests.test_evaluation_contracts.HostRunnerContractTests -v
```

Expected: failures identify the old installed skill name and Protocol 1 case expectations.

- [ ] **Step 3: Update host skill installation**

Change `evals/run_host_eval.py`:

```python
SKILL_NAMES = ("e2e-testing", "e2e-web")
```

Do not add a fallback copy from the old directory.

- [ ] **Step 4: Update exact case vocabulary**

Apply these changes to the ten files under `evals/cases/`:

| File | Exact change |
| --- | --- |
| `unsupported-cypress.json` | Change `manifest_status` from `unsupported-framework` to `capability-unavailable`; retain `evidence-framework-detection` and all no-mutation globs. |
| `auto-budget.json` | Rename `required_attempt_history_ids` to `required_attempt_ids`. |
| `missing-credentials.json` | Rename `required_next_action_ids` to `required_action_ids`. |
| All ten cases | Keep public entry skill `e2e-testing`; ensure prompts and expectation data contain no `e2e-web-playwright`, `unsupported-framework`, `tests`, `next_actions`, or `attempt_history` protocol vocabulary. |

Do not change fixture application source or Playwright infrastructure merely to update protocol vocabulary.

- [ ] **Step 5: Update unsupported-driver contract assertions**

In `tests/test_evaluation_contracts.py`, change the unsupported case setup and assertions to:

```python
manifest = _manifest(workspace, "capability-unavailable")
manifest["evidence"] = [{
    "id": "evidence-framework-detection",
    "framework": "cypress",
    "source_locations": ["package.json"],
    "read_only": True,
}]
```

```python
self.assertIn(
    "missing capability-unavailable framework detection evidence",
    diagnostics,
)
```

- [ ] **Step 6: Update host-evaluation documentation**

In `evals/HOST_EVALUATION.md`, state that isolated workspaces receive `e2e-testing` and `e2e-web`, manifests must validate as Protocol 2, and host runs remain opt-in because they consume paid model usage. Remove active instructions that invoke `e2e-web-playwright` or expect `unsupported-framework`.

- [ ] **Step 7: Run all deterministic evaluation tests**

Run:

```bash
python3 -m unittest tests.test_evaluation_contracts -v
```

Expected: all deterministic evaluator, case, fixture, and host-runner contract tests pass. Do not run Codex or Claude host cases without explicit user authorization.

- [ ] **Step 8: Commit behavioral cases and host installation**

```bash
git add evals/cases evals/run_host_eval.py evals/HOST_EVALUATION.md tests/test_evaluation_contracts.py
git commit -m "test: migrate web evaluation cases to protocol 2"
```

---

### Task 6: Update active onboarding and contributor documentation

**Files:**
- Modify: `tests/test_readmes.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: final skill names and paths from Task 2.
- Produces: active user/contributor entry points for the Protocol 2 web baseline.

- [ ] **Step 1: Change README expectations first**

Update `tests/test_readmes.py`:

```python
for required in (
    "e2e-testing",
    "e2e-web",
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
    "evals/fixtures/README.md",
    "evals/HOST_EVALUATION.md",
):
    self.assertTrue((ROOT / relative).is_file(), relative)
    self.assertIn(relative, text)

self.assertNotIn("e2e-web-playwright", text)
self.assertNotIn("Protocol 1.0", text)
```

- [ ] **Step 2: Run README tests and observe legacy-name failures**

Run:

```bash
python3 -m unittest tests.test_readmes -v
```

Expected: failure because the README still links to `skills/e2e-web-playwright` and describes the browser-only Protocol 1 baseline.

- [ ] **Step 3: Rewrite the active README entry points**

Make the README introduction and skill list state:

```markdown
Portable Agent Skills for repository-native web end-to-end testing on Protocol 2.

- [`e2e-testing`](skills/e2e-testing/SKILL.md) plans externally observable web journeys, applies shared safety policy, and coordinates durable Protocol 2 actions and handoffs.
- [`e2e-web`](skills/e2e-web/SKILL.md) implements Playwright-backed planning, generation, selected verification, failure classification, and bounded test repair behind a surface-oriented public boundary.
```

The quick start must direct normal users to `e2e-testing`. Direct invocation must use `e2e-web`. The repository layout must show `protocol/v2/`, `skills/e2e-testing/`, and `skills/e2e-web/`. State that generation ends `generated-unverified` and verification requires selected-check evidence and authorization.

Do not rewrite historical documents linked only as design history.

- [ ] **Step 4: Run README and link tests**

Run:

```bash
python3 -m unittest tests.test_readmes -v
python3 scripts/validate_skills.py
```

Expected: README tests pass; skill validation exits 0 with no output.

- [ ] **Step 5: Commit onboarding documentation**

```bash
git add README.md tests/test_readmes.py
git commit -m "docs: publish protocol 2 web entry points"
```

---

### Task 7: Add the active-surface release gate and run full verification

**Files:**
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: all active runtime, skill, evaluator, case, and README artifacts from Tasks 1-6.
- Produces: a deterministic guard preventing the old public name or Protocol 1 runtime contract from returning to active surfaces.

- [ ] **Step 1: Write the release-gate test**

Add to `SkillContractTests`:

```python
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

def test_active_bundles_publish_protocol_2_and_web_extension(self):
    for skill in ("e2e-testing", "e2e-web"):
        root = ROOT / "skills" / skill
        schema = json.loads((root / "references/manifest.schema.json").read_text())
        web = json.loads((root / "references/extensions/web.schema.json").read_text())
        self.assertEqual(schema["properties"]["protocol_version"]["const"], "2.0")
        self.assertEqual(web["$id"], "urn:e2e-testing:extension:web:1.0")
```

Add `import json` to the test module.

- [ ] **Step 2: Run the release gate and fix only identified active leaks**

Run:

```bash
python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_active_surfaces_have_no_legacy_web_runtime_contract tests.test_skill_contracts.SkillContractTests.test_active_bundles_publish_protocol_2_and_web_extension -v
```

Expected: both tests pass. If the first test reports a path, replace the legacy active vocabulary in that exact path; do not alter `protocol/v1/`, `protocol/v2/migrate_v1.py`, migration tests, or historical `docs/` files.

- [ ] **Step 3: Verify canonical synchronization**

Run:

```bash
python3 scripts/sync_protocol.py --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Validate portable skills**

Run:

```bash
python3 scripts/validate_skills.py
```

Expected: no output and exit code 0.

- [ ] **Step 5: Run the full deterministic suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: every test reports `ok` and the final result is `OK` with zero failures and zero errors.

- [ ] **Step 6: Confirm the protected historical/offline files are unchanged**

Run:

```bash
git diff origin/main -- protocol/v1 protocol/v2/migrate_v1.py docs/superpowers/specs/2026-07-20-e2e-testing-design.md docs/superpowers/plans/2026-07-20-e2e-testing-v1.md
```

Expected: no output.

- [ ] **Step 7: Review the complete implementation diff**

Run:

```bash
git status --short
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected: only V2 web-migration implementation files are changed; whitespace check exits 0. Ignore pre-existing untracked `__pycache__/` directories and never stage them.

- [ ] **Step 8: Commit the release gate**

```bash
git add tests/test_skill_contracts.py
git commit -m "test: enforce the active protocol 2 web boundary"
```

- [ ] **Step 9: Re-run full verification after the final commit**

Run:

```bash
python3 scripts/sync_protocol.py --check
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
```

Expected: both checks exit 0 with no output and the test suite ends `OK`.

## Execution Notes

- The implementation sequence is intentionally dependent: Task 1 provides safe initialization; Task 2 packages it; Task 3 documents it; Task 4 ports deterministic validation; Task 5 ports scenarios and host installation; Task 6 publishes active entry points; Task 7 guards the complete boundary.
- Do not run host-model evaluations during implementation unless the user explicitly authorizes that paid evaluation session. The deterministic host-runner tests use mocks and remain required.
- After all tasks pass, use `superpowers:requesting-code-review`, then `superpowers:finishing-a-development-branch` to choose merge, PR, or cleanup.
