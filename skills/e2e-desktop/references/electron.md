# Electron profile

WebdriverIO Electron is the first-class Electron adapter on macOS and Windows. Preserve repository-native WebdriverIO configuration, packaged application discovery, launch arguments, renderer locators, Electron API access, and multi-window conventions.

Preserve existing Playwright Electron as experimental and capability-gated; never migrate it automatically. Electron API mocks may remain lower-level tests, but mocked dialogs, permissions, notifications, filesystem results, protocol handlers, or other native APIs cannot satisfy E2E evidence. Real OS behavior must be observed inside the dedicated session.
