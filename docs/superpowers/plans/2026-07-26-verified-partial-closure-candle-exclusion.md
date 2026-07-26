# Verified Partial-Closure Candle Exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the authentic truncated Binance BTCUSDT 4-hour row in immutable raw evidence, exclude it exactly once from canonical completed-candle data, and bind the resulting exclusion into a new `candle-dataset-v3` identity.

**Architecture:** Upgrade the fixed closure declaration to version 2, add focused exclusion evidence that exact-matches raw rows, and bind that evidence through ingestion, storage, replay, verification, handoff, workflows, and sealed-study identity checks. Strict full-timeframe validation remains the default for every other candle.

**Tech Stack:** Python 3.12, dataclasses, canonical JSON, SHA-256 identities, frozen `uv`, pytest, Ruff, Pyright, GitHub Actions.

## Global Constraints

- `RESEARCH_ONLY`; no execution authority.
- Public Binance Spot, `BTCUSDT`, `4h`, `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` only.
- Only provider-row SHA-256 `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775` may be excluded.
- Raw bytes remain unchanged; no repair, interpolation, filling, or synthesis.
- One eight-slot closure, one exclusion, two continuous segments.
- Dataset schema becomes `candle-dataset-v3`; Stage 2 rejects v1/v2.
- Strategy, features, labels, costs, thresholds, folds, final dates, and final-access policy remain unchanged.
- Stage 2 remains blocked until a new merged-main Stage 1 v3 artifact is independently approved in Issue #22.

## Planned Tasks

1. Upgrade the fixed closure contract to `exchange-closure-manifest-v2` with exact partial-candle identity and fail-closed parser tests.
2. Add canonical Binance row encoding, exact row matching, immutable exclusion evidence, and exhaustive mismatch tests.
3. Validate the unified eight-slot closure and derive exactly two continuous segments.
4. Introduce `candle-dataset-v3`, binding candles, closure, exclusion, and segment bytes.
5. Persist exclusion evidence and produce v3 during ingestion while preserving raw bytes.
6. Reproduce exclusions in provider-free replay and independently verify every identity field.
7. Upgrade verified loading and the Stage 1 handoff to v3 with counts `1/1/2`, exact closure ID, exact row SHA, and segment boundaries.
8. Propagate v3 exclusion identity through pre-final, final, replay, and independent study evidence without changing strategy behavior.
9. Update CLI and protected workflows so Stage 1 uploads exclusions and Stage 2 rejects anything except the exact v3 identity.
10. Complete end-to-end integration, tamper, workflow, and operator-documentation coverage.
11. Run Ruff, Pyright, complete pytest, build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks.
12. Require exact-head CI, protected squash merge, exact-main verification, a completely new Stage 1 run, independent artifact review, and continued Stage 2 blocking pending explicit dataset approval.

## TDD and Commit Sequence

Each task follows the same protected sequence:

- [ ] Write the specific failing tests.
- [ ] Run the smallest focused command and confirm RED for the intended missing behavior.
- [ ] Implement only the minimal production change required by the approved spec.
- [ ] Run focused tests, Ruff, and strict typing until GREEN.
- [ ] Commit one reviewable deliverable with a narrowly scoped message.
- [ ] Do not begin the next task while the current task has an unexplained failure.

## Complete Gate

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
python scripts/validate_tracked_files.py
uv run detect-secrets scan --all-files --baseline .secrets.baseline
```

## Stage 1 Evidence Required After Merge

- exact merged source SHA and workflow run ID;
- artifact name and artifact ID;
- retrieval run ID and dataset ID;
- `candle-dataset-v3` schema;
- closure, exclusion, and segment paths and SHA-256 values;
- closure count `1`, exclusion count `1`, segment count `2`;
- closure ID `binance-spot-system-upgrade-2018-02-08`;
- excluded provider-row SHA-256;
- canonical segment boundary indices;
- candle count and first/last opens;
- inventory root hash;
- replay and independent-verification success.

## Plan Self-Review

- All written-spec architecture, identity, failure, testing, workflow, and migration requirements map to the 12 tasks.
- No placeholder or deferred requirement remains.
- Closure v2 → exclusion evidence → dataset v3 → storage/replay/verification → reader/handoff → CLI/workflows/study identity is type-consistent.
- No execution, strategy behavior, final-test rule, model configuration, or unrelated refactor is included.
