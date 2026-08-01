# Desktop lifecycle

Validate target, session, driver, application, artifact hash/trust, install scope, authorizations, and baseline envelope. Then perform only the declared phases: install/select, launch, activate, minimize/restore, reset, permissions, filesystem/clipboard, notifications/protocol handlers, selected checks, cleanup, uninstall when declared, restoration, and teardown.

Reset names every affected state class. Machine installation requires a disposable ephemeral target and exact authorization. Update requires distinct prior and candidate artifacts with matching product identity and is not automatically retried.

Teardown ends driver sessions, application-owned processes, helpers, installers, and temporary services in dependency order. It restores the baseline envelope and releases the session. A failed execution or cleanup remains durable even when a later attempt passes.
