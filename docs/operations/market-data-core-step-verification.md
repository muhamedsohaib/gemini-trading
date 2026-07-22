# Market Data Core Step Verification Protocol

## Status

This protocol is mandatory for the `feature/market-data-core` milestone and supplements the approved Market Data Core design.

Its purpose is to prevent unverified implementation drift. A task is not complete because code exists; it is complete only when fresh evidence proves the intended behavior and relevant failure behavior.

## Per-task gate

Every implementation task must follow this sequence:

1. State the exact behavior, invariant, and failure mode.
2. Add or identify the focused test that proves the requirement.
3. Run the focused test before implementation and confirm the expected failure when test-driven development applies.
4. Implement the smallest change that satisfies the requirement.
5. Run the focused tests and inspect the actual output.
6. Run Ruff formatting and lint checks on the affected scope.
7. Run Pyright strict checking on the affected scope, or the full project when scope isolation is unreliable.
8. Run all relevant regression and safety tests.
9. Inspect the Git diff for accidental scope expansion, unsafe execution behavior, secrets, generated data, or provenance contamination.
10. Append the exact commands, observed outcomes, commit identity, and known limitations to `reports/verification/market-data-core-progress.md`.
11. Stop on any failure. Correct it and rerun the complete task gate before beginning another task.

No unresolved failure may be carried into a later task.

## Checkpoint gate

At each meaningful checkpoint, run fresh verification of:

- the complete deterministic test suite;
- all pre-commit hooks;
- package build;
- dependency audit;
- tracked-file and secret scans;
- unsafe execution-mode rejection;
- repository cleanliness;
- GitHub `quality` and `gitleaks` checks.

A checkpoint is not accepted until all applicable checks pass.

## Market-data trust checks

Implementation work must continuously prove the following properties as they become available:

- canonical JSONL is reproducible byte for byte;
- the dataset identity is stable for identical canonical content;
- independent equivalent retrieval runs produce separate provenance receipts without changing canonical identity;
- preserved raw pages reconstruct the canonical dataset;
- incomplete candles never enter trusted canonical output;
- duplicate, out-of-order, gapped, malformed, conflicting, and partially retrieved inputs fail closed;
- replay uses no network access;
- storage adapters cannot alter canonical bytes;
- provider-specific metadata cannot contaminate canonical candle identity;
- unsafe execution modes remain prohibited.

## Evidence rules

The verification log must:

- record exact commands and observed results;
- identify the commit or working-tree state being tested;
- distinguish focused task checks from full checkpoint checks;
- record failures and their remediation rather than hiding them;
- state any limitation that remains untested;
- exclude credentials, authorization headers, and unrestricted raw API responses.

## Completion gate

The Market Data Core milestone cannot be declared complete until:

1. every implementation task has a recorded passing gate;
2. every checkpoint has fresh passing evidence;
3. the final full verification suite passes on the exact pull-request head;
4. GitHub `quality` and `gitleaks` pass on that head;
5. the final working tree is clean;
6. the final verification report is committed;
7. the pull request is merged into protected `main`;
8. GitHub issue #8 is closed only after the merged result is verified on `main`.
