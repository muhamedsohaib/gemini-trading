"""Apply the permanent sealed dataset v4 documentation migration."""

from pathlib import Path


readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
old_readme = (
    "The two-stage GitHub Actions implementation for the fixed BTCUSDT window "
    "`[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` uses `candle-dataset-v3`, "
    "`exchange-closure-manifest-v2`, one exact partial-candle exclusion bound to "
    "provider-row SHA-256 `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775`, "
    "seven fully absent opens, and two deterministic continuous segments. It preserves "
    "raw evidence, fabricates no candles, and resets all research dependencies at the "
    "segment boundary. There is no real historical Candidate result until the dataset "
    "and study workflows run against an approved exact merged-main SHA and the downloaded "
    "artifacts independently verify. No durable profitability, execution readiness, or "
    "capital authorization is claimed.\n"
)
new_readme = (
    "The two-stage GitHub Actions implementation for the fixed BTCUSDT window "
    "`[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` uses `candle-dataset-v4`, "
    "`exchange-closure-manifest-v3`, 20 exact partial-candle exclusions, 16 fully absent "
    "opens, 36 unavailable canonical `4h` slots, 21 deterministic continuous segments, "
    "and 18,582 completed canonical candles. `sealed-dataset-handoff-v4` binds every "
    "ordered closure ID and excluded provider-row SHA-256. Raw evidence is immutable, no "
    "candle is fabricated, and all research dependencies reset at segment boundaries. "
    "Earlier v1-v3 datasets and handoffs are invalid for this revised study. There is no "
    "real historical Candidate result until a completely new Stage 1 v4 workflow runs "
    "from an approved exact merged-main SHA, its downloaded artifact independently "
    "verifies, and the repository owner explicitly approves it before Stage 2. No durable "
    "profitability, execution readiness, or capital authorization is claimed.\n"
)
if readme.count(old_readme) != 1:
    raise SystemExit("unexpected README sealed validation paragraph")
readme_path.write_text(readme.replace(old_readme, new_readme, 1), encoding="utf-8")


guide_path = Path("docs/operations/sealed-btcusdt-historical-validation.md")
guide = guide_path.read_text(encoding="utf-8")
section_start = guide.index("## Verified exchange-closure and partial-candle evidence\n")
section_end = guide.index("## Workflows\n", section_start)
new_section = '''## Verified exchange-closure and partial-candle evidence

The fixed historical window contains 20 independently verified Binance Spot interruption declarations in `config/market-data/sealed-btcusdt-4h-exchange-closures.json` using `exchange-closure-manifest-v3`.

The immutable fixed identity is:

- 20 structurally valid partial-candle provider rows;
- 16 fully absent canonical opens;
- 36 unavailable canonical `4h` slots in total;
- 20 ordered exact exclusions in `candle-exclusion-manifest-v1`;
- 21 maximal continuous segments in `candle-segment-manifest-v1`;
- 18,582 completed canonical candles in `candle-dataset-v4`;
- first canonical open `2018-01-01T00:00:00Z`;
- last canonical open `2026-06-30T20:00:00Z`;
- segment boundaries `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`.

A closure may contain zero fully missing opens. In that case the partial candle is unavailable, `fully_missing_start` equals `resumed_open`, and `unavailable_candle_count` remains one. Every declaration must satisfy exact timeframe arithmetic and must match exactly one immutable provider row by open time, actual close, expected close, normalized values, page location, row location, and SHA-256.

Raw provider pages and excluded rows remain byte-for-byte immutable. The pipeline never inserts, forward-fills, interpolates, zero-fills, repairs, pads, or otherwise fabricates a candle. Missing, duplicate, changed, reordered, shifted, additional, overlong, undeclared, overlapping, touching, or unused evidence fails closed.

`candle-dataset-v4` binds canonical candle bytes, closure-manifest bytes, exclusion-manifest bytes, and segment-manifest bytes. `sealed-dataset-handoff-v4` additionally binds all ordered `(closure_id, provider_row_sha256)` pairs, the exact counts, all segment boundaries, the first and last opens, replay completion, independent verification, and the sorted artifact inventory root.

Features, labels, folds, strategy schedules, simulator orders, positions, returns, and final-test access cannot cross a segment boundary. Feature warm-up restarts after every interruption. Label outcomes crossing a boundary are omitted. A noncash account or active order at a boundary is a terminal validation failure; no synthetic liquidation is allowed. Every approved interruption precedes the final 18-month test. Any interruption intersecting that final partition requires a new written design gate.

The fixed Stage 1 commands are:

```text
gemini-trading research dataset-ingest --project-root <repo> --output-root <artifact-root>
gemini-trading research dataset-replay --run-id <retrieval-run-id> --output-root <artifact-root>
gemini-trading research dataset-verify --dataset-id <dataset-id> --run-id <retrieval-run-id> --output-root <artifact-root>
```

There is no operator-provided closure or exclusion path, environment override, dispatch input, or remote policy source. Earlier v1-v3 datasets and handoffs are invalid for the revised study. A completely new Stage 1 v4 run is mandatory after protected merge and exact-main verification.

'''
guide = guide[:section_start] + new_section + guide[section_end:]
old_stage1_start = guide.index("Record the following exact Stage 1 evidence on Issue #22:\n")
old_stage1_end = guide.index("Stage 2 remains prohibited", old_stage1_start)
new_stage1 = '''Record the following exact Stage 1 evidence on Issue #22:

- source commit;
- workflow run ID and attempt;
- artifact name and artifact ID;
- retrieval run ID;
- dataset ID and `candle-dataset-v4` schema;
- closure-manifest path, SHA-256, and `exchange-closure-manifest-v3` schema;
- exclusion-manifest path and SHA-256;
- segment-manifest path and SHA-256;
- closure count `20`, exclusion count `20`, and segment count `21`;
- all ordered closure IDs and excluded provider-row SHA-256 identities;
- all segment boundary indices `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`;
- unavailable canonical-slot count `36` and fully absent-open count `16`;
- candle count `18,582`;
- first open `2018-01-01T00:00:00Z` and last open `2026-06-30T20:00:00Z`;
- inventory root SHA-256;
- byte-identical replay result;
- independent verification result.

'''
guide = guide[:old_stage1_start] + new_stage1 + guide[old_stage1_end:]
guide_path.write_text(guide, encoding="utf-8")
