# Deterministic Backtesting Step Verification

## Required completion sequence

The milestone is complete only after every stage below is observed and recorded.

1. **Focused red evidence**
   - Add tests before the safe research CLI behavior.
   - Record formatter, lint, typing, collection, or behavior failures honestly; do not relabel a gate failure as a behavioral failure.
2. **Focused green evidence**
   - Run the CLI unit tests, end-to-end backtest/replay/verify acceptance test, provider-free replay integration test, verification tests, and live-mode rejection.
3. **Complete checkpoint**
   - Run Ruff formatting and lint, Pyright strict typing, the complete pytest suite, package build, dependency audit, tracked-file policy, repository secret scan, and Gitleaks.
4. **Exact pull-request-head verification**
   - Record the exact branch head SHA and GitHub Actions run.
   - Require both `quality` and `gitleaks` to pass on that exact head.
   - Review the cumulative diff for scope expansion, generated data, temporary diagnostics, secrets, and live-capable behavior.
5. **Protected merge**
   - Merge only through the protected pull request after required checks pass.
6. **Exact merged-main verification**
   - Record the exact merged `main` SHA.
   - Require the complete CI checkpoint on that SHA.
   - Confirm the deterministic research CLI, provider-free replay, and independent verification remain present on `main`.
7. **Milestone closure**
   - Add exact merged-main evidence to Issue #12.
   - Close Issue #12 only after verification.
   - Open the next design gate for Candidate Multi-Model Strategy v0.1 without implementing strategy logic in this milestone.

## Exact command checkpoint

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
```

Repository CI additionally validates tracked-file policy, scans tracked files for secrets, and runs Gitleaks.

The bounded public Binance smoke test remains disabled unless `GEMINI_TRADING_RUN_LIVE_API_TESTS=1` is explicitly set. It is not required to establish deterministic engine correctness and does not involve private credentials or order submission.

## Acceptance claims permitted

- The deterministic research engine reproduces identical content-addressed evidence for identical verified inputs.
- Provider-free replay and independent verification detect missing, malformed, tampered, or commit-mismatched evidence.
- Official evidence is next-candle, conservative, cost-bearing, and deterministic.
- Diagnostic policies are non-promotable.
- The CLI is read-only with respect to exchange execution and rejects live mode.

## Claims not permitted

- The fixture strategy is profitable.
- Backtest performance predicts future performance.
- The engine models queue position, intrabar path, hidden liquidity, or market impact exactly.
- The repository is ready for paper brokerage, demo trading, live trading, or real capital.
- The assistant can authorize real-capital deployment. Human authorization remains mandatory.
