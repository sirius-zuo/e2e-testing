# Desktop safety

Live execution requires a dedicated OS user session or ephemeral VM that is interactive, unlocked, connected, isolated, bounded, and explicitly selected. Refuse general-purpose, shared, locked, disconnected, expired, or unbounded sessions.

Control only the declared application, owned child processes, allowlisted windows and OS dialogs, scoped permissions, notifications, protocol schemes, filesystem roots, and one explicitly declared clipboard operation. Never use desktop-root discovery, arbitrary window control, global keyboard capture, credential-store access, unbounded shell/PowerShell/AppleScript, registry exploration, or unrelated filesystem access.

Credentials are runtime references only. Production is explicit read-only observation in a dedicated session; installation, update, uninstall, permissions, notifications, protocols, filesystem writes, clipboard mutation, test-data mutation, and external side effects are categorically prohibited.

Stop immediately on session drift, unexpected writes, unrelated window/process control, credential exposure, personal-data exposure, or unexplained OS state.
