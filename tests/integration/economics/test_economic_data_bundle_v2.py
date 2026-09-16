from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tests.support.economic_v2 import (
    AVAIL_1,
    AVAIL_2,
    DEFAULT_RAW_PAYLOADS,
    EVENT_1,
    EVENT_2,
    OBS_1,
    OBS_2,
    event,
    evidence,
    inventory,
    materialize_raw,
    observation,
    registry,
)

from gemini_trading.economics.data.asof_v2 import latest_visible_vintages_v2
from gemini_trading.economics.data.dataset_v2 import (
    EconomicDatasetV2,
    build_economic_dataset_v2,
    write_economic_bundle_v2,
)
from gemini_trading.economics.data.publication import PublicationSequence, RevisionClass
from gemini_trading.economics.data.replay_v2 import replay_economic_bundle_v2
from gemini_trading.economics.data.verification_v2 import verify_economic_bundle_v2

_AVAIL_3 = b"availability-3"
_EVENT_3 = b"event-3"
_OBS_3 = b"observation-3"


def _build_history() -> tuple[
    EconomicDatasetV2,
    tuple[datetime, datetime, datetime],
]:
    t1 = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    t2 = datetime(2026, 9, 12, 12, 30, tzinfo=UTC)
    t3 = datetime(2026, 9, 13, 12, 30, tzinfo=UTC)
    initial = observation()
    core = observation(
        "macro.us.cpi.core",
        value=Decimal("330.200"),
        raw=OBS_1,
    )
    revised_evidence = evidence("evidence-2", "event-2", t2, AVAIL_2)
    revised_event = event(
        "event-2",
        "evidence-2",
        t2,
        EVENT_2,
        PublicationSequence.ROUTINE_REVISION,
        RevisionClass.ROUTINE_REVISION,
        "event-1",
    )
    revised = observation(
        event_id="event-2",
        evidence_id="evidence-2",
        when=t2,
        raw=OBS_2,
        value=Decimal("324.200"),
        sequence=PublicationSequence.ROUTINE_REVISION,
        revision=RevisionClass.ROUTINE_REVISION,
        predecessor_version_id=initial.version_id,
    )
    corrected_evidence = evidence("evidence-3", "event-3", t3, _AVAIL_3)
    corrected_event = event(
        "event-3",
        "evidence-3",
        t3,
        _EVENT_3,
        PublicationSequence.CORRECTION,
        RevisionClass.CORRECTION,
        "event-2",
    )
    corrected = observation(
        event_id="event-3",
        evidence_id="evidence-3",
        when=t3,
        raw=_OBS_3,
        value=Decimal("324.250"),
        sequence=PublicationSequence.CORRECTION,
        revision=RevisionClass.CORRECTION,
        predecessor_version_id=revised.version_id,
    )
    raw_inventory = inventory(
        ("availability-1", AVAIL_1),
        ("event-1", EVENT_1),
        ("observation-1", OBS_1),
        ("availability-2", AVAIL_2),
        ("event-2", EVENT_2),
        ("observation-2", OBS_2),
        ("availability-3", _AVAIL_3),
        ("event-3", _EVENT_3),
        ("observation-3", _OBS_3),
    )
    dataset = build_economic_dataset_v2(
        registry=registry(),
        observations=(initial, core, revised, corrected),
        publication_events=(event(), revised_event, corrected_event),
        availability_evidence=(evidence(), revised_evidence, corrected_evidence),
        raw_inventory=raw_inventory,
    )
    return dataset, (t1, t2, t3)


def test_v2_bundle_replays_initial_revision_and_correction(tmp_path: Path) -> None:
    dataset, (t1, t2, t3) = _build_history()
    source = tmp_path / "source"
    bundle = tmp_path / "bundle"
    payloads = dict(DEFAULT_RAW_PAYLOADS)
    payloads.update(
        {
            "availability-3": _AVAIL_3,
            "event-3": _EVENT_3,
            "observation-3": _OBS_3,
        }
    )
    materialize_raw(source, dataset, payloads=payloads)
    write_economic_bundle_v2(bundle, dataset, raw_source_root=source)
    verified = verify_economic_bundle_v2(bundle)
    replayed = replay_economic_bundle_v2(bundle)

    assert verified.dataset_id == dataset.manifest.dataset_id
    before = latest_visible_vintages_v2(replayed, t1 - timedelta(microseconds=1))
    at_initial = latest_visible_vintages_v2(replayed, t1)
    at_revision = latest_visible_vintages_v2(replayed, t2)
    at_correction = latest_visible_vintages_v2(replayed, t3)
    assert before == ()
    assert sorted(str(row.value) for row in at_initial) == ["324.100", "330.200"]
    assert sorted(str(row.value) for row in at_revision) == ["324.200", "330.200"]
    assert sorted(str(row.value) for row in at_correction) == ["324.250", "330.200"]
    corrected = next(row for row in at_correction if row.series_id == "macro.us.cpi")
    assert corrected.revision_class is RevisionClass.CORRECTION
