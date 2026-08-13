"""Top-level safe command-line entry point."""

import argparse
import json
import sys
from collections.abc import Sequence
from typing import NoReturn, TextIO

from gemini_trading.cli.candidate_v0_2 import run_candidate_v0_2
from gemini_trading.cli.candidate_v0_3 import run_candidate_v0_3
from gemini_trading.cli.historical_validation import run_historical_validation
from gemini_trading.cli.market_data import CliUsageError, run_market_data
from gemini_trading.cli.research import run_research
from gemini_trading.cli.strategy import run_strategy
from gemini_trading.data.errors import MarketDataError
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.errors import ResearchError
from gemini_trading.safety.execution_mode import UnsafeExecutionModeError


class SafeArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage errors as compact JSON."""

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(prog="gemini-trading")
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=SafeArgumentParser,
    )
    market_data = commands.add_parser("market-data", help="bounded public market data")
    market_commands = market_data.add_subparsers(
        dest="market_data_command",
        required=True,
        parser_class=SafeArgumentParser,
    )

    ingest = market_commands.add_parser("ingest", help="retrieve and validate public candles")
    ingest.add_argument("--symbol", required=True)
    ingest.add_argument("--base-asset", required=True)
    ingest.add_argument("--quote-asset", required=True)
    ingest.add_argument(
        "--interval",
        required=True,
        choices=[timeframe.value for timeframe in Timeframe],
    )
    ingest.add_argument("--start", required=True)
    ingest.add_argument("--end", required=True)
    ingest.add_argument("--output-root", required=True)

    replay = market_commands.add_parser("replay", help="rebuild canonical data offline")
    replay.add_argument("--run-id", required=True)
    replay.add_argument("--output-root", required=True)

    verify = market_commands.add_parser("verify", help="independently verify stored evidence")
    verify.add_argument("--dataset-id", required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--output-root", required=True)

    research = commands.add_parser("research", help="read-only deterministic research")
    research_commands = research.add_subparsers(
        dest="research_command",
        required=True,
        parser_class=SafeArgumentParser,
    )
    backtest = research_commands.add_parser("backtest", help="run deterministic backtest")
    backtest.add_argument("--dataset-id", required=True)
    backtest.add_argument("--config", required=True)
    backtest.add_argument("--project-root", required=True)
    backtest.add_argument("--output-root", required=True)

    research_replay = research_commands.add_parser(
        "replay", help="replay stored research evidence offline"
    )
    research_replay.add_argument("--experiment-id", required=True)
    research_replay.add_argument("--project-root", required=True)
    research_replay.add_argument("--output-root", required=True)

    research_verify = research_commands.add_parser(
        "verify", help="independently verify research evidence"
    )
    research_verify.add_argument("--experiment-id", required=True)
    research_verify.add_argument("--project-root", required=True)
    research_verify.add_argument("--output-root", required=True)

    strategy_evaluate = research_commands.add_parser(
        "strategy-evaluate", help="run the locked Candidate strategy study"
    )
    strategy_evaluate.add_argument("--dataset-id", required=True)
    strategy_evaluate.add_argument("--config", required=True)
    strategy_evaluate.add_argument("--project-root", required=True)
    strategy_evaluate.add_argument("--output-root", required=True)

    for command_name, help_text in (
        ("strategy-replay", "replay a stored Candidate strategy study offline"),
        ("strategy-verify", "independently verify a Candidate strategy study"),
    ):
        strategy_command = research_commands.add_parser(command_name, help=help_text)
        strategy_command.add_argument("--study-id", required=True)
        strategy_command.add_argument("--project-root", required=True)
        strategy_command.add_argument("--output-root", required=True)

    dataset_ingest = research_commands.add_parser(
        "dataset-ingest", help="ingest the fixed closure-aware BTCUSDT dataset"
    )
    dataset_ingest.add_argument("--project-root", required=True)
    dataset_ingest.add_argument("--output-root", required=True)

    dataset_replay = research_commands.add_parser(
        "dataset-replay", help="replay the fixed dataset evidence offline"
    )
    dataset_replay.add_argument("--run-id", required=True)
    dataset_replay.add_argument("--output-root", required=True)

    dataset_verify = research_commands.add_parser(
        "dataset-verify", help="independently verify the fixed v2 dataset"
    )
    dataset_verify.add_argument("--dataset-id", required=True)
    dataset_verify.add_argument("--run-id", required=True)
    dataset_verify.add_argument("--output-root", required=True)

    handoff = research_commands.add_parser(
        "strategy-handoff", help="seal one verified BTCUSDT dataset handoff"
    )
    handoff.add_argument("--run-id", required=True)
    handoff.add_argument("--dataset-id", required=True)
    handoff.add_argument("--source-commit", required=True)
    handoff.add_argument("--workflow-run-id", required=True)
    handoff.add_argument("--workflow-run-attempt", required=True)
    handoff.add_argument("--output-root", required=True)

    prepare = research_commands.add_parser(
        "strategy-prepare", help="prepare development-only Candidate evidence"
    )
    prepare.add_argument("--handoff", required=True)
    prepare.add_argument("--config", required=True)
    prepare.add_argument("--project-root", required=True)
    prepare.add_argument("--output-root", required=True)

    authorize = research_commands.add_parser(
        "strategy-authorize-final", help="persist one final-test access receipt"
    )
    authorize.add_argument("--pre-final-id", required=True)
    authorize.add_argument("--workflow-run-id", required=True)
    authorize.add_argument("--workflow-run-attempt", required=True)
    authorize.add_argument("--project-root", required=True)
    authorize.add_argument("--output-root", required=True)

    finalize = research_commands.add_parser(
        "strategy-finalize", help="complete the receipt-authorized final study"
    )
    finalize.add_argument("--pre-final-id", required=True)
    finalize.add_argument("--receipt-id", required=True)
    finalize.add_argument("--project-root", required=True)
    finalize.add_argument("--output-root", required=True)

    resume = research_commands.add_parser(
        "strategy-resume", help="verify provider-free completed final evidence"
    )
    resume.add_argument("--study-id", required=True)
    resume.add_argument("--receipt-id", required=True)
    resume.add_argument("--project-root", required=True)
    resume.add_argument("--output-root", required=True)

    qualify_v0_2 = research_commands.add_parser(
        "strategy-v0-2-qualify",
        help="run the fixed development-only Candidate v0.2 qualification",
    )
    qualify_v0_2.add_argument("--handoff", required=True)
    qualify_v0_2.add_argument("--config", required=True)
    qualify_v0_2.add_argument("--workflow-run-id", required=True)
    qualify_v0_2.add_argument("--workflow-run-attempt", required=True)
    qualify_v0_2.add_argument("--project-root", required=True)
    qualify_v0_2.add_argument("--output-root", required=True)

    verify_v0_2 = research_commands.add_parser(
        "strategy-v0-2-qualification-verify",
        help="verify Candidate v0.2 qualification evidence provider-free",
    )
    verify_v0_2.add_argument("--qualification-id", required=True)
    verify_v0_2.add_argument("--project-root", required=True)
    verify_v0_2.add_argument("--output-root", required=True)

    seal_v0_2 = research_commands.add_parser(
        "strategy-v0-2-seal-prospective-final",
        help="seal the future final era from verified QUALIFIED evidence",
    )
    seal_v0_2.add_argument("--qualification-id", required=True)
    seal_v0_2.add_argument("--project-root", required=True)
    seal_v0_2.add_argument("--output-root", required=True)

    qualify_v0_3 = research_commands.add_parser(
        "strategy-v0-3-qualify",
        help="run the fixed development-only Candidate v0.3 qualification",
    )
    qualify_v0_3.add_argument("--handoff", required=True)
    qualify_v0_3.add_argument("--config", required=True)
    qualify_v0_3.add_argument("--workflow-run-id", required=True)
    qualify_v0_3.add_argument("--workflow-run-attempt", required=True)
    qualify_v0_3.add_argument("--project-root", required=True)
    qualify_v0_3.add_argument("--output-root", required=True)

    verify_v0_3 = research_commands.add_parser(
        "strategy-v0-3-verify-qualification",
        help="verify Candidate v0.3 qualification evidence provider-free",
    )
    verify_v0_3.add_argument("--qualification-id", required=True)
    verify_v0_3.add_argument("--project-root", required=True)
    verify_v0_3.add_argument("--output-root", required=True)

    seal_v0_3 = research_commands.add_parser(
        "strategy-v0-3-create-prospective-seal",
        help="create a future-only Candidate v0.3 seal from verified evidence",
    )
    seal_v0_3.add_argument("--qualification-id", required=True)
    seal_v0_3.add_argument("--project-root", required=True)
    seal_v0_3.add_argument("--output-root", required=True)
    return parser


def _emit(payload: dict[str, object], stream: TextIO) -> None:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    print(serialized, file=stream)


def _error_payload(error_type: str, message: str) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process-compatible exit code."""

    command: object = None
    try:
        arguments = build_parser().parse_args(argv)
        command = getattr(arguments, "command", None)
        if command == "market-data":
            payload = run_market_data(arguments)
        elif command == "research":
            research_command = getattr(arguments, "research_command", None)
            candidate_v0_2_commands = {
                "strategy-v0-2-qualify",
                "strategy-v0-2-qualification-verify",
                "strategy-v0-2-seal-prospective-final",
            }
            candidate_v0_3_commands = {
                "strategy-v0-3-qualify",
                "strategy-v0-3-verify-qualification",
                "strategy-v0-3-create-prospective-seal",
            }
            historical_commands = {
                "dataset-ingest",
                "dataset-replay",
                "dataset-verify",
                "strategy-authorize-final",
                "strategy-finalize",
                "strategy-handoff",
                "strategy-prepare",
                "strategy-resume",
            }
            if research_command in candidate_v0_3_commands:
                payload = run_candidate_v0_3(arguments)
            elif research_command in candidate_v0_2_commands:
                payload = run_candidate_v0_2(arguments)
            elif research_command in historical_commands:
                payload = run_historical_validation(arguments)
            elif isinstance(research_command, str) and research_command.startswith("strategy-"):
                payload = run_strategy(arguments)
            else:
                payload = run_research(arguments)
        else:
            raise CliUsageError("unsupported command")
    except (MarketDataError, ResearchError) as error:
        _emit(_error_payload(type(error).__name__, str(error)), sys.stderr)
        return 2
    except (CliUsageError, UnsafeExecutionModeError) as error:
        _emit(_error_payload(type(error).__name__, str(error)), sys.stderr)
        return 2
    except Exception:
        message = (
            "research command failed" if command == "research" else "market data command failed"
        )
        _emit(_error_payload("InternalError", message), sys.stderr)
        return 2

    _emit(payload, sys.stdout)
    return 0
