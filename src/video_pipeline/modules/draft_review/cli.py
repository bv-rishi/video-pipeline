from __future__ import annotations

import argparse
from pathlib import Path

from ... import __version__
from ...config import Settings
from ...models import ReviewRequest
from ...tracker import run_batch
from .engine import run_review


AGENT_CHOICES = ("auto", "none", "claude-code", "openai-compatible", "command", "mock", "glm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-draft-review", description="Independent draft-review module")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="Optional private TOML configuration file")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review", help="Review one local video")
    review.add_argument("--video", required=True)
    review.add_argument("--script", required=True)
    review.add_argument("--editor", required=True)
    review.add_argument("--title")
    review.add_argument("--agent", "--provider", dest="agent", default="auto", choices=AGENT_CHOICES)
    review.add_argument("--text-only", action="store_true")
    review.add_argument("--skip-transcript", action="store_true", help=argparse.SUPPRESS)
    review.add_argument("--skip-ocr", action="store_true", help=argparse.SUPPRESS)
    review.add_argument("--force", action="store_true")
    batch = sub.add_parser("batch", help="Review every video in a batch manifest")
    batch.add_argument("manifest")
    batch.add_argument("--agent", "--provider", dest="agent", default="auto", choices=AGENT_CHOICES)
    batch.add_argument("--text-only", action="store_true")
    batch.add_argument("--skip-transcript", action="store_true", help=argparse.SUPPRESS)
    batch.add_argument("--skip-ocr", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.load(Path(args.config).expanduser() if args.config else None)
    settings.ensure_dirs()
    if args.command == "review":
        video = Path(args.video).expanduser()
        script = Path(args.script).expanduser()
        result, job_dir = run_review(
            ReviewRequest(video=video, script=script, editor=args.editor, title=args.title or video.stem),
            settings,
            provider_name=args.agent,
            text_only=args.text_only,
            skip_transcript=args.skip_transcript,
            skip_ocr=args.skip_ocr,
            force=args.force,
        )
        print(f"Review status: {result.status}")
        print(f"Report: {job_dir / 'report.html'}")
        print(f"Agent: {result.provider} · model: {result.model}")
        return 0 if result.status == "review_complete" else 2
    if args.command == "batch":
        state, batch_path = run_batch(
            Path(args.manifest).expanduser(), settings, provider_name=args.agent,
            text_only=args.text_only, skip_transcript=args.skip_transcript, skip_ocr=args.skip_ocr,
        )
        print(f"Batch status: {state['status']}")
        print(f"Batch record: {batch_path}")
        return 0 if state["status"] == "review_complete" else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
