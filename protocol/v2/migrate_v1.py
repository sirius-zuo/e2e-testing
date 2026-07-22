"""Explicit lossless migration from Protocol 1 to Protocol 2."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from protocol.v1.e2e_protocol import validate_manifest as validate_v1_manifest
from protocol.v2.e2e_protocol import ProtocolError, new_manifest, validate_manifest, validate_v2_policy


STATUS_MAP = {
    "unsupported-framework": "capability-unavailable",
    "protocol-incompatible": "extension-incompatible",
}


def source_sha256(source: dict[str, Any]) -> str:
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def migrate_manifest(source: dict[str, Any]) -> dict[str, Any]:
    source_copy = copy.deepcopy(source)
    source_errors = validate_v1_manifest(source_copy)
    if source_errors:
        raise ValueError("invalid Protocol 1 manifest: " + "; ".join(source_errors))

    project = source_copy["project"]
    target = source_copy["target"]
    result = new_manifest(project["root"], mode=source_copy["mode"], autonomy=source_copy["autonomy"]["mode"], timestamp="1970-01-01T00:00:00Z")
    mapped_status = STATUS_MAP.get(source_copy["status"], source_copy["status"])
    result["run"] = {
        "id": source_copy["run_id"],
        "revision": source_copy["revision"],
        "mode": source_copy["mode"],
        "autonomy": copy.deepcopy(source_copy["autonomy"]),
        "status": mapped_status,
        "created_at": None,
        "updated_at": None,
        "attempt_budget": copy.deepcopy(source_copy["attempt_budget"]),
    }

    interface = {
        "id": "interface-web-primary",
        "kind": "web",
        "endpoint_ref": target.get("base_url_ref"),
        "evidence_ids": [],
    }
    result["systems"] = [{
        "id": "system-primary",
        "project_root": project["root"],
        "primary_surface": "web",
        "boundary": {
            "status": "needs-clarification",
            "actors": [],
            "public_interfaces": [interface],
            "evidence_ids": [],
        },
        "target": {
            "tier": target["tier"],
            "endpoint_refs": [] if target.get("base_url_ref") is None else [target["base_url_ref"]],
            "credential_refs": [] if target.get("credentials_ref") is None else [target["credentials_ref"]],
            "mutation_policy": {"namespace_ref": None, "allowed_classes": []},
        },
    }]
    result["journeys"] = [
        {**copy.deepcopy(item), "system_id": "system-primary"}
        for item in source_copy["journeys"]
    ]
    result["execution_units"] = [{
        "id": "execution-web-primary",
        "system_id": "system-primary",
        "surface": "web",
        "capability": "e2e-web",
        "extension_id": "extension-web-primary",
        "status": mapped_status,
    }]
    result["checks"] = [
        {**copy.deepcopy(item), "execution_unit_id": "execution-web-primary"}
        for item in source_copy["tests"]
    ]
    result["evidence"] = copy.deepcopy(source_copy["evidence"])
    result["actions"] = copy.deepcopy(source_copy["next_actions"])
    for action in result["actions"]:
        if action.get("capability") == "e2e-web-playwright":
            action["capability"] = "e2e-web"
    result["handoffs"] = copy.deepcopy(source_copy["handoffs"])
    for handoff in result["handoffs"]:
        resume = handoff.get("resume")
        if isinstance(resume, dict) and isinstance(resume.get("command"), str):
            resume["command"] = resume["command"].replace("e2e-web-playwright", "e2e-web")
    result["authorizations"] = copy.deepcopy(source_copy["authorizations"])
    result["attempts"] = copy.deepcopy(source_copy["attempt_history"])
    digest = source_sha256(source_copy)
    existing_evidence_ids = {item.get("id") for item in result["evidence"] if isinstance(item, dict)}
    evidence_id = f"evidence-migration-protocol1-{digest}"
    counter = 2
    while evidence_id in existing_evidence_ids:
        evidence_id = f"evidence-migration-protocol1-{digest}-{counter}"
        counter += 1
    result["evidence"].append({
        "id": evidence_id,
        "kind": "protocol-migration",
        "source_protocol": "1.0",
        "source_revision": source_copy["revision"],
        "source_sha256": digest,
        "archive_extension_id": "extension-protocol1-archive",
    })
    result["extensions"] = [
        {
            "id": "extension-web-primary",
            "namespace": "e2e.web",
            "version": "1.0",
            "owner": "e2e-web",
            "data": {
                "driver": project.get("framework"),
                "project": copy.deepcopy(project),
                "target": copy.deepcopy(target),
            },
        },
        {
            "id": "extension-protocol1-archive",
            "namespace": "e2e.protocol1.archive",
            "version": "1.0",
            "owner": "e2e-testing",
            "data": {
                "source_sha256": digest,
                "source_manifest": source_copy,
                "status_translation": {"source": source_copy["status"], "target": mapped_status},
                "capability_translation": {"source": "e2e-web-playwright", "target": "e2e-web"},
                "conflicts": copy.deepcopy(source_copy["conflicts"]),
            },
        },
    ]
    errors = validate_manifest(result) + validate_v2_policy(result)
    if errors:
        raise ProtocolError("invalid migrated manifest: " + "; ".join(errors))
    return result
