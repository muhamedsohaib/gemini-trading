"""Apply the temporary Task 11 Stage 2 workflow migration."""

from pathlib import Path


study_path = Path(".github/workflows/sealed-btcusdt-study.yml")
study = study_path.read_text(encoding="utf-8")
old_import = (
    "          from gemini_trading.strategy.handoff import "
    "load_dataset_handoff, verify_dataset_handoff\n"
)
new_import = old_import + (
    "          from gemini_trading.strategy.sealed_dataset_identity import (\n"
    "              assert_fixed_sealed_dataset_identity,\n"
    "          )\n"
)
if study.count(old_import) != 1:
    raise SystemExit("unexpected Stage 2 handoff import")
study = study.replace(old_import, new_import, 1)
old_checks = '''          if handoff.dataset_schema_version != "candle-dataset-v3":
              raise SystemExit("Stage 2 requires candle-dataset-v3")
          if (handoff.closure_count, handoff.exclusion_count, handoff.segment_count) != (1, 1, 2):
              raise SystemExit("Stage 2 closure, exclusion, and segment count mismatch")
          if handoff.closure_ids != ("binance-spot-system-upgrade-2018-02-08",):
              raise SystemExit("Stage 2 closure identity mismatch")
          if handoff.excluded_provider_row_sha256 != "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775":
              raise SystemExit("Stage 2 excluded provider row mismatch")
          if handoff.segment_boundary_indices != (228,):
              raise SystemExit("Stage 2 segment boundary mismatch")
          if handoff.candle_count != 18617:
              raise SystemExit("Stage 2 candle count mismatch")
'''
new_checks = "          assert_fixed_sealed_dataset_identity(handoff)\n"
if study.count(old_checks) != 1:
    raise SystemExit("unexpected Stage 2 v3 identity checks")
study_path.write_text(study.replace(old_checks, new_checks, 1), encoding="utf-8")
