# Market Data Core Final Verification

## Status

The Market Data Core implementation and deterministic non-live acceptance matrix have completed the required task, checkpoint, GitHub-hosted, and operator-local verification gates.

This evidence establishes market-data integrity, deterministic reconstruction, and fail-closed behavior. It does not establish strategy profitability.

## Evidence identity

- Verification date: `2026-07-23`
- Verified implementation head: `5f3b4afd78f399e5f5703714367d649cf99ac7f3`
- Pull request: `#9` — `feat: add verified Binance market data core`
- Deferred database-backed ingestion: issue `#7`
- Mandatory verification protocol: issue `#8`
- Fixed acceptance dataset ID: `9c696d00d7116a7a9ef7d8b7fb7e42b75d7150e4d1254768ef87080869bd1333`
- Canonical schema version: `candle-dataset-v1`

## Verified environments

### Operator-local Windows checkpoint

- Operating system: `Microsoft Windows NT 10.0.19045.0`
- PowerShell: `7.6.4`
- System `python --version`: `3.11.9`
- uv: `0.11.25`
- Project interpreter selected by uv: `Python 3.12.13`
- Verified head before and after the run: `5f3b4afd78f399e5f5703714367d649cf99ac7f3`
- Working tree before and after the run: clean

The project requires Python `>=3.12,<3.13`; the actual test, build, lint, typing, and CLI commands ran through uv with Python `3.12.13`. The separately installed system Python `3.11.9` was not used as the project interpreter.

### GitHub-hosted Ubuntu

- Runner: Ubuntu `24.04.4 LTS`
- Exact clean-head CI run: `29980034562`
- Result: `quality` passed and `gitleaks` passed

### GitHub-hosted Windows

- Runner: Microsoft Windows Server `2025`, build `10.0.26100`
- Native Windows milestone run: `29979874135`
- Result: complete Windows verification gate passed
- The temporary evidence workflow was removed before the final clean implementation head was accepted.

## Commands and observed outcomes

The operator-local checkpoint ran the following commands on the verified implementation head:

```powershell
uv sync --all-groups --frozen
uv run pre-commit run --all-files
uv run pytest -m "not live_api"
uv run pyright
uv run ruff format --check .
uv run ruff check .
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
uv run pre-commit run detect-secrets --all-files
uv run gemini-trading --help
uv run gemini-trading market-data --help
git diff --check
git status --short
```

Observed outcomes:

- Frozen dependency synchronization passed.
- Every pre-commit hook passed.
- `227` tests were collected; `1` opt-in live test was deselected; `226` deterministic non-live tests passed.
- Test duration was `26.24s` on the operator-local machine.
- Aggregate statement coverage was `91%` (`1319` statements, `125` missed).
- Strict Pyright reported `0 errors, 0 warnings, 0 informations`.
- Ruff reported `69 files already formatted` and all lint checks passed.
- The source distribution and wheel built successfully.
- `pip-audit` reported no known vulnerabilities in auditable dependencies. The local project package itself was skipped because it is not published on PyPI.
- Tracked-file policy validation passed.
- Detect-secrets passed.
- Root and market-data CLI help commands exited successfully and exposed `ingest`, `replay`, and `verify`.
- Prohibited `GEMINI_TRADING_MODE=live` failed closed with exit code `1` and the expected `UnsafeExecutionModeError`.
- `git diff --check` passed.
- The working tree remained clean and HEAD remained unchanged.

## Acceptance evidence

The deterministic ETHUSDT 4-hour acceptance matrix proves:

- exact raw fixture-byte persistence;
- bounded `[start, end)` retrieval semantics;
- strict completion using `close_time < server_time`;
- incomplete terminal candle exclusion;
- exact `Decimal` value and scale preservation;
- duplicate, reversal, gap, malformed-response, and partial-publication rejection;
- deterministic canonical UTF-8 JSONL;
- dataset identity calculated as `sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)`;
- fixed dataset ID `9c696d00d7116a7a9ef7d8b7fb7e42b75d7150e4d1254768ef87080869bd1333`;
- byte-identical offline replay without provider or network access;
- independent verification of raw hashes, retrieval-manifest encoding and hash, canonical bytes and hash, dataset identity, deterministic manifest bytes, provenance linkage, continuity, and completed state;
- equivalent retrieval runs producing identical canonical identity with separate provenance receipts;
- canonical output independence from the concrete storage adapter;
- no production-source literals for acceptance-only markets `ETHUSDT`, `BTCUSDT`, or `SOLUSDT`.

A separate PowerShell SHA-256 implementation independently recomputed the fixed acceptance dataset ID during checkpoint 2.

## Live smoke-test status

No live Binance request was executed as part of final verification.

The bounded public smoke test is deliberately opt-in and was deselected during deterministic verification. It runs only when:

```text
GEMINI_TRADING_RUN_LIVE_API_TESTS=1
```

The smoke test uses no credentials, accesses only public Binance Spot market-data endpoints, requests a small historical completed window, and writes only under pytest temporary storage. It does not authorize trading or exchange submission.

## Safety conclusions

- Runtime operation remains research and paper only.
- Live, demo, production, and unknown execution modes are rejected.
- No API-key, secret, signing, authorization, private-endpoint, strategy, signal, order, or exchange-submission capability was introduced.
- Operational CLI results are compact safe JSON and do not emit raw provider bodies, environment dumps, credentials, tracebacks, or absolute operator paths.
- Generated raw and canonical market-data paths are ignored by Git and rejected by repository tracked-file policy.
- Replay performs no network access.

## Remaining limitations

1. **Cross-store rollback:** raw and canonical stores are separate immutable interfaces. Validation prevents canonical publication before a complete valid sequence exists, and verification detects missing or inconsistent artifacts, but the system cannot roll back files already published if storage fails after publication begins.
2. **Informational timestamps:** retrieval and provenance creation timestamps are validated but are not externally signed. They cannot independently prove time authenticity against an external authority and do not affect canonical candle bytes or dataset identity.
3. **Storage scope:** the operational adapter in this milestone is the local immutable filesystem adapter. Database-backed ingestion remains deferred under issue #7.
4. **Live compatibility:** the public smoke test was not executed during final verification. Deterministic fixture, contract, replay, and verification evidence passed without live-network dependence.
5. **Profitability:** this milestone verifies data integrity and reproducibility only. It does not establish strategy profitability, trading performance, or suitability for live execution.

## Milestone disposition

The verified implementation is suitable for protected pull-request review and merge as a research/paper-only Market Data Core, subject to the final CI and security checks running on the exact commit containing this report and the required post-merge verification on protected `main`.
