# Evaluation Fixtures

Each child directory is a minimal repository used by one or more behavioral cases. The host harness copies a fixture into an isolated temporary repository; agents never operate on the source fixture.

## Integrity baselines

Every fixture contains a source-controlled `.fixture-baseline.json`. It maps every other fixture file to its SHA-256 digest. These files are intentional test inputs, not caches or disposable generated output.

The evaluator uses the baseline to distinguish:

- **preserved** files, which must remain byte-identical;
- **created** files, which must not exist in the baseline;
- **changed** files, which must exist in the baseline and receive an intentional modification.

Tracking the baseline makes fixture changes explicit in code review and prevents a modified source fixture from silently changing the expected evaluation result.

## Changing a fixture

1. Change only the files required by the scenario.
2. Recalculate `.fixture-baseline.json` with sorted relative POSIX paths and lowercase SHA-256 digests.
3. Ensure the baseline contains every fixture file except itself.
4. Run:

   ```sh
   python3 -m unittest tests.test_evaluation_contracts.FixtureContractTests -v
   ```

5. Review the fixture and baseline together. An unexpected hash change is a test-contract change, not formatting noise.

## Fixture rules

- Keep fixtures minimal, deterministic, and dependency-light.
- Do not add credentials, tokens, production endpoints, retained transcripts, or generated `.e2e` run artifacts.
- Do not initialize nested Git repositories.
- Do not edit source fixtures during a behavioral run; use the harness-created copy.
