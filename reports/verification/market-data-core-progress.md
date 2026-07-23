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

## Task 7 — Deterministic canonical dataset writer

### RED phase

- Initial test files were committed at `b07a5323369cef63c675a4ca75d9775c3d127b3c` and `ac1f9d30e3d14c4a3b0d00ee700e179e4d961b53`.
- GitHub Actions run `29969257505` stopped at Ruff formatting before the intended missing-module failure; this run was rejected as RED evidence. `gitleaks` passed.
- Repository-pinned Ruff format and lint fixes were applied through a temporary cleanup workflow, which removed itself from the clean test tree.
- Bot-authored formatted head `ca967762c14e733ac566eefd406d0d7c480f55bb` was marked `action_required` without jobs. Connector-authored test-only RED head: `22ecd4bf689671257c37ac485e2db6e4142a7552`.
- GitHub Actions RED run: `29969376593`.
- Frozen dependency sync, Ruff format, and Ruff lint passed; strict Pyright failed on the intentionally absent `gemini_trading.data.datasets.canonical_writer` module. Pytest and later quality steps were skipped. `gitleaks` passed.
- Read-only diagnostic run `29969424437` exported the exact Pyright output: 53 diagnostics, all caused by the missing canonical-writer import and the resulting unknown-type cascade; no independent test typing defect was present.
- Unit tests defined fixed field order, compact JSONL, one newline per row, UTC `Z` millisecond timestamps, preserved decimal trailing zeros, incomplete-row rejection, exact dataset-ID formula, deterministic manifest bytes, non-empty manifest input, provenance bytes, and run/provenance isolation.
- Hypothesis properties defined stable bytes/manifest/identity for identical candles, changed bytes and identity when a canonical close value changes, and invariant canonical bytes/identity when only run metadata changes.

### GREEN phase

- Initial clean implementation head: `0fa70e2af6684cd717863ec6cd5d48ca6001d77b`.
- GitHub Actions run `29969519793` passed frozen sync and Ruff formatting, then failed Ruff lint on one `UP012` diagnostic for an unnecessary explicit UTF-8 argument to `encode`; strict Pyright and pytest were skipped. `gitleaks` passed.
- Read-only diagnostic run `29969556033` isolated that single lint finding. The minimal correction changed `f"{serialized}\n".encode("utf-8")` to `f"{serialized}\n".encode()`; the dataset-ID formula retained explicit UTF-8 encoding as required by the design.
- Corrected implementation head: `9882f8b922496303c38878e0f356a270fc962bca`.
- GitHub Actions run `29969647798` passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest including Hypothesis properties, package build, pip-audit, tracked-file policy validation, detect-secrets, and `gitleaks`.
- Final review found one test-evidence gap: `ensure_ascii=False` was implemented but no test explicitly proved non-ASCII text remained UTF-8 rather than `\\u`-escaped. `tests/unit/data/datasets/test_canonical_utf8.py` was added to prove exact UTF-8 bytes.
- Final implementation head: `5908573f03686d7ddc246eb26e3148c6c0d3b147`.
- Final GitHub Actions run: `29969747441`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest including property tests and explicit UTF-8 coverage, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.
- Net diff review found only `data/datasets/__init__.py`, `data/datasets/canonical_writer.py`, the deterministic-writer unit suite, the UTF-8 unit test, and the dataset-identity property suite. Temporary workflows and placeholders were absent.
- Canonical candle rows use fixed insertion order, compact UTF-8 JSON, one trailing newline per row, UTC `Z` milliseconds, and `format(value, "f")` decimal text. Incomplete candles are rejected.
- Dataset identity is exactly `sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)`. The deterministic manifest contains only schema, content identity/hash, provider, instrument, timeframe, requested window, actual first/last open times, and count.
- Run ID, page hashes, retrieval-manifest hash, linkage state, and receipt creation time exist only in `DatasetProvenance`; they cannot alter canonical JSONL or dataset identity.
- No filesystem writes, network access, credentials, private endpoints, strategy, signal, order, or execution behavior was introduced.
- Limitation: the final Task 7 gate was observed on GitHub-hosted Ubuntu; fresh Windows-local verification remains required at the operator checkpoint and final exact-head verification.

## Task 8 — Retry policy and fail-closed ingestion

### RED phase

- Task base: `c4952786646453e0fc47c450ceb0b6138cd75d60`.
- Final test-only RED head: `397aa87e95ba79053090a347bce7fb061bbedb82`.
- GitHub Actions RED run: `29971120358`.
- Frozen dependency sync, Ruff format, and Ruff lint passed; strict Pyright failed because `gemini_trading.data.ingestion.retry` and `gemini_trading.data.ingestion.service` did not yet exist. Pytest and later quality steps were skipped. `gitleaks` passed.
- Read-only diagnostic run `29971157329` exported the complete strict-Pyright output and confirmed every diagnostic originated from those two intentionally missing modules and the resulting unknown-type cascade; no independent test typing defect was present.
- Retry tests defined positive attempt limits, finite non-negative base delays, exponential backoff, `Retry-After` precedence, and attempt validation.
- Ingestion tests defined one shared server-time snapshot, raw persistence before normalization, forward cursor progress, repeated-cursor rejection, terminal incomplete guard behavior, continuation after a short non-terminal page, empty non-terminal failure, transient retry, `Retry-After`, retry exhaustion, permanent-response rejection, malformed raw preservation, gap failure, zero-completed failure, and no canonical publication before complete validation.
- Three sanitized deterministic fixtures model a two-page retrieval, terminal guard page, and internal continuity gap. They contain no credentials or unrestricted live response data.

### GREEN phase

- Initial clean implementation head: `703aae0941f4ae75d25d1cbe5d19f592400a5f54`.
- GitHub Actions run `29971383285` stopped at Ruff formatting before strict typing or tests; no skipped result was counted as evidence. `gitleaks` passed.
- Repository-pinned Ruff diagnostics identified one substantive lint issue after formatting: `B023`, caused by the retry closure capturing the mutable pagination cursor.
- Read-only diagnostic run `29971462624` exported the exact formatted files and lint output. The correction binds the attempt cursor as a lambda default argument, so retries use the cursor value belonging to that page request.
- Robust cleanup run `29971644010` passed repository-pinned Ruff format and lint and produced corrected bot-authored head `a09c770a216c7b553b39ba6bcf1c0a8fdea4d3e3`.
- Clean connector-authored implementation head: `934bce708c5696cf0db883dc98c5d616655c40d0`.
- GitHub Actions run `29971679183` passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy validation, detect-secrets, and `gitleaks`.
- `RetryPolicy` is frozen and slotted, validates its configuration, retries at most `max_attempts`, applies exponential delay `base * 2 ** (attempt - 1)`, and honors a larger provider `retry_after_seconds` value.
- `IngestionService` uses injected provider, stores, clock, sleeper, run-ID factory, normalizer, and page limit. It retries only connection failures, rate limits, and retryable provider responses.
- Each successful run takes one governing Binance server-time snapshot. Each exact response body is hashed and persisted as `RawPage` before the normalizer receives it.
- Retrieval terminates only when the cursor reaches the requested end or a persisted page contains the incomplete guard candle. A short page does not terminate by itself; empty and non-advancing pages fail closed.
- Completed candles are filtered using the shared server-time snapshot, then the complete sequence is validated before any canonical-store method is called. Malformed payloads, duplicates/order/gaps, retry exhaustion, and zero-completed windows write no canonical dataset.
- On successful validation, the service writes deterministic canonical JSONL and manifest bytes, hashes the persisted completed retrieval manifest, and writes a run-specific provenance receipt. Run metadata does not alter canonical identity.
- Safe failure manifests contain only the exception type and safe message. Raw payload bytes are never copied into failure diagnostics.

### Checkpoint 1

- Temporary checkpoint head: `23d5132d0ec7250c64683d805f04265a37124129`.
- Checkpoint run: `29971789329`.
- Observed result: passed the Task 8/data/property/regression/safety pytest scope, every pre-commit hook, strict Pyright, package build, pip-audit, tracked-file policy, explicit live-mode rejection, `git diff --check`, and clean working-tree verification.
- The temporary checkpoint workflow was removed.
- Clean post-checkpoint implementation head: `2a02999abf9d2c9c3ec56b3358187dd3f5af9e7e`.
- Clean exact-head GitHub Actions run: `29971879936`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.
- Net Task 8 diff contains only the ingestion package, two ingestion test modules, and three sanitized Binance fixtures. Temporary diagnostic/checkpoint workflows and placeholders are absent.
- No credential, private endpoint, strategy, signal, order, or execution capability was introduced. Runtime live mode remains rejected.
- Architectural limitation: the approved `RawStore` and `CanonicalStore` protocols expose separate immutable write operations but no transaction, staging bundle, or rollback contract. The implementation therefore guarantees failed manifests and zero canonical calls for provider, retry, normalization, completion, and validation failures before publication begins, but cannot honestly guarantee cross-store rollback if a filesystem/store failure occurs after completed-manifest or canonical publication has started. A transactional composite publication boundary would be required for that stronger guarantee; this limitation must remain visible during Task 9 verification and milestone acceptance.
- Platform limitation: the final Task 8 checkpoint and exact-head gates were observed on GitHub-hosted Ubuntu. Fresh Windows-local verification remains required at the operator checkpoint and final exact-head verification.

## Task 9 — Offline replay and independent verification

### RED phase

- Task base: `1fc7aa3841e905c6edceaca1dba6b6a9c64c4436`.
- Initial test-only head: `1d048f9a3b2244359cba308c368084b92acdadd0`.
- GitHub Actions run `29973056382` stopped at Ruff formatting before the intended missing-module failure; this run was rejected as RED evidence. `gitleaks` passed.
- Repository-pinned Ruff formatted and lint-fixed the three Task 9 tests. Clean test-only RED head: `4358c5e98799f086ad25edd6975409c390f894d2`.
- GitHub Actions RED run: `29973124542`.
- Frozen dependency sync, Ruff format, Ruff lint, and `gitleaks` passed; strict Pyright failed on the intentionally absent replay and verification modules. Pytest and later quality steps were skipped.
- Read-only diagnostic run `29973171371` exported the complete strict-Pyright output: all 55 diagnostics resulted from the absent Task 9 modules and the planned exact-manifest-byte reader; no independent test typing defect was present.
- The RED suite defined provider-free replay, disabled-network execution, exact canonical JSONL/manifest/identity reproduction, equivalent-run identity with separate receipts, raw page hash verification, canonical retrieval-manifest bytes, failed-run rejection, raw/canonical/manifest/provenance tampering rejection, parsed continuity, completed-state validation, and missing-receipt rejection.

### Initial GREEN phase and remediation

- Initial replay and verification modules reused the Task 4 normalizer, Task 3 completion/sequence validation, Task 7 canonical serializers/builders, and immutable local storage.
- Diagnostic run `29973545694` isolated an indentation error in the newly inserted manifest-byte reader and strict-Pyright private-helper usage. No result from that run was accepted.
- Diagnostic run `29973683400` passed Ruff and all 105 focused/regression tests, but strict Pyright exposed an architectural regression: extending the global write-oriented storage protocols forced unrelated Task 8 test stores to implement Task 9 read methods.
- The global `RawStore` and `CanonicalStore` contracts were restored unchanged. Task 9 introduced narrow `ReplayRawStore`, `ReplayCanonicalStore`, and `VerificationCanonicalStore` protocols instead.
- Cleanup run `29973772860` passed repository-pinned Ruff, strict Pyright, and all 105 focused/regression tests.
- Clean connector-authored implementation head: `27c7ae8d4fe01239e56a686ffbe6cde886772ad2`.
- GitHub Actions run `29973841543` passed sync, Ruff, Pyright, and `gitleaks`, then full pytest exposed a collection-only conflict because two non-package test directories both contained `test_service.py`.
- Read-only diagnostic run `29973878507` confirmed the pytest import mismatch. The verification test was renamed to `test_verification_service.py`; no production behavior changed.
- Core Task 9 implementation head: `3421968914514d99c213baa97f193cf4baa71dfa`.
- GitHub Actions run `29973970401` passed frozen sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy, detect-secrets, and `gitleaks`.

### Review-added request-metadata linkage regression

- Final review identified a meaningful integrity gap: a canonically rewritten retrieval manifest could change its instrument while persisted provider request metadata still named the original symbol.
- Clean formatted regression head: `098e82aff54c60b9f915539ed4d789f47053fdd0`.
- GitHub Actions RED run `29974283509` passed sync, Ruff format, Ruff lint, strict Pyright, and `gitleaks`, then failed pytest.
- Focused diagnostic run `29974323631` observed the exact expected failure: `Failed: DID NOT RAISE MarketDataError` for mismatched manifest instrument versus persisted request parameters.
- The minimal correction validates the exact sorted Binance request parameter set (`symbol`, `interval`, `startTime`, `endTime`, `limit`) against the manifest and current cursor, validates bounded canonical limit text, requires each page to begin at its requested cursor, requires forward cursor progress, rejects retrieval-time reversal, rejects pages after a terminal guard, and rejects uncovered requested windows.
- Metadata GREEN run `29974466041` passed repository-pinned Ruff, strict Pyright, and the complete pytest suite, producing bot-authored implementation head `ab38d6e2288c9073dc8edfa552727296fc762670` and removing its temporary workflows.
- Final clean connector-authored implementation head: `acc5b0c2215046a4539ad2e7862f59073552b000`.
- Final implementation CI run: `29974519569`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.

### Verified behavior and scope

- `ReplayService` has no provider field or provider constructor parameter. Integration coverage disables `urllib.request.urlopen` and `socket.create_connection`; replay still completes from stored evidence.
- Replay first verifies canonical retrieval-manifest bytes and recomputes every listed response-body SHA-256 before any normalization.
- Replay cross-checks persisted Binance request identity, interval, bounded window, cursor, and limit against the retrieval manifest, then reuses the exact normalizer, completion filter, sequence validator, and deterministic canonical writer.
- Equivalent raw runs reproduce identical canonical JSONL, deterministic manifest bytes, and dataset ID while retaining separate run-specific provenance receipts.
- `VerificationService` independently parses persisted canonical JSONL, manifest, and provenance; recomputes raw reconstruction, canonical bytes, canonical SHA-256, dataset ID, deterministic manifest bytes, retrieval-manifest SHA-256, provenance linkage, continuity, and completed state.
- Tampering coverage includes raw response bytes, retrieval-manifest bytes, canonical JSONL, deterministic dataset manifest, provenance linkage, request-metadata identity/window mismatch, and missing provenance. Every tested case fails closed.
- The net Task 9 diff contains only replay, verification, the exact retrieval-manifest serializer/reader extension in local immutable storage, and four Task 9 test modules. Temporary workflows, trigger files, placeholders, credentials, private endpoints, strategy, signal, order, and execution behavior are absent.

### Remaining trust boundaries

- The Task 8 cross-store publication limitation remains: verification detects missing or inconsistent canonical/provenance artifacts but cannot roll back files after a storage failure once publication has begun.
- `RawPage.retrieved_at` and `DatasetProvenance.created_at` are informational timestamps, not externally signed timestamps. Verification enforces their schema, UTC/domain validity, deterministic encoding, ordering where applicable, and all derived linkage fields, but cannot prove a valid rewritten informational timestamp against an external authority. These timestamps do not affect canonical JSONL or dataset identity. Stronger adversarial timestamp authenticity would require signatures or an external append-only audit anchor.
- Final Task 9 evidence was observed on GitHub-hosted Ubuntu. Fresh Windows-local verification remains required at the operator checkpoint and final exact-head milestone verification.

## Task 10 — Safe command-line interface

### RED phase

- Task base: `4fa92c0363337d112efe15b9762476020286f724`.
- Test-only RED head: `6347a16307a690f12d946eb3458a905e8bb1d163`.
- GitHub Actions RED run: `29975592248`.
- Frozen dependency sync, Ruff format, Ruff lint, and `gitleaks` passed; strict Pyright failed after the intentionally absent `gemini_trading.cli` package was imported by the new unit and acceptance tests. Pytest and later quality steps were skipped.
- Read-only diagnostic run `29975654083` exported the strict-Pyright output. Missing CLI imports caused the RED failure and cascading unknown types; no production CLI or project script existed.
- The RED suite required explicit ingest identity/window/root arguments, curated interval rejection before provider construction, strict ISO `Z` timestamps, runtime-policy evaluation before provider construction, compact safe JSON success and failure output, exit code 2 for `MarketDataError`, no traceback or raw body leakage, the installed project script, all three command surfaces, and live-mode rejection before network construction.

### GREEN phase and remediation

- Initial implementation head: `1c91fae90b4e321bae5b6daf1cecddc748ec4f89`.
- `pyproject.toml` registered `gemini-trading = "gemini_trading.cli.main:main"`. Frozen sync continued to pass without a lockfile content change because the console-script metadata did not alter the resolved dependency graph.
- GitHub Actions run `29975975874` passed sync and Ruff, then strict Pyright exposed five test-only JSON/TOML narrowing diagnostics. Production CLI typing was clean.
- Diagnostic run `29976025662` confirmed those exact five test-side diagnostics.
- Cleanup run `29976161676` failed before committing. No result from that run was accepted.
- Read-only diagnostic run `29976235955` passed Ruff and strict Pyright and showed 218 tests passing, with two focused failures caused by a brittle assertion that treated `": "` inside human error-message strings as JSON formatting whitespace.
- Finalize run `29976327677` replaced that assertion with exact compact JSON reserialization, then passed repository-pinned Ruff, strict Pyright, the focused CLI/regression suite, the complete pytest suite, and both installed help commands. It produced bot-authored clean head `5912ba0083a1d758d0f8970719c2e4c6b156c90c` and removed its temporary workflow.
- Final clean connector-authored implementation head: `0d4ea68bdb2accce72aac41fac93261dc1bc4980`.
- Exact-head GitHub Actions run: `29976430073`.
- Observed `quality` result: passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy validation, and detect-secrets.
- Observed `gitleaks` result: passed.

### Verified behavior and scope

- The installed command surface is `gemini-trading market-data ingest|replay|verify`.
- Ingest requires `--symbol`, `--base-asset`, `--quote-asset`, `--interval`, `--start`, `--end`, and `--output-root`; replay requires `--run-id` and `--output-root`; verify requires `--dataset-id`, `--run-id`, and `--output-root`.
- Approved intervals are sourced directly from `Timeframe`; invalid values are rejected by `argparse` before any provider is constructed.
- Ingest timestamps must be ISO-8601 UTC values ending in `Z`.
- `load_runtime_policy()` runs after local argument/domain validation and before `BinanceSpotProvider()` construction. Prohibited live mode returns safe JSON with exit code 2 and constructs no provider.
- Successful operational commands emit one compact, sorted JSON object containing only safe identifiers, counts, checks, and paths relative to the configured output root. Absolute operator filesystem paths are not emitted.
- `MarketDataError`, CLI usage errors, and unsafe execution modes emit one compact JSON error object to stderr with exit code 2. Unexpected exceptions emit only a generic `InternalError`; tracebacks, raw response bodies, environment dumps, credentials, and authorization data are not printed.
- Replay and verify use only `LocalImmutableStore`, `ReplayService`, and `VerificationService`; no provider is constructed for those commands.
- Standard `--help` output remains human-readable argparse text and exits successfully; operational success/failure results use compact JSON.
- The Task 10 net change is limited to the CLI package, project script metadata, and its unit/acceptance tests. No strategy, signal, order, private endpoint, credential, or exchange-submission behavior was introduced.

### Remaining trust boundaries

- The CLI currently targets the local immutable filesystem adapter. Mobile-triggered GitHub workflow dispatch and self-hosted-runner integration are outside this milestone and should be added only after Task 12 completes.
- Windows-local command execution remains required at the final operator checkpoint; Task 10 evidence was observed on GitHub-hosted Ubuntu.
