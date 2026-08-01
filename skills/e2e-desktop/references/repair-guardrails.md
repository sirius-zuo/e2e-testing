# Desktop repair guardrails

The repair action must list exact allowed paths. Allowed changes are desktop E2E tests, desktop test configuration, fixtures, and dedicated test-support files.

Protected paths include application source, build/package/signing/notarization/publisher/certificate configuration, production configuration, OS settings and security, user profiles, provider administration, unrelated tests, and files outside the repository. Never weaken assertions, expected outcomes, cleanup, isolation, or authorization requirements.
