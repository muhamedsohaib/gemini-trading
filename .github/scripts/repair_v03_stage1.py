from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one repair anchor in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1))


# Register isolated v0.3 Stage 1 CLI shapes and route them through the v0.3 handler.
main = "src/gemini_trading/cli/main.py"
replace_once(
    main,
    '''    dataset_ingest.add_argument("--project-root", required=True)\n    dataset_ingest.add_argument("--output-root", required=True)\n\n    dataset_replay = research_commands.add_parser(\n''',
    '''    dataset_ingest.add_argument("--project-root", required=True)\n    dataset_ingest.add_argument("--output-root", required=True)\n\n    dataset_v0_3_ingest = research_commands.add_parser(\n        "dataset-v0-3-ingest", help="ingest the fixed Candidate v0.3 development dataset"\n    )\n    dataset_v0_3_ingest.add_argument("--project-root", required=True)\n    dataset_v0_3_ingest.add_argument("--output-root", required=True)\n\n    dataset_replay = research_commands.add_parser(\n''',
)
replace_once(
    main,
    '''    handoff.add_argument("--workflow-run-attempt", required=True)\n    handoff.add_argument("--output-root", required=True)\n\n    prepare = research_commands.add_parser(\n''',
    '''    handoff.add_argument("--workflow-run-attempt", required=True)\n    handoff.add_argument("--output-root", required=True)\n\n    handoff_v0_3 = research_commands.add_parser(\n        "strategy-v0-3-handoff", help="seal one verified Candidate v0.3 Stage 1 handoff"\n    )\n    handoff_v0_3.add_argument("--run-id", required=True)\n    handoff_v0_3.add_argument("--dataset-id", required=True)\n    handoff_v0_3.add_argument("--source-commit", required=True)\n    handoff_v0_3.add_argument("--workflow-run-id", required=True)\n    handoff_v0_3.add_argument("--workflow-run-attempt", required=True)\n    handoff_v0_3.add_argument("--project-root", required=True)\n    handoff_v0_3.add_argument("--output-root", required=True)\n\n    prepare = research_commands.add_parser(\n''',
)
replace_once(
    main,
    '''            candidate_v0_3_commands = {\n                "strategy-v0-3-qualify",\n                "strategy-v0-3-verify-qualification",\n                "strategy-v0-3-create-prospective-seal",\n            }\n''',
    '''            candidate_v0_3_commands = {\n                "dataset-v0-3-ingest",\n                "strategy-v0-3-handoff",\n                "strategy-v0-3-qualify",\n                "strategy-v0-3-verify-qualification",\n                "strategy-v0-3-create-prospective-seal",\n            }\n''',
)

# Extend the v0.3 CLI handler without widening the legacy historical-validation surface.
cli = "src/gemini_trading/cli/candidate_v0_3.py"
replace_once(
    cli,
    '''from gemini_trading.cli.strategy import load_candidate_strategy_config\nfrom gemini_trading.data.storage.local_immutable import LocalImmutableStore\nfrom gemini_trading.research.dataset_reader import load_verified_dataset\n''',
    '''from gemini_trading.cli.strategy import load_candidate_strategy_config\nfrom gemini_trading.data.ingestion.service import IngestionService\nfrom gemini_trading.data.providers.binance_spot import BinanceSpotProvider\nfrom gemini_trading.data.storage.local_immutable import LocalImmutableStore\nfrom gemini_trading.domain.dataset import RetrievalRequest\nfrom gemini_trading.research.dataset_reader import load_verified_dataset\n''',
)
replace_once(
    cli,
    '''from gemini_trading.strategy.errors import DatasetHandoffError, StudyArtifactError\nfrom gemini_trading.strategy.handoff import load_dataset_handoff, verify_dataset_handoff\n''',
    '''from gemini_trading.strategy.errors import DatasetHandoffError, StudyArtifactError\nfrom gemini_trading.strategy.v0_3_stage1 import (\n    build_v0_3_closure_manifest,\n    create_v0_3_dataset_handoff,\n    load_v0_3_dataset_handoff,\n    verify_v0_3_dataset_handoff,\n)\n''',
)
replace_once(
    cli,
    '''def _qualification_root(handoff_path: Path, output_root: Path) -> Path:\n''',
    '''def _safe_relative(path: Path, root: Path) -> str:\n    resolved_root = root.resolve(strict=False)\n    try:\n        return path.resolve(strict=False).relative_to(resolved_root).as_posix()\n    except ValueError:\n        raise DatasetHandoffError("Candidate v0.3 result path escaped the output root") from None\n\n\ndef _qualification_root(handoff_path: Path, output_root: Path) -> Path:\n''',
)
replace_once(
    cli,
    '''def _qualify(arguments: argparse.Namespace) -> dict[str, object]:\n''',
    '''def _ingest_stage1(arguments: argparse.Namespace) -> dict[str, object]:\n    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)\n    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)\n    closure_manifest, closure_bytes = build_v0_3_closure_manifest(project_root)\n    request = RetrievalRequest(\n        instrument=closure_manifest.instrument,\n        timeframe=closure_manifest.timeframe,\n        start_time=closure_manifest.start_time,\n        end_time=closure_manifest.end_time,\n    )\n    store = LocalImmutableStore(output_root)\n    result = IngestionService(\n        provider=BinanceSpotProvider(),\n        raw_store=store,\n        canonical_store=store,\n        closure_manifest=closure_manifest,\n        closure_manifest_bytes=closure_bytes,\n    ).ingest(request)\n    return _research_only(\n        {\n            "status": "completed",\n            "run_id": result.run_id,\n            "dataset_id": result.dataset_id,\n            "raw_page_count": result.raw_page_count,\n            "candle_count": result.candle_count,\n            "paths": {\n                name: _safe_relative(path, output_root) for name, path in result.paths\n            },\n        }\n    )\n\n\ndef _handoff_stage1(arguments: argparse.Namespace) -> dict[str, object]:\n    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)\n    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)\n    source_commit = _argument(arguments, "source_commit")\n    if resolve_clean_git_commit(project_root) != source_commit:\n        raise DatasetHandoffError("Candidate v0.3 Stage 1 source commit mismatch")\n    manifest, path = create_v0_3_dataset_handoff(\n        project_root=project_root,\n        output_root=output_root,\n        run_id=_argument(arguments, "run_id"),\n        dataset_id=_argument(arguments, "dataset_id"),\n        source_commit=source_commit,\n        workflow_run_id=_positive_integer(arguments, "workflow_run_id"),\n        workflow_run_attempt=_positive_integer(arguments, "workflow_run_attempt"),\n    )\n    return _research_only(\n        {\n            "dataset_id": manifest.dataset_id,\n            "handoff_path": _safe_relative(path, output_root),\n            "inventory_root_sha256": manifest.inventory_root_sha256,\n            "status": "verified",\n        }\n    )\n\n\ndef _qualify(arguments: argparse.Namespace) -> dict[str, object]:\n''',
)
replace_once(
    cli,
    '''        handoff = load_dataset_handoff(handoff_path.read_bytes())\n''',
    '''        handoff = load_v0_3_dataset_handoff(handoff_path.read_bytes())\n''',
)
replace_once(
    cli,
    '''    verify_dataset_handoff(\n        handoff,\n        artifact_root,\n        expected_commit=code_commit,\n        expected_dataset_id=handoff.dataset_id,\n        expected_run_id=handoff.workflow_run_id,\n    )\n''',
    '''    verify_v0_3_dataset_handoff(\n        handoff,\n        artifact_root,\n        project_root=project_root,\n        expected_commit=code_commit,\n        expected_dataset_id=handoff.dataset_id,\n        expected_run_id=handoff.workflow_run_id,\n    )\n''',
)
replace_once(
    cli,
    '''    return verify_candidate_v0_3_qualification(\n        output_root,\n        qualification_id,\n        expected_commit=code_commit,\n    )\n''',
    '''    return verify_candidate_v0_3_qualification(\n        output_root,\n        qualification_id,\n        expected_commit=code_commit,\n        project_root=project_root,\n    )\n''',
)
replace_once(
    cli,
    '''    command = _argument(arguments, "research_command")\n    if command == "strategy-v0-3-qualify":\n''',
    '''    command = _argument(arguments, "research_command")\n    if command == "dataset-v0-3-ingest":\n        return _ingest_stage1(arguments)\n    if command == "strategy-v0-3-handoff":\n        return _handoff_stage1(arguments)\n    if command == "strategy-v0-3-qualify":\n''',
)

# Bind qualification execution statically to the v0.3-specific handoff type.
execution = "src/gemini_trading/strategy/qualification_execution_v0_3.py"
replace_once(
    execution,
    '''from gemini_trading.strategy.handoff import DatasetHandoffManifest\n''',
    '''from gemini_trading.strategy.v0_3_stage1 import V03DatasetHandoffManifest\n''',
)
replace_once(
    execution,
    '''    handoff: DatasetHandoffManifest,\n''',
    '''    handoff: V03DatasetHandoffManifest,\n''',
)

# Make independent qualification verification rebuild the isolated Stage 1 identity.
verification = "src/gemini_trading/strategy/qualification_verification_v0_3.py"
replace_once(
    verification,
    '''from gemini_trading.strategy.handoff import load_dataset_handoff, verify_dataset_handoff\n''',
    '''from gemini_trading.strategy.v0_3_stage1 import (\n    load_v0_3_dataset_handoff,\n    verify_v0_3_dataset_handoff,\n)\n''',
)
replace_once(
    verification,
    '''    *,\n    expected_commit: str,\n) -> V03QualificationArtifacts:\n''',
    '''    *,\n    expected_commit: str,\n    project_root: Path,\n) -> V03QualificationArtifacts:\n''',
)
replace_once(
    verification,
    '''        handoff = load_dataset_handoff(handoff_path.read_bytes())\n''',
    '''        handoff = load_v0_3_dataset_handoff(handoff_path.read_bytes())\n''',
)
replace_once(
    verification,
    '''    verify_dataset_handoff(\n        handoff,\n        Path(root),\n        expected_commit=expected_commit,\n        expected_dataset_id=artifacts.context.dataset_id,\n        expected_run_id=artifacts.context.dataset_run_id,\n    )\n''',
    '''    verify_v0_3_dataset_handoff(\n        handoff,\n        Path(root),\n        project_root=project_root,\n        expected_commit=expected_commit,\n        expected_dataset_id=artifacts.context.dataset_id,\n        expected_run_id=artifacts.context.dataset_run_id,\n    )\n''',
)

# Qualification workflow must verify the new handoff, not the frozen legacy July-1 handoff.
workflow = ".github/workflows/candidate-v0.3-qualification.yml"
replace_once(
    workflow,
    '''          from gemini_trading.strategy.handoff import load_dataset_handoff, verify_dataset_handoff\n''',
    '''          from gemini_trading.strategy.v0_3_stage1 import (\n              load_v0_3_dataset_handoff,\n              verify_v0_3_dataset_handoff,\n          )\n''',
)
replace_once(
    workflow,
    '''          handoff = load_dataset_handoff(path.read_bytes())\n          verify_dataset_handoff(\n              handoff,\n              root,\n              expected_commit=os.environ["EXPECTED_COMMIT"],\n''',
    '''          handoff = load_v0_3_dataset_handoff(path.read_bytes())\n          verify_v0_3_dataset_handoff(\n              handoff,\n              root,\n              project_root=Path(os.environ["GITHUB_WORKSPACE"]),\n              expected_commit=os.environ["EXPECTED_COMMIT"],\n''',
)
