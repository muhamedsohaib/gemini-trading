# Task 12 Red-Gate Evidence

- Scope: safe read-only `research backtest`, `research replay`, and `research verify` CLI.
- Tests added before implementation: parser requirements, runtime-policy ordering, safe error output, deterministic end-to-end backtest/replay/verify, diagnostic non-promotion, and live-mode rejection.
- Test head after repository-pinned formatting: `63511243e0e492e400303f52ded6cc2a44bbe874`.
- Expected red outcome: collection or dispatch failure because `gemini_trading.cli.research` and the `research` command are not implemented.
- Safety boundary: no credentials, private endpoints, network replay, paper broker, demo adapter, or exchange submission.
