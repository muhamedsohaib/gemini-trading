"""Top-level safe command-line entry point."""

import argparse
import json
import sys
from collections.abc import Sequence
from typing import NoReturn, TextIO

from gemini_trading.cli import research
from gemini_trading.cli.market_data import CliUsageError, run_market_data
from gemini_trading.data.errors import MarketDataError
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.errors import ResearchError
from gemini_trading.safety.execution_mode import UnsafeExecutionModeError


class SafeArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage errors as compact JSON."""

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


def _build_parser() -> SafeArgumentParser:
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
        arguments = _build_parser().parse_args(argv)
        command = getattr(arguments, "command", None)
        if command == "market-data":
            payload = run_market_data(arguments)
        elif command == "research":
            payload = research.run_research(arguments)
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
