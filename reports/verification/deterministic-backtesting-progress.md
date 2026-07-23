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

## Task 8 — Read-only strategy contract and non-production fixture

### Goal

Expose only the current completed candle, immutable account state, and active-order state to strategies while providing a deterministic scripted fixture that cannot be promoted as production logic.

### Red evidence

- Unit-test commit: `a45d954f1526c40e97386acb4ec62d2259f3c585`
- Regression-test commit: `9b7c884df4c7d982459c85159961311ed0dac799`
- GitHub Actions run: `30000923612`
- Formatting and linting passed
- Pyright failed as expected because `research.contracts` and `research.fixture_strategy` did not yet exist
- Gitleaks passed

### Green implementation

- Contract commit: `b2523a6bd651b108b5a284f15c04a2285da27c68`
- Fixture commit: `abd8f9668163ebf819e8b22569fa29b640b33952`
- Complete CI run: `30001013660` — passed

Implemented and verified:

- immutable `StrategyContext` with only candle index, one completed candle, account, and active orders;
- no future-candle iterator, provider, network, filesystem, or execution adapter exposure;
- strict rejection of incomplete candles and invalid indexes;
- immutable `StrategyDecision` records;
- read-only strategy identity and production-eligibility metadata;
- stable strategy configuration bytes independent of input ordering;
- scripted fixture returns predefined intents only at exact candle indexes;
- fixture is permanently marked `production_eligible=False`.

### Remaining limitations

The fixture contains no market hypothesis or profitability claim. It exists only to exercise engine behavior and is not the future candidate strategy.

## Task 9 — Chronological event-driven backtesting engine

### Goal

Process one verified candle stream exactly once in strict order, fill only eligible orders, enforce bounded order lifecycles, record immutable decisions, and reconcile the terminal account.

### Red evidence

- Unit-test commit: `e4e42df27c770cf23bae10bd4e60e8e32ce6eb42`
- Integration-test commit: `d4fbf4d651665443d089d6068a3eea9702389946`
- Duplicate-cycle regression commit: `24f0419f53101e7a797eb87c71349cd95edad4e0`
- Clean red-gate head: `2b49c5d202788d50b05a7b1075e0139fe7413caa`
- GitHub Actions run: `30001511744`
- Static checks stopped as expected because `research.engine` did not yet exist

### Implementation and observed failures

- Initial engine commit: `45b7865aa9481dc472438e628061244c3e9a59a5`
- Ruff diagnostic run: `30001720649`
- Pyright diagnostics: `30002016457`, `30002298814`, `30002493986`, and `30002714784`
- The failures were limited to one mechanical Ruff finding and strict-typing interactions at the runtime strategy-output boundary
- Runtime validation was not removed; it was isolated behind an object-typed checked helper and a justified cast after tuple validation
- Strategy protocol metadata was corrected to read-only properties

### Green evidence

- Final checkpoint head: `aec476b9462701422576303f9d4d4bbaa7b00a36`
- Complete CI run: `30002945113` — passed
- Temporary diagnostics were removed before the green checkpoint

Implemented and verified:

- completed, identity-matching candles processed exactly once in contiguous order;
- duplicate, reversed, skipped, mismatched, and post-finalization events fail closed;
- active orders evaluated before each strategy decision in deterministic order;
- one shared consumed-volume counter per candle;
- official next-candle eligibility and separately labelled same-close diagnostic handling;
- deterministic order IDs derived from experiment, decision, and intent identity;
- conflict, insufficient-position, precision, and minimum-order rejection records;
- IOC/BAR remainder cancellation and bounded GTC expiry;
- experiment-end cancellation of still-active orders;
- immutable decisions, orders, fills, ledger, account series, and terminal account evidence;
- terminal mark-to-market and exact accounting reconciliation.

### Remaining limitations

The engine is one-instrument and candle-based. It does not model order-book queues, asynchronous exchange acknowledgements, broker restarts, multi-asset concurrency, or live order submission.

## Task 10 — Deterministic metrics, artifacts, and result identity

### Goal

Derive exact metrics and flat-to-flat trades, serialize every core research artifact deterministically, assign a content-derived result identity, and persist byte-identical evidence immutably.

### Red evidence

- Metrics-test commit: `02b3e881cb82c92fed4412834c3a0691aaa2d9c4`
- Artifact-test commit: `e417576928f3e243bf7897d4dac6d9a55f658f73`
- Result-identity property-test commit: `f0317ba58371f9c412f5b2104bb5d6049ad70739`
- Clean red-gate head: `68d6d1b6a3985def0b1d74bab37734309fb2a306`
- GitHub Actions run: `30003493494`
- Formatting and linting passed
- Pyright failed as expected because `research.metrics` and `research.artifacts` did not yet exist
- Gitleaks passed

### Implementation and observed failures

- Metrics implementation: `6e689336332d92ab5ac3e84e542587d5cdc888d9`
- Artifact implementation: `c8e05d35b2bbabd722599c01e88804ffe33d3f6e`
- `.gitignore` correction: `0949b6b1f603ab75a97ea2dd80cdda992ab9e97f`
- Production formatter diagnostic run: `30003729325`
- Exact formatter output changed line wrapping only; no behavioral defect was implicated

### Green evidence

- Final checkpoint head: `b5ecae7251d14fb5006e97ee1c8f8196204ba78a`
- Complete CI run: `30003963950` — passed
- Temporary diagnostics were removed before the green checkpoint

Implemented and verified:

- exact gross and net return, realized and unrealized PnL, fees, simulated costs, drawdown, exposure, and count metrics;
- exact flat-to-flat trade attribution from recorded order sides and fill chronology;
- deterministic experiment manifest, decisions, orders, rejections, fills, cash ledger, account series, trades, metrics, verification, and result-manifest files;
- result identity derived from sorted core-artifact hashes without circular self-hashing;
- official promotion flag only for next-candle timing and conservative limit policy;
- byte-identical artifacts and identities for identical evidence;
- immutable local storage beneath `data/research/<experiment_id>/`;
- identical reruns accepted and conflicting bytes rejected safely;
- generated research evidence excluded from version control.

### Remaining limitations

Artifacts currently represent successful completed experiments. Typed failed-experiment artifacts, provider-free replay, independent stored-evidence verification, safe CLI commands, and final operator documentation remain to be implemented.
