from datetime import UTC, datetime, timedelta
from pathlib import Path

from gemini_trading.economics.data.asof_v2 import latest_visible_vintages_v2
from gemini_trading.economics.data.dataset_v2 import write_economic_bundle_v2
from gemini_trading.economics.data.replay_v2 import replay_economic_bundle_v2
from tests.unit.economics.data import test_dataset_v2 as fixtures


def _materialize_raw(root: Path, dataset) -> None:  # type: ignore[no-untyped-def]
    payloads = {
        "availability-1": fixtures._AVAIL_1,
        "event-1": fixtures._EVENT_1,
        "observation-1": fixtures._OBS_1,
        "availability-2": fixtures._AVAIL_2,
        "event-2": fixtures._EVENT_2,
        "observation-2": fixtures._OBS_2,
    }
    for receipt in dataset.raw_inventory.receipts:
        target = root / receipt.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[receipt.receipt_id])


def test_provider_free_replay_reproduces_identity_and_vintages(tmp_path: Path) -> None:
    dataset = fixtures._build_revision()
    raw_source = tmp_path / "source"
    bundle = tmp_path / "bundle"
    _materialize_raw(raw_source, dataset)
    write_economic_bundle_v2(bundle, dataset, raw_source_root=raw_source)

    replayed = replay_economic_bundle_v2(bundle)
    assert replayed.manifest.dataset_id == dataset.manifest.dataset_id
    assert tuple(row.version_id for row in replayed.observations) == tuple(
        row.version_id for row in dataset.observations
    )

    first_release = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    revision_release = datetime(2026, 9, 12, 12, 30, tzinfo=UTC)
    before = latest_visible_vintages_v2(replayed, first_release - timedelta(microseconds=1))
    at_initial = latest_visible_vintages_v2(replayed, first_release)
    at_revision = latest_visible_vintages_v2(replayed, revision_release)
    assert before == ()
    assert str(at_initial[0].value) == "324.100"
    assert str(at_revision[0].value) == "324.200"
