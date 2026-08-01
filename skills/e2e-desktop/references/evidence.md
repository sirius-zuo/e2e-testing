# Desktop evidence

Passing evidence binds the current run/revision, selected check, execution unit, application, driver, OS, target, dedicated session, artifact, lifecycle phase, authorization, attempt, observable outcome, and timestamps. Fixture evidence requires explicit evaluator opt-in. Mocked OS behavior is never passing E2E evidence.

Supported sanitized artifacts are application-window screenshots/video, public accessibility snapshots, normalized driver results, lifecycle/window events, application/driver/installer/crash logs, scoped notification/protocol/filesystem observations, and cleanup/restoration results. Exclude unrelated desktop content, identities, paths, credentials, and personal data.

Cleanup evidence binds the exact cleanup action, lifecycle, session, baseline, restoration, current revision/phase, and successful restoration. Stale, cross-session, incomplete, conflicting, or later-masked cleanup evidence is inconclusive or `cleanup-failure`.

Required environment vocabulary: `driver`, `driver_version`, `adapter_version`, `backend_version`, `platform`, `os_version`, `target_reference`, `target_kind`, `target_tier`, `session_reference`, `session_kind`, `session_isolated`, `application_id`, `application_kind`, `artifact_reference`, `artifact_format`, `lifecycle_phase`, `authorization_refs`, `evidence_origin`
