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

Checkpoint CI run `29993614209` passed after Task 2 with 245 tests passed, one bounded public live smoke test intentionally skipped, and formatting, linting, strict typing, build, dependency audit, tracked-file policy, secret scan, and gitleaks all passing.

### Remaining limitations

This task provides only foundational errors and serialization. It does not yet simulate orders, calculate account transitions, or produce backtest results.

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

Checkpoint CI run `29993614209` passed with 245 tests passed and one intentional live-test skip. Two defects were preserved in the history and corrected: a Ruff control-flow finding and a pytest test-module filename collision.

### Remaining limitations

These are contracts only. Costs, liquidity, execution simulation, accounting transitions, engine orchestration, artifacts, replay, and verification remain unimplemented.

## Task 3 — Verified canonical dataset reader

### Goal

Load immutable Market Data Core datasets without network access and independently verify manifest encoding, content hashes, dataset identity, exact candle schema, chronology, completion, provider identity, and canonical byte encoding.

### Red evidence

- Commit: `2cef5476c029c498f78fb74a6bcb2381479575cd`
- GitHub Actions run: `29993908820`
- Result: failed as expected because `gemini_trading.research.dataset_reader` did not exist

### First green attempt and defect

- Implementation commit: `dd29ca47345dc49bb503fddf49c246f9c12ab69d`
- GitHub Actions run: `29994006856`
- Formatting, linting, strict typing, and gitleaks passed
- Pytest exposed that tampered canonical bytes were parsed before their stored hash was checked
- Observed error was `invalid candle fields` instead of the required canonical-content identity failure

### Remediation and green evidence

- Remediation commit: `f8f8475ffa85513ad1a5db0e462afd78ae782575`
- Focused diagnostic run: `29994232184` — 5 tests passed
- Complete CI run: `29994232051` — passed
- Content SHA-256 and dataset identity are now verified before any candle row is trusted or parsed
- Exact manifest and candle field sets are enforced
- Re-serialization must reproduce the persisted canonical bytes
- Existing completed-candle sequence validation is reused
- Storage, decoding, and parsing failures are converted to safe `DatasetVerificationError` messages without raw payloads or absolute paths

### Remaining limitations

The reader trusts only local immutable canonical storage in this milestone. It does not add a database adapter, order-book data, trade-level data, strategy logic, or exchange access.

## Task 4 — Simulation configuration and deterministic experiment identity

### Goal

Make every result-shaping execution assumption explicit, validated, canonically serialized, and linked to a stable experiment identity.

### Red evidence

- Commit: `29690213a2b24e98ab9e87315ad0080df08b523c`
- GitHub Actions run: `29994455913`
- Result: failed as expected because simulation configuration and identity modules did not exist

### Green implementation

Implemented:

- finite non-negative fees, spread, slippage, and latency assumptions;
- positive tick, step, quantity minimum, and notional minimum constraints;
- deterministic candle-volume participation bounded to `(0, 1]`;
- conservative official defaults for next-candle timing, strict-cross fills, BAR lifetime, and three-candle maximum lifetime;
- mandatory non-zero costs for promotable official evidence;
- automatic non-promotable status for diagnostic timing or fill policies;
- canonical simulation configuration bytes and SHA-256 linkage;
- canonical experiment manifest serialization with strategy configuration sorted by unique key;
- experiment identity as SHA-256 of canonical manifest bytes.

Complete CI run `29994857733` passed after exact formatter and import-order findings were applied. Formatting, linting, strict typing, tests, build, dependency audit, tracked-file policy, secret scan, and gitleaks all passed.

### Remaining limitations

Experiment identity records assumptions but does not yet execute orders, create fills, alter account state, calculate metrics, or publish research artifacts.
