# Desktop failure classification

Use `needs-clarification` for unresolved boundaries; `authorization-required` for missing exact approval; `capability-unavailable` for unsupported driver/OS/session/lifecycle; `extension-incompatible` for unsupported typed state; `environment` for session/driver/installer/target/signing infrastructure failure; `test-defect` for high-confidence test/config/fixture faults; `product-defect` for externally observable application violations; `inconclusive` for stale, mocked, conflicting, or incomplete evidence; and `cleanup-failure` when restoration is not proven.

Retry only classified transient environment or test failures within budget. Never blindly retry install/uninstall, update, permissions, protocol registration, destructive setup, or external side effects. Preserve every attempt and its evidence.
