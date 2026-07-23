# Market Data Core Progress Verification

This append-only log records fresh task and checkpoint evidence for GitHub issue #8.

## Rules

- Record the tested commit or working-tree identity.
- Record exact commands and observed outcomes.
- Record failures and remediation.
- Record unresolved limitations.
- Do not include credentials, authorization headers, or unrestricted API responses.

## Task 1 — Verification ledger and generated-data guard

### RED phase

- Tested commit: `7fe5185c2d7c009ec61b9c6541bd557eef27b328`
- GitHub Actions run: `29955214056`
- Added tests requiring tracked paths under `data/raw/` and `data/canonical/` to raise `RepositoryPolicyViolation` with a generated-market-data diagnostic.
- Observed `quality` result: failed at `uv run pytest` after format, lint, and Pyright passed.
- Observed `gitleaks` result: passed.
- Expected cause confirmed by code inspection: the pre-change policy had no generated-market-data prefix rule.
- Remediation started: add normalized-prefix rejection while preserving the existing `RepositoryPolicyViolation` public exception.

### GREEN phase

- Initial implementation head: `62b308221711d1a7567fd120dd078aec52bf4f02`.
- GitHub Actions run `29955344061` stopped at `uv run ruff format --check .`; `gitleaks` passed. No later quality steps were treated as evidence because they were skipped.
- Remediation: applied Ruff-equivalent line wrapping in commits `66b361643d374516be719ab1925fd169908b7b73` and `5829145f849a27d2d60e204361b51f5d1291bc0b`.
- Final tested implementation head: `5829145f849a27d2d60e204361b51f5d1291bc0b`.
- GitHub Actions run: `29955458684`.
- Observed `quality` result: passed.
- Observed quality steps: frozen dependency sync, Ruff format check, Ruff lint, Pyright strict checking, full pytest suite, package build, pip-audit, tracked-file policy validation, and detect-secrets all passed.
- Observed `gitleaks` result: passed.
- Generated market-data paths are ignored by Git and rejected by the tracked-file policy using the existing `RepositoryPolicyViolation` exception.
- Limitation: this task gate was observed on GitHub-hosted Ubuntu; Windows-local verification is deferred to the next operator checkpoint and final exact-head gate.

## Task 2 — Domain contracts and error taxonomy

### RED phase

- Final test-only RED commit: `08a3c33bb7e2fd8fb32b5684fec489282d3684ec`.
- Windows-local Ruff `0.15.22` check passed after import normalization.
- Windows-local focused pytest collection failed with five intended `ModuleNotFoundError` results because `gemini_trading.domain` and `gemini_trading.data` did not yet exist.
- `git diff --check` passed and the working tree was clean after the test-only commit.
- GitHub Actions run: `29957670360`.
- GitHub format and lint passed; strict Pyright failed on the same absent domain/data imports before pytest. `gitleaks` passed.
- Tooling failure discovered during RED preparation: `uv.lock` pinned Ruff `0.15.22` while pre-commit pinned Ruff `0.12.4`, causing contradictory import grouping. Commit `0dc23a6d9fadd60fdbae5220bffd1434360a9c6e` aligned pre-commit to `0.15.22` before production implementation.

### GREEN phase

- Initial production-contract head: `4645916a74d37fd188bdeda52ff5f2f19ac883af`.
- Ruff correctly reclassified `gemini_trading.domain` and `gemini_trading.data` as first-party after those packages existed; commit `df52b0cc98bd910913a25fe9ff91fc855e1ff76b` restored the required four import separators.
- Final Windows-local tested head: `df52b0cc98bd910913a25fe9ff91fc855e1ff76b`.
- Windows-local outcomes: frozen dependency sync passed; Ruff format reported 12 files already formatted; Ruff lint passed; Pyright reported 0 errors, 0 warnings, and 0 informations; 57 focused, regression, and safety tests passed in 0.97 seconds; aggregate coverage was 84%; `git diff --check` passed; all pre-commit hooks passed; final working tree was clean.
- GitHub Actions run: `29958596769`.
- GitHub `quality` passed frozen sync, Ruff format, Ruff lint, Pyright, full pytest, package build, pip-audit, tracked-file policy, and detect-secrets.
- GitHub `gitleaks` passed.
- Diff review against the Task 1 evidence base found only the intended Ruff-version alignment, eight domain/data production files, and five contract-test files. No provider, network, storage, strategy, signal, order, or execution behavior was introduced.
- Public contract review confirmed frozen slotted dataclasses, explicit instrument identity, curated timeframes, UTC-only timestamps, finite Decimal enforcement, safe provider-error metadata, and the approved retrieval/dataset/provenance field shapes.
- Limitation: auxiliary dataset-manifest and provenance validation branches are not yet exhaustively unit-tested; deeper cross-field consistency, deterministic serialization, and content/hash linkage are deferred to their dedicated later tasks.

## Task 3 — Pure candle validation

### RED phase

- Initial test-only commit: `e94e823d7083447a63bd7d17538579bd4227312c`.
- GitHub Actions run `29959804527` stopped at Ruff formatting before reaching the intended failure; this run was rejected as RED evidence. `gitleaks` passed.
- Repository-pinned Ruff formatting and lint fixes were exported through temporary read-only workflows and applied to the two tests; all temporary workflow and placeholder files were removed from the final tree.
- Final test-only RED head: `7907e5f0b3139e749d59e78de934a9d40d712986`.
- GitHub Actions run: `29961406243`.
- Frozen dependency sync, Ruff format, and Ruff lint passed; strict Pyright then failed on the intentionally absent `gemini_trading.data.validation.candles` module. Pytest and later quality steps were skipped. `gitleaks` passed.
- Unit tests covered non-positive OHLC, negative and zero volume behavior, open/close range geometry, strict completion filtering, empty sequences, identity mismatch, request-window containment, incomplete canonical rows, duplicates, reversals, and gaps.
- Hypothesis tests mutated valid sequences into duplicates, reversals, and internal gaps and required the corresponding specialized exception.

### GREEN phase

- Initial implementation head: `d275bd3f64af1717d09102174f6033cb0620d530`.
- GitHub Actions run `29964524157` stopped at Ruff formatting; no later quality step was treated as evidence. `gitleaks` passed.
- The repository-pinned Ruff output was applied in commit `e3e0a32d986dda709a6bc8c896cea2e63a75b5f7`; its full GitHub gate passed in run `29964657279`.
- Review then removed an untested UTC guard from `completed_candles` so the implementation remained strictly minimal and matched the Task 3 contract. Final tested implementation head: `a8955e62cf4ac8a13f2bd16ce802323e9ca6c5ff`.
- Final GitHub Actions run: `29964789124`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, the full pytest suite including Hypothesis properties, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.
- Diff review confirmed only the validation package and its two intended tests remained in the net Task 3 change; temporary workflows and placeholders were absent.
- Contract review confirmed the required check order: non-empty, per-candle geometry, identity consistency, request containment, completed flag, duplicate detection, strict ordering, then exact timeframe continuity.
- `completed_candles` uses `dataclasses.replace(..., completed=True)` only for rows with `close_time < server_time` and does not mutate input candles.
- No provider, network, storage, strategy, signal, order, credential, or execution behavior was introduced.
- Limitation: this Task 3 gate was observed on GitHub-hosted Ubuntu; a fresh Windows-local run is deferred to the next operator checkpoint and final exact-head verification.

## Task 4 — Strict Binance kline normalization

### Tooling stabilization

- Commit `0d7f5932927132b746410e00537cd4e2eab94ba1` configured Ruff isort with `known-first-party = ["gemini_trading"]`, preventing import-group changes when RED tests reference not-yet-created first-party submodules.
- GitHub Actions run `29965042940` passed the complete quality and Gitleaks gates before Task 4 tests were added.

### RED phase

- Test-only RED head: `7f982e2bb574bc67b1b20bf62af26ebbe0e85b2f`.
- GitHub Actions run: `29965299346`.
- Frozen dependency sync, Ruff format, and Ruff lint passed; strict Pyright failed on the intentionally absent `gemini_trading.data.normalization.binance_klines` module. Pytest and later quality steps were skipped. `gitleaks` passed.
- Sanitized fixtures covered a valid two-row page, a short malformed row, and an invalid decimal marker used to prove safe error messages.
- Unit tests covered exact field mapping, Decimal exponent preservation, invalid UTF-8, invalid JSON, non-list roots and rows, non-integer millisecond types including booleans, non-finite decimals, safe messages, provider/completion metadata, and a far-future exact-millisecond regression.
- Hypothesis properties covered exact integer-millisecond round trips without float precision loss, exact decimal value/exponent preservation, and rejection of non-integer timestamp values.

### GREEN phase

- Initial implementation head: `619d522074f57a5c338137d6a46f4a7d99f26c7c`.
- GitHub Actions run `29965466455` passed sync, Ruff format, and Ruff lint, then failed strict Pyright because `len` received `list[Unknown]`; pytest and later steps were skipped. `gitleaks` passed.
- A temporary read-only diagnostic workflow exported the exact Pyright message. Commit `8004d825ba1122cebd2fe272fc4fe40ff3c33d99` narrowed each row to `list[object]` before checking its length and removed the workflow.
- Final GitHub Actions run: `29965626579`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, the full pytest suite including Hypothesis properties, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.
- Net diff review found only the normalization package, three sanitized fixtures, one unit-test file, and one property-test file; temporary diagnostic workflows were absent.
- The parser decodes strict UTF-8, uses `json.loads(..., parse_float=str)` to prevent JSON decimal tokens from entering a float path, rejects non-standard JSON constants, requires a list root and list rows with at least seven fields, and reads only Binance indices `0` through `6`.
- Milliseconds are converted exactly with `datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=value)` after rejecting booleans and non-integers; no division or timestamp float conversion is used.
- Numeric fields use `Decimal(str(value))`, require finiteness, preserve decimal exponents, and never call `float`.
- Output candles are immutable candidates with `completed=False` and `source_provider="binance_spot"`; malformed rows fail closed with generic `ProviderSchemaError` messages that do not include raw payload content.
- No credentials, authorization headers, private endpoints, network access, strategy, signal, order, or execution behavior was introduced.
- Limitation: this Task 4 gate was observed on GitHub-hosted Ubuntu; a fresh Windows-local run is deferred to the next operator checkpoint and final exact-head verification.

## Task 5 — HTTP transport and Binance Spot provider

### RED phase

- Initial test-only head: `7c39b4940b3fe68969202cb495f0618b48f9f2bd`.
- GitHub Actions run `29966036458` stopped at Ruff formatting before reaching the intended missing-module failure; this run was rejected as RED evidence. `gitleaks` passed.
- The repository-pinned Ruff formatter was applied through a temporary read-only workflow; all temporary workflow files were removed from the final test tree.
- Final test-only RED head: `af1f2776aef0a87abc60d56f021452eb467faf5f`.
- GitHub Actions run: `29966201370`.
- Frozen dependency sync, Ruff format, and Ruff lint passed; strict Pyright failed on the intentionally absent `gemini_trading.data.providers` modules. Pytest and later quality steps were skipped. `gitleaks` passed.
- Unit tests covered exact GET behavior, unchanged response bytes, HTTP-error byte preservation, body-free connection failures, exact public endpoints, sorted bounded query parameters, integer UTC milliseconds, no constructor credential surface, 429 `Retry-After`, retryable 5xx classification, permanent 4xx classification, safe malformed server-time rejection, and injected-transport behavior.
- The integration contract test used only an injected fake transport and made no live network request.

### GREEN phase

- Initial implementation head: `de2c3821c483563c447403808d48b96f148b57f3`.
- GitHub Actions run `29966364487` stopped at Ruff formatting; no later quality step was treated as evidence. `gitleaks` passed.
- Repository-pinned Ruff output was applied in commit `640a1a3a873bbc719bc9b67f514a579a21a61cb9`; run `29966503124` then passed format and lint but failed strict Pyright because positional `urlopen(request, timeout_seconds)` was typed as request data rather than timeout.
- A temporary read-only diagnostic workflow exported the exact Pyright output. Final implementation head `5cc0110ce832886ab7ec674e8422576c3c7aa939` changed the call to `urlopen(request, timeout=timeout_seconds)`, aligned the monkeypatched tests, and removed the workflow.
- Final GitHub Actions run: `29966661856`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.
- Net diff review found only four provider files, two unit-test files, and one integration-contract test; no temporary workflows or placeholders remained.
- `UrllibTransport` uses `urllib.request.Request(method="GET")`, returns exact success and `HTTPError` bytes with status and headers, and maps `URLError`, `TimeoutError`, and `OSError` to a body-free `ProviderConnectionError`.
- `BinanceSpotProvider` uses only `/api/v3/time` and `/api/v3/klines`, stable sorted parameters, `[start_time, end_time)` mapping through inclusive `endTime = end_ms - 1`, exact integer UTC-millisecond arithmetic, injected transport and clock dependencies, and safe HTTP/schema classification.
- The provider constructor defines no API-key, secret, signature, authorization, or credential parameter and reads no credential environment variable.
- No private endpoint, filesystem write, canonical dataset construction, strategy, signal, order, or execution behavior was introduced.
- Limitation: this Task 5 gate was observed on GitHub-hosted Ubuntu; a fresh Windows-local run is deferred to the next operator checkpoint and final exact-head verification.

## Task 6 — Immutable local storage

### RED phase

- Initial test-only head: `ff24a545b16ac9fb4168e4645e987e46a1080f8f`.
- GitHub Actions run `29967590847` stopped at Ruff formatting before reaching the intended missing-module failure; this run was rejected as RED evidence. `gitleaks` passed.
- Repository-pinned Ruff formatting and three regex-literal corrections were applied through temporary workflows; those workflows were removed from the clean test tree.
- Final test-only RED head: `ead5a3068eaf42a31bfe048ee010a1c12bcd19c0`.
- GitHub Actions run: `29967783120`.
- Frozen dependency sync, Ruff format, and Ruff lint passed; strict Pyright failed on the intentionally absent `gemini_trading.data.storage` package. Pytest and later quality steps were skipped. `gitleaks` passed.
- Unit tests covered exact bytes, idempotent identical writes, immutable conflict preservation, temporary-write failure cleanup, six-digit page naming, sequence bounds, traversal rejection, stable retrieval-manifest bytes, typed raw-run reconstruction, missing files, canonical paths, provenance paths, and canonical conflict preservation.
- Hypothesis properties covered arbitrary byte round trips, arbitrary conflicting bytes, and containment beneath the canonical root.

### GREEN phase

- Initial implementation head: `b6284f1cc71298c476dad33e7d2ea09803560678`.
- GitHub Actions run `29968040222` passed sync and Ruff checks, then failed strict Pyright on four decoded JSON container values typed as `Unknown`; pytest and later quality steps were skipped. `gitleaks` passed.
- A focused cleanup narrowed decoded mappings and lists to explicit `dict[object, object]` and `list[object]` containers. Connector-authored implementation head `62af7be50600c0f737625610e155888ceba2afd6` passed the full gate in run `29968244914`.
- Review identified a precision defect not covered by the initial suite: millisecond-only serialization changed a valid `retrieved_at` value from `789123` microseconds to `789000` during typed reconstruction.
- Regression-test head `94ae1f80661365cd49d2db2035085d9e260b2fe2` passed sync, Ruff, and Pyright, then failed pytest in run `29968457449` with the exact expected `789123` versus observed `789000` assertion. `gitleaks` passed.
- The formatter now emits milliseconds for millisecond-aligned values and microseconds otherwise, preserving existing stable manifest bytes while round-tripping all domain-valid timestamp precision.
- Connector-authored precision head `a670cb2b10f446c415c10d642ed0fc925e0d48b0` passed the complete gate in run `29968621122`.
- Final implementation head: `9d4281d7f9845b5b13b6c412267dd495fee0d133`.
- Final GitHub Actions run: `29968692730`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest including Hypothesis properties, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.
- Net diff review found only `storage/__init__.py`, `storage/base.py`, `storage/local_immutable.py`, the immutable-storage unit suite, and the immutable-storage property suite; temporary workflows and placeholders were absent.
- `write_immutable` uses a same-directory exclusive temporary file, flush plus `fsync`, atomic hard-link publication, byte comparison for idempotency/conflict, and unconditional temporary cleanup. No final destination can contain partial bytes, and conflicting existing bytes remain unchanged.
- Storage identities enforce the approved segment grammar and reject empty values, separators, and `..`. Raw pages use six-digit names under `data/raw/binance_spot/<run-id>/`; canonical datasets and provenance use the approved `data/canonical/<dataset-id>/` layout.
- Exact raw response bytes are preserved separately from deterministic page metadata. `read_run` reconstructs typed `RetrievalManifest` and `RawPage` values without performing the hash verification reserved for Task 9.
- Property identities are prefixed to avoid Windows-reserved basename flakiness while retaining varied valid-segment coverage.
- No network access, credentials, private endpoint, strategy, signal, order, or execution behavior was introduced.
- Limitation: the final Task 6 gate was observed on GitHub-hosted Ubuntu; a fresh Windows-local run remains required at the operator checkpoint and final exact-head verification.
