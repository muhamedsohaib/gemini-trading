# Task 12 Red-Gate Evidence

- Scope: safe read-only `research backtest`, `research replay`, and `research verify` CLI.
- Tests were committed before the command implementation: parser requirements, runtime-policy ordering, safe error output, deterministic end-to-end backtest/replay/verify, diagnostic non-promotion, and live-mode rejection.
- Formatted test head: `63511243e0e492e400303f52ded6cc2a44bbe874`.
- Initial CI run `30019270721` failed at the formatter before behavioral collection.
- Normalized red-gate runs `30019408824`, `30019560283`, and `30019847362` passed formatting and gitleaks but stopped at Ruff lint before pytest.
- Repository-wide lint diagnosis found only `E731` in the new CLI handler and one stale `F401` import in Task 11 replay; both were removed at `38abf6e10c5d7f0767c1158220dad3e697c3e230` with all temporary workflows and diagnostic output deleted.
- Safety boundary: no credentials, private endpoints, network replay, paper broker, demo adapter, or exchange submission.
