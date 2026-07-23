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

Green CI evidence will be appended after a stable implementation checkpoint completes GitHub Actions.

### Remaining limitations

This task provides only foundational errors and serialization. It does not yet load datasets, simulate orders, calculate account state, or produce backtest results.

## Task 2 — Immutable experiment, order, fill, and account contracts

### Goal

Establish immutable, strictly validated domain records for experiment identity, long-only market and limit orders, fills, account state, and ledger deltas.

### Red evidence

- Commit: `ddb0706b073af9780f278e4387f286d7d40d19e4`
- GitHub Actions run: `29991861979`
- Result: failed as expected while the new domain modules were absent
- No execution-capable or credential-bearing code was introduced

### Green implementation

Implemented:

- official and diagnostic timing/fill-policy enums;
- explicit `BUY` and `SELL_TO_CLOSE` sides with no short side;
- `MARKET` and `LIMIT` intents with exact price rules;
- bounded `IOC`, `BAR`, and `GTC` lifetimes;
- deterministic order lifecycle snapshots and remaining quantity;
- immutable fill records with exact notional reconciliation;
- non-negative long-only account state and exact ledger records;
- SHA-256, Git commit, Decimal, identifier, chronology, and status validation.

Green CI evidence will be appended after the checkpoint workflow completes.

### Remaining limitations

These are contracts only. Dataset loading, costs, liquidity, execution simulation, accounting transitions, engine orchestration, artifacts, replay, and verification remain unimplemented.
