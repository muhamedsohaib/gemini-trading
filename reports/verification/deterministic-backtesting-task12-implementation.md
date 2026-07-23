# Task 12 Implementation and Acceptance Evidence

## Implemented surface

- Safe read-only commands: `research backtest`, `research replay`, and `research verify`.
- Runtime policy loads before configuration, dataset, service, or stored-evidence access.
- Configuration parsing is strict and limited to the documented non-production scripted fixture schema.
- A clean exact Git commit is recorded as a result-shaping experiment input.
- Backtest artifacts are canonical, immutable, content-addressed, and safe to rerun only when byte-identical.
- Replay is provider-free and regenerates every canonical core artifact for byte comparison.
- Independent verification checks dataset integrity, experiment identity, simulation configuration, artifact hashes, result identity, accounting, metrics, referential integrity, and replay equivalence.
- Official next-candle and conservative-fill evidence may be promotable; diagnostic timing or fill assumptions are never promotable.
- CLI success and failure output is one compact canonical JSON object with no traceback text, environment dump, raw evidence, or absolute path disclosure.

## Gate remediation

The final gate sequence exposed and resolved only bounded implementation defects:

- Ruff rejected a lambda assignment and one unused import.
- Strict Pyright required an explicit return type on the nested clean-commit resolver.
- Pytest collection required repository-wide access to the shared research fixture helper.
- The safe internal-error test was aligned with the actual `cli.main` dispatch binding.

Temporary formatting, lint, typing, and pytest diagnostics were removed after use. No temporary workflow remains in the milestone diff.

## Verification evidence

- Clean full CI checkpoint: head `4e5b98a7d5723eb9b64f2ba74d071a6c14a87c47`, run `30020996929`.
- Focused deterministic acceptance: tested head `ae18706d79bb3a02069a138378e1b62d21cfcf67`, run `30021138715`.
- Focused result: 5 tests passed, covering safe CLI backtest, provider-free replay, independent verification, tamper detection, diagnostic non-promotion, and live-mode rejection.
- Detailed focused output: `reports/verification/deterministic-backtesting-task12-acceptance.md`.

A final evidence-only head must pass the complete CI gate before protected merge. The milestone remains open until the exact merged `main` commit is independently verified.

## Safety boundary

No credentials, private endpoints, paper broker, demo adapter, live exchange submission, leverage, futures, shorting, autonomous order authority, production strategy, or profitability claim was added.
