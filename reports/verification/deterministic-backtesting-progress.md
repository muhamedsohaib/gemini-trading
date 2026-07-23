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

## Task 5 — Conservative precision, cost, and liquidity primitives

### Goal

Provide pure deterministic Decimal primitives for adverse tick and quantity rounding, explicit fee/spread/slippage accounting, and capped candle-volume participation.

### Recovered implementation evidence

Implemented:

- quantity-step rounding strictly downward;
- adverse price-tick rounding by order side;
- deterministic market fill price, notional, fee, half-spread, and slippage components;
- finite positive input validation before arithmetic;
- candle-volume participation caps that never become negative or exceed the configured allocation;
- property tests for deterministic liquidity behavior.

The interrupted browser session was recovered after Task 5 had already been implemented. Its individual red and green commits remain preserved in PR #13 history. The complete Task 5 surface was reverified together with Task 6 at exact head `79ad32a51e3e135474e682158e78de042d997dc1` in CI run `29999431967`, where formatting, linting, strict typing, the full test suite, build, dependency audit, tracked-file policy, secret scan, and gitleaks all passed.

### Remaining limitations

These primitives operate on OHLCV candles. They cannot reconstruct queue position, exact intrabar path, trade ordering, or true market impact.

## Task 6 — Deterministic market and limit fill simulator

### Goal

Evaluate market and limit orders against completed candles using official conservative assumptions, explicit diagnostic separation, liquidity-capped partial fills, affordability, precision, minimums, and deterministic identities.

### Implementation and observed failures

- Implementation commit: `bec6dce819253ab6e855299d898ee2752b088bc8`
- Initial CI run: `29995586778`
- Result: logic reached the checkpoint, but Ruff formatting failed
- Formatter diagnostic run: `29995586792`
- Exact formatter output identified only `fills.py` and `test_fills.py`
- Follow-up CI run: `29999210027`
- Formatting passed; Ruff lint then exposed one first-party import-order defect
- Ruff diagnostic run: `29999314117`
- No runtime logic defect was implicated

### Green evidence

- Final recovered checkpoint head: `79ad32a51e3e135474e682158e78de042d997dc1`
- Complete CI run: `29999431967` — passed
- Temporary format and lint diagnostic workflows were removed before the green checkpoint
- `quality` and `gitleaks` both passed
- All quality steps passed, including the complete test suite, build, dependency audit, tracked-file policy, and secret scan

Verified behavior includes:

- official strict-cross limit fills and separately labelled optimistic touch diagnostics;
- next-eligible-candle market reference pricing;
- maker versus taker fees;
- adverse spread, slippage, and tick rounding;
- cash-, position-, precision-, minimum-, and liquidity-capped fill quantity;
- deterministic partial-fill state and fill identity;
- no network, system clock, randomness, credential, or exchange submission access.

### Remaining limitations

The simulator does not yet apply fills to authoritative account state, orchestrate a strategy, publish artifacts, or independently replay a complete experiment.

## Task 7 — Account transitions, exact cost basis, and reconciliation

### Goal

Apply fills to immutable long-only account state, preserve exact cash and position conservation, mark equity and drawdown, and independently reconcile ledger balances.

### Red evidence

- Unit-test commit: `5a68e4138c1b68362ab57eb21a3df3d3b8ed2b0e`
- Property-test commit: `d97c24365276e018b19d75cc8e2ff0872d1878d1`
- Clean red-gate head: `a727734d70cd371561d31b659556cd050866acf7`
- GitHub Actions run: `30000040623`
- Formatting and linting passed
- Pyright failed as expected because `gemini_trading.research.accounting` did not yet exist
- Gitleaks passed

### First green attempt and defect

- Initial implementation commit: `287bf70224076760b7cb07667e5d1809c277a94e`
- Formatter diagnostic run: `30000178923`
- Full CI run after formatting: `30000283472`
- Static gates passed, but the accounting property test failed
- Focused diagnostic run: `30000354541`
- The failing generated case proved that storing only `average_entry_price` loses exact position cost basis when division repeats, such as a three-unit purchase
- No tolerance or approximate comparison was accepted because that would weaken exact financial reconciliation

### Remediation and green evidence

- Exact-cost-basis contract commit: `ceddfefeccb8e2d32aebb8c28d32bf847a2f5c75`
- Accounting remediation commit: `8e5dcdcbba53fe670a73ddba888b9d56ef35571b`
- Final checkpoint head: `8c1483f275f72a92002d70a1f3ce08190ac4b9fe`
- Complete CI run: `30000597295` — passed
- Temporary diagnostics were removed before the green checkpoint

Implemented and verified:

- exact buy cash reduction and cost-basis accumulation;
- exact full-close cost-basis release without repeated-Decimal drift;
- deterministic proportional basis release for partial closes while conserving the exact remainder;
- realized profit and loss including buy and sell fees;
- exact cumulative fees and simulated execution costs;
- non-negative cash and position enforcement;
- fill/order identity and active-order validation;
- mark-to-market equity, peak equity, and drawdown;
- unique fill identities, increasing ledger sequences, and terminal cash/position/fee reconciliation;
- deterministic property replay across generated valid round trips.

### Remaining limitations

The first slice remains one instrument and long-only. Ledger entries do not yet represent deposits, withdrawals, portfolio transfers, borrowing, funding, leverage, or multi-asset cost-basis allocation.
