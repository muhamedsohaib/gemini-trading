# Deterministic Research and Backtesting Milestone Acceptance

## Decision

The deterministic research/backtesting milestone is eligible for protected merge after the final evidence-only PR head passes the complete repository CI gate. This decision establishes simulation correctness, reproducibility, and safe research operations. It does not establish strategy profitability or readiness for real capital.

## Task 11 — Provider-free replay and independent verification

Task 11 is complete.

Implemented and verified:

- strict canonical parsing of persisted experiment manifests and simulation configurations;
- exact experiment, dataset, configuration, code-commit, and result identity validation;
- reconstruction of the supported non-production scripted fixture from immutable manifest evidence;
- verified canonical-dataset loading without provider or network access;
- deterministic rerun of the complete backtest engine;
- byte-for-byte comparison of regenerated decisions, orders, rejections, fills, ledger, account series, trades, metrics, verification, and result-manifest artifacts;
- independent artifact-hash and result-identity recomputation;
- fail-closed behavior for missing, malformed, tampered, non-canonical, mismatched, or incomplete evidence;
- sorted deterministic verification checks including replay equivalence, accounting reconciliation, dataset verification, metrics recomputation, referential integrity, and identity verification.

Task 11 limitations:

- replay supports the non-production scripted fixture only;
- the engine remains one-instrument, long-only, and candle-based;
- OHLCV evidence cannot reconstruct queue priority, exact intrabar path, trade ordering, or true market impact;
- replay requires the exact recorded clean code commit;
- typed failed-experiment artifact publication remains deferred.

## Task 12 — Safe research CLI and final acceptance

Task 12 is complete subject only to protected-merge and merged-main verification.

Implemented and verified:

- `gemini-trading research backtest`;
- `gemini-trading research replay`;
- `gemini-trading research verify`;
- explicit required identities and paths;
- runtime-policy enforcement before reading configuration or evidence;
- exact clean Git-head resolution;
- strict documented fixture configuration schema;
- compact canonical JSON success and failure output;
- safe broad-failure containment without traceback, environment, raw evidence, or absolute-path leakage;
- immutable artifact publication;
- provider-free replay and independent verification;
- official versus diagnostic promotion classification;
- rejection of live mode before work begins.

## Acceptance evidence

- Full CI run `30020996929` passed on head `4e5b98a7d5723eb9b64f2ba74d071a6c14a87c47`.
- Focused deterministic acceptance run `30021138715` passed on head `ae18706d79bb3a02069a138378e1b62d21cfcf67`.
- Focused acceptance result: 5 tests passed.
- Focused coverage included CLI backtest, provider-free replay, independent verification, tamper detection, diagnostic non-promotion, and live-mode rejection.
- The final evidence-only PR head must pass formatting, lint, strict typing, the complete test suite, package build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks before merge.

## Safety and governance

- Research only.
- No credentials or private endpoints.
- No paper broker, demo adapter, or live exchange submission.
- No leverage, futures, shorting, or autonomous order authority.
- The scripted fixture is permanently non-production.
- Profitability and strategy edge are not established.
- The assistant remains an independent advisory reviewer for evidence classification, strategy promotion, risk-limit changes, credentials, stage changes, material capital allocation, and acceptance of unresolved limitations.
- Final real-capital authorization remains an explicit human decision and must fail closed when required evidence or advisory review is unavailable.

## Merge and closure protocol

1. Pass the complete CI gate on the final PR head.
2. Mark PR #13 ready for review.
3. Merge through protected `main` using the repository-approved merge method.
4. Run complete verification against the exact merged-main commit.
5. Record the merged commit and verification run on Issue #12.
6. Close Issue #12 only after merged-main verification passes.
7. Open the next design gate for the candidate multi-model strategy; no implementation begins before its written specification is approved.
