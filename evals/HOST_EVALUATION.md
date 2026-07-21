# Authorized host evaluation

Codex and Claude host evaluations may consume paid model usage. Do not run any command below unless an authorized reviewer has explicitly approved that individual evaluation session.

Before approval is used, authenticate freshly to the selected host CLI. Use only the disposable fixture workspace created by the harness: do not supply production credentials, production tokens, or access to production systems. If `--keep-results` is used, review the retained transcript for secret leakage before sharing, archiving, or committing anything from `evals/results/`.

Each command creates a fresh fixture copy and installs both portable skills into the host's project-local skill directory. The acceptance status comes from the deterministic evaluator, not host output.

## Codex

```sh
python3 evals/run_host_eval.py --host codex --case greenfield-source --keep-results
python3 evals/run_host_eval.py --host codex --case live-assisted-generation --keep-results
python3 evals/run_host_eval.py --host codex --case existing-playwright --keep-results
python3 evals/run_host_eval.py --host codex --case unsupported-cypress --keep-results
python3 evals/run_host_eval.py --host codex --case conflicting-evidence --keep-results
python3 evals/run_host_eval.py --host codex --case verify-pass --keep-results
python3 evals/run_host_eval.py --host codex --case repair-test-defect --keep-results
python3 evals/run_host_eval.py --host codex --case product-defect-handoff --keep-results
python3 evals/run_host_eval.py --host codex --case missing-credentials --keep-results
python3 evals/run_host_eval.py --host codex --case auto-budget --keep-results
```

## Claude Code

```sh
python3 evals/run_host_eval.py --host claude --case greenfield-source --keep-results
python3 evals/run_host_eval.py --host claude --case live-assisted-generation --keep-results
python3 evals/run_host_eval.py --host claude --case existing-playwright --keep-results
python3 evals/run_host_eval.py --host claude --case unsupported-cypress --keep-results
python3 evals/run_host_eval.py --host claude --case conflicting-evidence --keep-results
python3 evals/run_host_eval.py --host claude --case verify-pass --keep-results
python3 evals/run_host_eval.py --host claude --case repair-test-defect --keep-results
python3 evals/run_host_eval.py --host claude --case product-defect-handoff --keep-results
python3 evals/run_host_eval.py --host claude --case missing-credentials --keep-results
python3 evals/run_host_eval.py --host claude --case auto-budget --keep-results
```

Without `--keep-results`, the workspace and transcript stay in a temporary directory and are removed when the evaluation ends.
