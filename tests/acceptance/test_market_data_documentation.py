from pathlib import Path

_PROJECT_ROOT = Path(__file__).parents[2]
_README = _PROJECT_ROOT / "README.md"
_ADR = _PROJECT_ROOT / "docs" / "architecture" / "adr" / "0002-market-data-core.md"
_OPERATOR_GUIDE = _PROJECT_ROOT / "docs" / "operations" / "binance-market-data.md"


def _required_text(path: Path) -> str:
    assert path.is_file(), f"required documentation is missing: {path.relative_to(_PROJECT_ROOT)}"
    return path.read_text(encoding="utf-8")


def test_market_data_documentation_covers_the_verified_operator_contract() -> None:
    readme = _required_text(_README)
    adr = _required_text(_ADR)
    operator = _required_text(_OPERATOR_GUIDE)
    combined = "\n".join((readme, adr, operator))

    for command in (
        "gemini-trading market-data ingest",
        "gemini-trading market-data replay",
        "gemini-trading market-data verify",
    ):
        assert command in combined

    for interval in ("1m", "5m", "15m", "1h", "4h", "1d", "1w"):
        assert f"`{interval}`" in operator

    for required_contract in (
        "[start, end)",
        "close_time < server_time",
        "data/raw/binance_spot/<run_id>/",
        "data/canonical/<dataset_id>/",
        "candle-dataset-v1",
        "sha256(utf8(schema_version) + b\"\\n\" + canonical_jsonl_bytes)",
        "GEMINI_TRADING_RUN_LIVE_API_TESTS=1",
    ):
        assert required_contract in combined

    assert "replay performs no network access" in combined.lower()
    assert "research and paper only" in combined.lower()
    assert "live mode is rejected" in combined.lower()
    assert "issue #7" in combined.lower()
    assert "issue #8" in combined.lower()
    assert "does not establish strategy profitability" in combined.lower()

    assert "ADR 0002" in adr
    assert "Database-backed ingestion is deferred" in adr
    assert "cross-store rollback" in operator
    assert "informational timestamps" in operator


def test_readme_links_the_market_data_architecture_and_operator_guides() -> None:
    readme = _required_text(_README)

    assert "docs/architecture/adr/0002-market-data-core.md" in readme
    assert "docs/operations/binance-market-data.md" in readme
    assert "reports/verification/market-data-core-final.md" in readme
