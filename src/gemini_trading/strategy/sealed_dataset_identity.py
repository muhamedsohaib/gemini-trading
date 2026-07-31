"""Fixed fail-closed identity for the sealed BTCUSDT dataset v4 workflow."""

from __future__ import annotations

from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import DatasetHandoffManifest, ExcludedProviderRow

EXPECTED_HANDOFF_SCHEMA = "sealed-dataset-handoff-v4"
EXPECTED_DATASET_SCHEMA = "candle-dataset-v4"
EXPECTED_CLOSURE_MANIFEST_SHA256 = (
    "a028bd367ac51b85cca3fab24a28b794fc35ea2d9f73b6f39d681eafa66a31f5"  # pragma: allowlist secret
)
EXPECTED_COUNTS = (20, 20, 21)
EXPECTED_CANDLE_COUNT = 18_582
EXPECTED_FIRST_OPEN_TIME = "2018-01-01T00:00:00Z"
EXPECTED_LAST_OPEN_TIME = "2026-06-30T20:00:00Z"
_EXPECTED_ROW_PAIRS = (
    (
        "binance-spot-infrastructure-maintenance-2018-01-04",
        "ce5df946e724e509699e24166fcd96bd566c48de7090b3a092aaa324bd73c426",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2018-02-08",
        "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2018-06-26",
        "31d7e347e1830772a39ab0bdf78e09af6ff3f3735cad745916fe32e6fe0fd557",
    ),  # pragma: allowlist secret
    (
        "binance-spot-risk-control-suspension-2018-07-04",
        "1202a2e967f8907eab3917a36f9b5bb440e4ca6647779fdebefd50bcce61b5b8",
    ),  # pragma: allowlist secret
    (
        "binance-spot-emergency-maintenance-2018-10-19",
        "3a06f4a8c191d42bebd2597f7c19932362f4d95f7fe7452f51c268209b629474",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2018-11-14",
        "dd328080cdc59124c3a0467faf719f055dc208a03a229d89dbe0ec403ebf3ee8",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2019-03-12",
        "455bc52eeca4bc7097498742c200d5ecc46019683ed37ea36ed2acb4f3d8478f",
    ),  # pragma: allowlist secret
    (
        "binance-spot-security-upgrade-2019-05-15",
        "1021733a2305723bc1dad0dd8ebd8523fdc36839ef52353018d987429508efad",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2019-08-15",
        "1f68a701351a2ae6917bf4a5d524885416dc7715a704af8e0db52d3938cff876",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2019-11-13",
        "aee4ed92909f4b8e8c957370da2499c928d304374c7db303ffd591a370c2e609",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2019-11-25",
        "2b11ed5d8fe5724c559ce91e5c922b0a98d3ae16a859eec895e128b5e1e9ac54",
    ),  # pragma: allowlist secret
    (
        "binance-spot-market-data-maintenance-2020-02-19",
        "a756811ac8139d621c6fde28980d8019fef535d7f1e17b2d4310b10370d2ac53",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2020-04-25",
        "7c11bd7bff7cd4815615ea6003cb3dbed08b214b78a2bbe722cfe22912592354",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2020-06-28",
        "bbca0d86447c44964449be1ae5bf5968e391cffad1fb16aee136f07369553a01",
    ),  # pragma: allowlist secret
    (
        "binance-spot-matching-engine-maintenance-2020-12-21",
        "b9208db0c003f68d77ffeeb7e9054c348f61ede5840db275f0d5baf84cfdd2c9",
    ),  # pragma: allowlist secret
    (
        "binance-spot-matching-engine-maintenance-2021-02-11",
        "6336454bf83a67e99118f3405c3926c444668028f1c65518d509bdf19eab6cb4",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2021-04-20",
        "bdf24e2e33ecdca4f2d6960f80dd62521e9588e72badd2497857fa4efc521393",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2021-04-25",
        "d033c7c18ec2bc9b3b545a93b7d886e5e3f8c70331ffb07f2cf04fb631108d49",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2021-08-13",
        "82ec6dfd6d5d034bd9dfa6c81a5fdcee87db14a998beb3d9dad6f3dbd860509d",
    ),  # pragma: allowlist secret
    (
        "binance-spot-system-upgrade-2021-09-29",
        "ae05924001aab056ea72c61061f0b75db9aab01ca04ca6db69c7a01f09a99924",
    ),  # pragma: allowlist secret
)
EXPECTED_EXCLUDED_PROVIDER_ROWS = tuple(
    ExcludedProviderRow(closure_id, row_sha256) for closure_id, row_sha256 in _EXPECTED_ROW_PAIRS
)
EXPECTED_CLOSURE_IDS = tuple(item.closure_id for item in EXPECTED_EXCLUDED_PROVIDER_ROWS)
EXPECTED_BOUNDARIES = (
    18,
    227,
    1047,
    1092,
    1733,
    1887,
    2593,
    2975,
    3524,
    4062,
    4133,
    4650,
    5042,
    5425,
    6483,
    6791,
    7198,
    7228,
    7886,
    8168,
)


def _mismatch(field_name: str) -> None:
    raise DatasetHandoffError(f"fixed sealed dataset identity mismatch: {field_name}")


def assert_fixed_sealed_dataset_identity(handoff: DatasetHandoffManifest) -> None:
    """Require the exact approved Stage 1 and Stage 2 dataset evidence identity."""

    checks: tuple[tuple[bool, str], ...] = (
        (handoff.schema_version == EXPECTED_HANDOFF_SCHEMA, "handoff schema"),
        (handoff.dataset_schema_version == EXPECTED_DATASET_SCHEMA, "dataset schema"),
        (
            handoff.closure_manifest_sha256 == EXPECTED_CLOSURE_MANIFEST_SHA256,
            "closure manifest SHA-256",
        ),
        (
            (handoff.closure_count, handoff.exclusion_count, handoff.segment_count)
            == EXPECTED_COUNTS,
            "closure/exclusion/segment counts",
        ),
        (handoff.closure_ids == EXPECTED_CLOSURE_IDS, "closure IDs"),
        (
            handoff.excluded_provider_rows == EXPECTED_EXCLUDED_PROVIDER_ROWS,
            "excluded provider rows",
        ),
        (handoff.segment_boundary_indices == EXPECTED_BOUNDARIES, "segment boundaries"),
        (handoff.candle_count == EXPECTED_CANDLE_COUNT, "candle count"),
        (handoff.first_open_time == EXPECTED_FIRST_OPEN_TIME, "first open time"),
        (handoff.last_open_time == EXPECTED_LAST_OPEN_TIME, "last open time"),
        (handoff.replay_status == "completed", "replay status"),
        (handoff.verification_status == "verified", "verification status"),
    )
    for valid, field_name in checks:
        if not valid:
            _mismatch(field_name)


__all__ = [
    "EXPECTED_BOUNDARIES",
    "EXPECTED_CANDLE_COUNT",
    "EXPECTED_CLOSURE_IDS",
    "EXPECTED_CLOSURE_MANIFEST_SHA256",
    "EXPECTED_COUNTS",
    "EXPECTED_DATASET_SCHEMA",
    "EXPECTED_EXCLUDED_PROVIDER_ROWS",
    "EXPECTED_FIRST_OPEN_TIME",
    "EXPECTED_HANDOFF_SCHEMA",
    "EXPECTED_LAST_OPEN_TIME",
    "assert_fixed_sealed_dataset_identity",
]
