# Host Evaluation Guide

## Codex

### Mobile cases

```bash
python3 evals/run_host_eval.py --host codex --case mobile-generate-appium
python3 evals/run_host_eval.py --host codex --case mobile-generate-maestro
python3 evals/run_host_eval.py --host codex --case mobile-verify-lifecycle
python3 evals/run_host_eval.py --host codex --case mobile-production-refusal
```

## Claude Code

### Mobile cases

```bash
python3 evals/run_host_eval.py --host claude --case mobile-generate-appium
python3 evals/run_host_eval.py --host claude --case mobile-generate-maestro
python3 evals/run_host_eval.py --host claude --case mobile-verify-lifecycle
python3 evals/run_host_eval.py --host claude --case mobile-production-refusal
```

## Authorization Warning

Paid Codex/Claude host evaluations require explicit reviewer authorization.
Do not run paid sessions without authorization.
