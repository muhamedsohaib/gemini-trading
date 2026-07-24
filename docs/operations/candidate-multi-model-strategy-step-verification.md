# Candidate Multi-Model Strategy v0.1 Step Verification

## Required completion sequence

The milestone is complete only after every stage below is observed, reviewed, and recorded.

1. **Task-level RED evidence**
   - Add exact tests before each implementation boundary.
   - Preserve the real failure category: formatter, lint, typing, collection, behavior, missing evidence, or safety rejection.
2. **Task-level GREEN evidence**
   - Run focused tests and strict Pyright after every implementation task.
   - Keep temporary diagnostic workflows out of the final clean branch head.
3. **Documentation acceptance**
   - Require the operations document to state the `RESEARCH_ONLY` boundary, BTC/USDT 4h scope, seven-year historical requirement, sealed 18-month final test, all three strategy commands, valid rejection outcome, and profitability limitation.
4. **Diagnostic end-to-end acceptance**
   - Build a deterministic synthetic canonical BTCUSDT H4 dataset.
   - Exercise point-in-time features, cost-aware labels, chronological splits, both model families, calibration, regimes, arbitration, candidate and baseline simulation, immutable artifacts, provider-free replay, independent verification, tamper rejection, and unsafe-mode rejection.
   - Require `INCONCLUSIVE`; synthetic evidence must never claim edge.
5. **Deterministic repetition**
   - Run the focused end-to-end acceptance twice.
   - Require identical study ID, study result ID, and core artifact hashes.
6. **Complete quality and security checkpoint**
   - Run frozen dependency sync, Ruff formatting and lint, strict Pyright, the complete pytest suite, package build, dependency audit, pre-commit, tracked-file policy, repository secret scan, and Gitleaks.
7. **Exact pull-request-head verification**
   - Record the exact PR head SHA.
   - Require ordinary CI and focused deterministic Candidate acceptance on that exact SHA.
   - Review failed gates, limitations, cumulative scope, temporary files, generated evidence, secrets, and any live-capable behavior.
8. **Independent advisory review**
   - Review whether the evidence supports only the recorded classification.
   - Confirm that missing or inconclusive evidence fails closed and that no profitability or execution claim exceeds the artifacts.
9. **Protected merge**
   - Merge only through the protected pull request after all required checks pass.
10. **Exact merged-main verification**
    - Record the merged `main` SHA.
    - Run a purpose-built verification pinned to that SHA.
    - Confirm CLI evaluation, replay, verification, documentation, immutable evidence, and safety boundaries remain present.
11. **Issue closure**
    - Add exact merged-main evidence to Issue #16.
    - Close Issue #16 only after post-merge verification.

## Exact command checkpoint

```bash
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
uv run pre-commit run --all-files
git diff --check
git status --short
```

Repository CI additionally validates tracked-file policy, scans tracked files for secrets, and runs Gitleaks.

## Deterministic Candidate acceptance

```bash
export GEMINI_TRADING_MODE=research
uv run pytest tests/acceptance/test_candidate_strategy_end_to_end.py -v
uv run pytest tests/acceptance/test_candidate_strategy_end_to_end.py -v
```

Both executions must report identical content identities. A test that merely passes twice without comparing identities is insufficient.

## Evidence required in the final report

- exact implementation commit and merged-main commit;
- dependency-lock SHA-256;
- complete and focused test counts;
- deterministic acceptance study and result identities;
- replay and verification receipts;
- every mandatory promotion gate with pass, fail, or not-evaluated status;
- recorded failed folds, controls, and rejected experiments;
- whether a real seven-year historical run occurred;
- limitations and final classification;
- explicit confirmation that no broker, demo, live, credentials, leverage, futures, shorting, portfolio allocation, or capital authority was introduced.

## Acceptance claims permitted

- The Candidate implementation is deterministic for identical verified inputs and exact code.
- Point-in-time, chronology, cost, final-test-seal, immutable-artifact, replay, and verification boundaries are tested.
- Synthetic end-to-end evidence is `INCONCLUSIVE` and verifies architecture only.
- Rejection, failed gates, and inconclusive classification are valid outcomes.
- Provider-free replay and independent verification detect missing, malformed, tampered, incomplete, or commit-mismatched evidence.

## Claims not permitted

- Synthetic or diagnostic evidence establishes trading edge.
- A historical pass guarantees durable profitability or future returns.
- OHLCV candles exactly model intrabar path, bid/ask history, queue priority, hidden liquidity, adverse selection, or market impact.
- The Candidate is approved for paper brokerage, demo trading, live trading, or real capital.
- The assistant can authorize deployment or capital allocation. Separate explicit human authorization remains mandatory.
