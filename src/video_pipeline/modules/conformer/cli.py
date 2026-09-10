from __future__ import annotations

import argparse
import json
from pathlib import Path

from ... import __version__
from . import STATUS, validate_benchmark_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-conformer",
        description="Independent Tutorial Conformer module boundary",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show the current conformer implementation status")
    validate = sub.add_parser("validate-benchmark", help="Validate a sanitized conformer benchmark summary")
    validate.add_argument("summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        print(json.dumps({
            "module": "conformer",
            "status": STATUS,
            "components": ["aroll", "screen-matcher"],
            "agent_policy": "optional_per_module_adapter",
        }, indent=2))
        return 0
    if args.command == "validate-benchmark":
        path = Path(args.summary).expanduser()
        value = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_benchmark_summary(value)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
            return 2
        print(json.dumps({
            "valid": True,
            "case_id": value["case_id"],
            "retrieval": value["retrieval"],
            "state_contrasts": value["state_contrasts"],
            "agent_usage": value["agent_usage"],
        }, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
