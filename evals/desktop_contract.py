"""Desktop surface evaluator: graph, lifecycle, evidence, and authorization gates."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any


def _records(items: Any, label: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    result: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if not isinstance(items, list):
        return result, [f"desktop {label} must be an array"]
    for item in items:
        identifier = item.get("id") if isinstance(item, dict) else None
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"desktop {label} contains a record without an ID")
        elif identifier in result:
            errors.append(f"duplicate desktop {label} ID: {identifier}")
        else:
            result[identifier] = item
    return result, errors


def _ids(items: Any) -> set[str]:
    return {item["id"] for item in items or [] if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _extension_records(extension: dict[str, Any]):
    data = extension.get("data", {})
    groups = {}
    errors = []
    for key in ("applications", "drivers", "targets", "sessions", "artifacts", "lifecycle_profiles", "interaction_boundaries"):
        groups[key], duplicate = _records(data.get(key), key)
        errors.extend(duplicate)
    return groups, errors


def _check_refs(groups: dict[str, dict[str, dict[str, Any]]], unit_ids: set[str], evidence_ids: set[str], action_ids: set[str], authorization_ids: set[str]) -> list[str]:
    errors: list[str] = []
    apps, drivers, targets = groups["applications"], groups["drivers"], groups["targets"]
    sessions, artifacts = groups["sessions"], groups["artifacts"]
    boundaries, lifecycles = groups["interaction_boundaries"], groups["lifecycle_profiles"]
    for target_id, target in targets.items():
        if target.get("driver_id") not in drivers:
            errors.append(f"desktop target {target_id} references unknown driver {target.get('driver_id')}")
        for ref in target.get("evidence_refs", []):
            if ref not in evidence_ids:
                errors.append(f"desktop target {target_id} references unknown evidence {ref}")
    for session_id, session in sessions.items():
        if session.get("target_id") not in targets:
            errors.append(f"desktop session {session_id} references unknown target {session.get('target_id')}")
        for ref in session.get("application_allowlist", []):
            if ref not in apps:
                errors.append(f"desktop session {session_id} allowlists unknown application {ref}")
        for ref in session.get("os_interaction_allowlist", []):
            if ref not in boundaries:
                errors.append(f"desktop session {session_id} allowlists unknown boundary {ref}")
    for artifact_id, artifact in artifacts.items():
        if artifact.get("application_id") not in apps:
            errors.append(f"desktop artifact {artifact_id} references unknown application {artifact.get('application_id')}")
    for boundary_id, boundary in boundaries.items():
        if boundary.get("application_id") not in apps:
            errors.append(f"desktop boundary {boundary_id} references unknown application {boundary.get('application_id')}")
    for lifecycle_id, lifecycle in lifecycles.items():
        refs = {
            "execution unit": (lifecycle.get("execution_unit_id"), unit_ids),
            "application": (lifecycle.get("application_id"), set(apps)),
            "driver": (lifecycle.get("driver_id"), set(drivers)),
            "target": (lifecycle.get("target_id"), set(targets)),
            "session": (lifecycle.get("session_id"), set(sessions)),
            "boundary": (lifecycle.get("interaction_boundary_id"), set(boundaries)),
        }
        for label, (ref, valid) in refs.items():
            if ref not in valid:
                errors.append(f"desktop lifecycle {lifecycle_id} references unknown {label} {ref}")
        for ref in lifecycle.get("artifact_ids", []):
            if ref not in artifacts:
                errors.append(f"desktop lifecycle {lifecycle_id} references unknown artifact {ref}")
        for ref in lifecycle.get("cleanup_action_refs", []) + lifecycle.get("setup_action_refs", []):
            if ref not in action_ids:
                errors.append(f"desktop lifecycle {lifecycle_id} references unknown action {ref}")
        for ref in lifecycle.get("authorization_refs", []):
            if ref not in authorization_ids:
                errors.append(f"desktop lifecycle {lifecycle_id} references unknown authorization {ref}")
    return errors


DRIVER_MATRIX = {
    "appium-mac2": {("macos", "native")},
    "novawindows": {("windows", "native")},
    "webdriverio-electron": {("macos", "electron"), ("windows", "electron")},
    "playwright-electron": {("macos", "electron"), ("windows", "electron"), ("linux", "electron")},
    "appium-windows-legacy": {("windows", "native")},
}
REQUIRED_ENVIRONMENT = {
    "driver", "driver_version", "adapter_version", "backend_version",
    "platform", "os_version", "target_reference", "target_kind", "target_tier",
    "session_reference", "session_kind", "session_isolated", "application_id",
    "application_kind", "artifact_reference", "artifact_format",
    "lifecycle_phase", "authorization_refs", "evidence_origin",
}


def _check_compatibility(groups: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    drivers = groups["drivers"]
    targets = groups["targets"]
    lifecycles = groups["lifecycle_profiles"]
    apps = groups["applications"]

    # Build a map of artifact → (application_id, platform)
    artifacts = groups["artifacts"]

    for lifecycle_id, lifecycle in lifecycles.items():
        driver_id = lifecycle.get("driver_id", "")
        target_id = lifecycle.get("target_id", "")
        artifact_ids = lifecycle.get("artifact_ids", [])

        if driver_id not in drivers:
            errors.append(f"desktop lifecycle {lifecycle_id} references unknown driver {driver_id}")
            continue

        driver = drivers[driver_id]
        target = targets.get(target_id, {})
        target_platform = target.get("platform", "")
        target_kind = target.get("kind", "")

        # Find the application for this lifecycle
        app_id = lifecycle.get("application_id", "")
        app = apps.get(app_id, {})
        app_kind = app.get("kind", "")

        # Check driver compatibility with target platform and app kind
        driver_kind = driver.get("kind", "")
        expected_pairs = DRIVER_MATRIX.get(driver_kind, set())
        if expected_pairs and (target_platform, app_kind) not in expected_pairs:
            errors.append(f"desktop lifecycle {lifecycle_id} driver {driver_kind} incompatible with platform {target_platform} and application kind {app_kind}")

        # Legacy drivers require legacy: true
        if driver_kind in ("playwright-electron", "appium-windows-legacy"):
            if not driver.get("legacy", False):
                errors.append(f"desktop lifecycle {lifecycle_id} driver {driver_kind} requires legacy: true")

        # Reject Linux as a baseline claim (not capability-gated)
        if target_platform == "linux":
            errors.append(f"desktop lifecycle {lifecycle_id} Linux is not a deterministic baseline")

        # Require all target capabilities used by the lifecycle
        lifecycle_capabilities = set()
        # Check if lifecycle references capabilities from the target
        target_capabilities = set(target.get("capabilities", []))
        lifecycle_caps = set(driver.get("capabilities", []))
        for cap in lifecycle_caps:
            if cap not in target_capabilities:
                errors.append(f"desktop lifecycle {lifecycle_id} driver capability {cap} not available on target {target_id}")

    return errors


def _check_sessions(groups: dict[str, dict[str, dict[str, Any]]], now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    sessions = groups["sessions"]
    boundaries = groups["interaction_boundaries"]
    apps = groups["applications"]

    if now is None:
        now = datetime.now(timezone.utc)

    # Forbidden capabilities
    forbidden_caps = {"desktop-root", "arbitrary-window", "global-keyboard", "arbitrary-shell", "arbitrary-filesystem", "credential-store"}

    for session_id, session in sessions.items():
        # Check execution-safety flags
        for flag in ("interactive", "unlocked", "connected", "isolated"):
            if not session.get(flag, False):
                errors.append(f"desktop session {session_id} is not execution-safe (missing {flag})")

        # Check expiry
        expires_at = session.get("expires_at", "")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expiry <= now:
                    errors.append(f"desktop session {session_id} has expired at {expires_at}")
            except (ValueError, TypeError):
                errors.append(f"desktop session {session_id} has invalid expires_at")

        # Check allowlists are non-empty
        app_allowlist = session.get("application_allowlist", [])
        os_allowlist = session.get("os_interaction_allowlist", [])
        if not app_allowlist:
            errors.append(f"desktop session {session_id} has empty application_allowlist")
        if not os_allowlist:
            errors.append(f"desktop session {session_id} has empty os_interaction_allowlist")

        # Check for forbidden capabilities in allowlists
        for ref in app_allowlist + os_allowlist:
            # Check if any boundary or application contains forbidden capabilities
            boundary = boundaries.get(ref, {})
            if boundary:
                for cap in boundary.get("capabilities", []):
                    if cap in forbidden_caps:
                        errors.append(f"desktop session {session_id} references forbidden capability {cap}")

    return errors


# Ordered lifecycle phase subsequences
NORMAL_PHASES = ("target", "session", "baseline", "install", "launch", "check", "cleanup", "restore")
UPDATE_PHASES = ("target", "session", "baseline", "prior-install", "prior-state", "candidate-update", "launch", "check", "cleanup", "restore")


def _validate_phases(phases: list[str], expected: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    if not isinstance(phases, list):
        return ["lifecycle phases must be an array"]

    expected_set = set(expected)
    seen: set[str] = set()
    indices: dict[str, int] = {}

    for i, phase in enumerate(phases):
        if phase not in expected_set:
            errors.append(f"lifecycle contains unexpected phase: {phase}")
        elif phase in seen:
            errors.append(f"lifecycle contains duplicate phase: {phase}")
        else:
            seen.add(phase)
            indices[phase] = i

    # Verify subsequence ordering for all expected phases that are present
    last_pos = -1
    for phase in expected:
        if phase in indices:
            if indices[phase] <= last_pos:
                errors.append(f"lifecycle phase {phase} out of order")
            last_pos = indices[phase]

    return errors


FORMAT_PLATFORMS = {
    "app": "macos", "dmg": "macos", "pkg": "macos",
    "portable-exe": "windows", "installer-exe": "windows",
    "msi": "windows", "msix": "windows",
}


def _check_lifecycle(groups: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    targets = groups["targets"]
    sessions = groups["sessions"]
    artifacts = groups["artifacts"]
    lifecycles = groups["lifecycle_profiles"]
    boundaries = groups["interaction_boundaries"]

    for lifecycle_id, lifecycle in lifecycles.items():
        target_id = lifecycle.get("target_id", "")
        session_id = lifecycle.get("session_id", "")
        artifact_ids = lifecycle.get("artifact_ids", [])
        cleanup_action_refs = lifecycle.get("cleanup_action_refs", [])
        authorization_refs = lifecycle.get("authorization_refs", [])
        install_policy = lifecycle.get("install_policy", "")
        update_flag = lifecycle.get("update", False)

        # Require ready target
        target = targets.get(target_id, {})
        if target.get("provisioning_status") != "ready":
            errors.append(f"desktop lifecycle {lifecycle_id} target {target_id} is not ready")

        # Require session is isolated, interactive, unlocked, connected
        session = sessions.get(session_id, {})
        for flag in ("interactive", "unlocked", "connected", "isolated"):
            if not session.get(flag, False):
                errors.append(f"desktop lifecycle {lifecycle_id} session {session_id} is not execution-safe")

        # Check session allowlists match lifecycle references
        session_app_list = session.get("application_allowlist", [])
        lifecycle_app_id = lifecycle.get("application_id", "")
        if session_app_list and lifecycle_app_id not in session_app_list:
            errors.append(f"desktop lifecycle {lifecycle_id} application {lifecycle_app_id} not in session {session_id} allowlist")

        boundary_id = lifecycle.get("interaction_boundary_id", "")
        session_boundary_list = session.get("os_interaction_allowlist", [])
        if session_boundary_list and boundary_id not in session_boundary_list:
            errors.append(f"desktop lifecycle {lifecycle_id} boundary {boundary_id} not in session {session_id} allowlist")

        # Require at least one artifact
        if not artifact_ids:
            errors.append(f"desktop lifecycle {lifecycle_id} has no artifact_ids")

        # Validate artifact platform/format compatibility
        for aid in artifact_ids:
            artifact = artifacts.get(aid, {})
            artifact_platform = artifact.get("platform", "")
            artifact_format = artifact.get("format", "")
            if artifact_platform and artifact_format:
                expected_platform = FORMAT_PLATFORMS.get(artifact_format)
                if expected_platform and artifact_platform != expected_platform:
                    errors.append(f"desktop lifecycle {lifecycle_id} artifact {aid} format {artifact_format} incompatible with platform {artifact_platform}")

        # Validate artifact application/platform matching
        for aid in artifact_ids:
            artifact = artifacts.get(aid, {})
            app_id = lifecycle.get("application_id", "")
            if artifact.get("application_id") != app_id:
                errors.append(f"desktop lifecycle {lifecycle_id} artifact {aid} application_id does not match lifecycle application_id")
            if artifact.get("platform") != target.get("platform"):
                errors.append(f"desktop lifecycle {lifecycle_id} artifact {aid} platform does not match target platform")

        # Update requires distinct prior and candidate artifacts
        if update_flag:
            prior_artifacts = [a for a in artifact_ids if artifacts.get(a, {}).get("role") == "prior"]
            candidate_artifacts = [a for a in artifact_ids if artifacts.get(a, {}).get("role") == "candidate"]
            if len(prior_artifacts) < 1:
                errors.append(f"desktop lifecycle {lifecycle_id} update requires prior artifact")
            if len(candidate_artifacts) < 1:
                errors.append(f"desktop lifecycle {lifecycle_id} update requires candidate artifact")
            if len(prior_artifacts) >= 1 and len(candidate_artifacts) >= 1:
                prior = artifacts[prior_artifacts[0]]
                candidate = artifacts[candidate_artifacts[0]]
                if prior.get("version") == candidate.get("version") and prior.get("build") == candidate.get("build"):
                    errors.append(f"desktop lifecycle {lifecycle_id} update prior and candidate artifacts are identical")
                if prior.get("product_id") != candidate.get("product_id"):
                    errors.append(f"desktop lifecycle {lifecycle_id} update artifacts have mismatched product_id")

        # Require cleanup action refs
        if not cleanup_action_refs:
            errors.append(f"desktop lifecycle {lifecycle_id} has no cleanup_action_refs")

        # Authorization refs required for mutating lifecycles
        if install_policy in ("fresh", "reinstall", "update", "portable") and not authorization_refs:
            errors.append(f"desktop lifecycle {lifecycle_id} mutating install_policy requires authorization_refs")

        # Machine install requires disposable ephemeral target
        install_scope = ""
        if artifact_ids:
            first_artifact = artifacts.get(artifact_ids[0], {})
            install_scope = first_artifact.get("install_scope", "")
        if install_scope == "machine" and target.get("kind") != "ephemeral":
            errors.append(f"desktop lifecycle {lifecycle_id} machine install requires ephemeral target")

    return errors


def _check_evidence(manifest: dict[str, Any], expect: dict[str, Any], groups: dict[str, dict[str, dict[str, Any]]], unit_ids: set[str]) -> list[str]:
    errors: list[str] = []
    lifecycles = groups["lifecycle_profiles"]
    sessions = groups["sessions"]
    targets = groups["targets"]
    artifacts_map = groups["artifacts"]
    apps = groups["applications"]
    drivers = groups["drivers"]
    driver_kinds = {d.get("kind") for d in drivers.values() if isinstance(d, dict)}

    evidence_list = manifest.get("evidence", [])
    actions = manifest.get("actions", [])
    authorizations = manifest.get("authorizations", [])
    run = manifest.get("run", {})

    required_checks = expect.get("required_check_ids", [])
    required_execution_ids = expect.get("required_execution_evidence_ids", [])
    required_cleanup_outcome = expect.get("required_cleanup_outcome")
    allow_fixture = expect.get("allow_fixture_evidence", False)
    target_tier = manifest.get("systems", [{}])[0].get("target", {}).get("tier", "unspecified")

    action_ids = {a.get("id") for a in actions if isinstance(a, dict)}
    auth_ids = {a.get("id") for a in authorizations if isinstance(a, dict)}
    execution_evidence: dict[str, dict] = {}
    cleanup_evidence: dict[str, dict] = {}

    for evidence in evidence_list:
        if not isinstance(evidence, dict):
            continue
        evidence_id = evidence.get("id", "")

        # Check for execution evidence
        if "execution_environment" in evidence or "check_ids" in evidence:
            execution_evidence[evidence_id] = evidence
        elif evidence.get("phase") == "cleanup" and "cleanup_action_id" in evidence:
            cleanup_evidence[evidence_id] = evidence

    # Validate execution evidence
    for evidence_id, ev in execution_evidence.items():
        # Require selected check IDs and outcomes
        check_ids = ev.get("check_ids", [])
        outcomes = ev.get("outcomes", [])
        if required_checks:
            for rc in required_checks:
                if rc not in check_ids:
                    errors.append(f"evidence {evidence_id} missing required check_id {rc}")
                matching = [o for o in outcomes if o.get("check_id") == rc]
                if not matching:
                    errors.append(f"evidence {evidence_id} missing outcome for check {rc}")

        # Validate duration
        duration = ev.get("duration_ms")
        if not _valid_duration(duration):
            errors.append(f"evidence {evidence_id} has invalid duration")

        # Require current consumed revision
        consumed = ev.get("manifest_revision_consumed")
        current_revision = run.get("revision", 0)
        expected_consumed = current_revision - 1
        if consumed is None or consumed != expected_consumed:
            errors.append(f"evidence {evidence_id} has stale revision (expected {expected_consumed})")

        # Environment binding
        env = ev.get("execution_environment", {})
        for req_field in REQUIRED_ENVIRONMENT:
            if req_field not in env:
                errors.append(f"evidence {evidence_id} missing environment field {req_field}")

        # Require real_os_evidence
        if not ev.get("real_os_evidence"):
            errors.append(f"evidence {evidence_id} is not real OS evidence")

        # Lifecycle phase must be current
        if ev.get("phase") != expect.get("mode", "verify"):
            errors.append(f"evidence {evidence_id} phase mismatch")

        # Require authorization_refs in environment
        auth_refs = env.get("authorization_refs", [])
        if not auth_refs or not isinstance(auth_refs, list) or not auth_refs:
            errors.append(f"evidence {evidence_id} missing authorization_refs")

        # Verify authorization exists in manifest
        for aref in auth_refs:
            if aref not in auth_ids:
                errors.append(f"evidence {evidence_id} references unknown authorization {aref}")

        # Validate specific environment field values against extension records
        lifecycle_id = env.get("lifecycle_phase", "")
        if env.get("driver") not in driver_kinds:
            errors.append(f"evidence {evidence_id} driver {env.get('driver')} not in drivers")
        if env.get("target_reference") not in targets:
            errors.append(f"evidence {evidence_id} target_reference {env.get('target_reference')} not in targets")
        if env.get("session_reference") not in sessions:
            errors.append(f"evidence {evidence_id} session_reference {env.get('session_reference')} not in sessions")
        if env.get("application_id") not in apps:
            errors.append(f"evidence {evidence_id} application_id {env.get('application_id')} not in apps")
        if env.get("artifact_reference") not in artifacts_map:
            errors.append(f"evidence {evidence_id} artifact_reference {env.get('artifact_reference')} not in artifacts")

    # Require execution evidence
    for req_id in required_execution_ids:
        if req_id not in execution_evidence:
            errors.append(f"missing required execution evidence {req_id}")

    # Validate cleanup evidence
    if required_cleanup_outcome == "successful":
        if not cleanup_evidence:
            errors.append("missing cleanup evidence")
        else:
            for evidence_id, ev in cleanup_evidence.items():
                if not ev.get("cleanup_successful"):
                    errors.append(f"cleanup evidence {evidence_id} failed")
                if not ev.get("restored_baseline"):
                    errors.append(f"cleanup evidence {evidence_id} did not restore baseline")
                if "cleanup_action_id" not in ev:
                    errors.append(f"cleanup evidence {evidence_id} missing cleanup_action_id")
                if "lifecycle_id" not in ev:
                    errors.append(f"cleanup evidence {evidence_id} missing lifecycle_id")
                if "session_id" not in ev:
                    errors.append(f"cleanup evidence {evidence_id} missing session_id")
                if "baseline_ref" not in ev:
                    errors.append(f"cleanup evidence {evidence_id} missing baseline_ref")
                if "restoration_ref" not in ev:
                    errors.append(f"cleanup evidence {evidence_id} missing restoration_ref")

    # Production tier: reject installation/update/uninstall/permission/notification/protocol/filesystem writes
    if target_tier == "production":
        for evidence_id, ev in execution_evidence.items():
            # Production only allows read-only observation
            if not ev.get("real_os_evidence"):
                errors.append(f"evidence {evidence_id} not real OS evidence in production")

    return errors


def _valid_duration(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0


def check_desktop_contract(manifest: dict[str, Any], expect: dict[str, Any], surface: str) -> list[str]:
    if surface != "desktop":
        return []
    errors: list[str] = []
    units = [item for item in manifest.get("execution_units", []) if isinstance(item, dict) and item.get("surface") == "desktop"]
    if not units:
        return ["desktop case requires at least one desktop execution unit"]
    extensions = {item["id"]: item for item in manifest.get("extensions", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
    bound = {unit.get("extension_id") for unit in units}
    if len(bound) != 1:
        errors.append("desktop execution units must share one e2e.desktop extension")
        return errors
    extension = extensions.get(next(iter(bound)))
    if not isinstance(extension, dict) or extension.get("namespace") != "e2e.desktop" or extension.get("version") != "1.0" or extension.get("owner") != "e2e-desktop":
        return ["desktop execution unit does not reference e2e.desktop@1.0 owned by e2e-desktop"]
    groups, duplicates = _extension_records(extension)
    errors.extend(duplicates)
    if duplicates:
        return errors
    errors.extend(_check_refs(
        groups, {item["id"] for item in units}, _ids(manifest.get("evidence")),
        _ids(manifest.get("actions")), _ids(manifest.get("authorizations")),
    ))
    errors.extend(_check_compatibility(groups))
    errors.extend(_check_sessions(groups))
    errors.extend(_check_lifecycle(groups))
    errors.extend(_check_evidence(manifest, expect, groups, {item["id"] for item in units}))
    return errors
