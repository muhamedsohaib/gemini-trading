# Deterministic Backtesting Progress Evidence

## Scope

Task-by-task verification evidence for Issue #12 and PR #13. This milestone remains research only and introduces no exchange submission capability.

## Task 1 — Research failure taxonomy and canonical serialization

### Goal

Establish one safe research-error base and deterministic UTF-8 JSON/JSONL encoding with exact Decimal and UTC formatting.

### Red evidence

- Commit: `b1ec73585d6238465c2f9fab8df609176607dfdc`
- GitHub Actions run: `29991509563`
- `ruff format`: passed
- `ruff check`: passed
- `pyright`: failed as expected because `gemini_trading.research.errors` did not yet exist
- `pytest` and later quality steps: skipped after the expected static failure
- `gitleaks`: passed

### Green implementation

Implemented:

- `ResearchError` and typed safe subclasses;
- exact finite Decimal formatting;
- strict UTC-aware millisecond timestamp formatting;
- sorted compact UTF-8 JSON with one terminal newline;
- ordered deterministic JSONL serialization.

Green CI evidence will be appended after the implementation head completes GitHub Actions.

### Remaining limitations

This task provides only foundational errors and serialization. It does not yet load datasets, simulate orders, calculate account state, or produce backtest results.
