from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import webbrowser

from . import __version__
from .config import Settings
from .models import ReviewRequest
from .relay import serve
from .modules.draft_review import run_review
from .tracker import BatchError, mark_ready, run_batch


def _settings(args: argparse.Namespace) -> Settings:
    return Settings.load(Path(args.config).expanduser() if getattr(args, "config", None) else None)


def doctor(settings: Settings) -> int:
    checks = {
        "Python 3.11+": sys.version_info >= (3, 11),
        "FFmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "whisper-cli": bool(shutil.which("whisper-cli")),
        "Swift compiler": bool(shutil.which("swiftc")),
        "Whisper model": bool(settings.whisper_model and settings.whisper_model.exists()),
        "GLM API or command": bool(settings.glm_api_key or settings.glm_command),
    }
    for label, okay in checks.items():
        print(f"{'OK' if okay else 'MISSING':8} {label}")
    print(f"\nLocal work directory: {settings.work_dir}")
    if not checks["Whisper model"]:
        print("Set VIDEO_PIPELINE_WHISPER_MODEL to an existing whisper.cpp model file.")
    if not checks["GLM API or command"]:
        print("Set the GLM API variables or VIDEO_PIPELINE_GLM_COMMAND_JSON. Use --provider mock only for testing.")
    return 0 if all(checks.values()) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-pipeline", description="Local-first tutorial video reviewer")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="Optional private TOML configuration file")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check local dependencies")

    review = sub.add_parser("review", help="Review one local video")
    review.add_argument("--video", required=True)
    review.add_argument("--script", required=True)
    review.add_argument("--editor", required=True, help="Editor key from the private team configuration")
    review.add_argument("--title")
    review.add_argument("--provider", default="glm", choices=("glm", "command", "mock"))
    review.add_argument("--text-only", action="store_true", help="Do not send screenshots to a cloud model")
    review.add_argument("--skip-transcript", action="store_true", help=argparse.SUPPRESS)
    review.add_argument("--skip-ocr", action="store_true", help=argparse.SUPPRESS)
    review.add_argument("--force", action="store_true", help="Regenerate report while retaining media caches")
    review.add_argument("--open", action="store_true", dest="open_report")

    batch = sub.add_parser("batch", help="Review every video in a batch manifest")
    batch.add_argument("manifest")
    batch.add_argument("--provider", default="glm", choices=("glm", "command", "mock"))
    batch.add_argument("--text-only", action="store_true")
    batch.add_argument("--skip-transcript", action="store_true", help=argparse.SUPPRESS)
    batch.add_argument("--skip-ocr", action="store_true", help=argparse.SUPPRESS)

    ready = sub.add_parser("ready", help="Editor confirms that a checked batch is ready for final review")
    ready.add_argument("--batch-id", required=True)

    status = sub.add_parser("status", help="Show the local status of one batch")
    status.add_argument("--batch-id", required=True)

    relay = sub.add_parser("relay", help="Run the metadata-only Google Chat notification relay")
    relay.add_argument("--host", default="127.0.0.1")
    relay.add_argument("--port", type=int, default=8787)
    relay.add_argument("--db", default="relay-events.sqlite3")
    relay.add_argument("--config", required=True, dest="relay_config")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        settings = _settings(args)
        settings.ensure_dirs()
        if args.command == "doctor":
            return doctor(settings)
        if args.command == "review":
            video = Path(args.video).expanduser()
            script = Path(args.script).expanduser()
            request = ReviewRequest(video=video, script=script, editor=args.editor,
                                    title=args.title or video.stem)
            result, job_dir = run_review(request, settings, provider_name=args.provider,
                                         text_only=args.text_only, skip_transcript=args.skip_transcript,
                                         skip_ocr=args.skip_ocr, force=args.force)
            print(f"Review complete: {job_dir / 'report.html'}")
            print(f"{len(result.issues)} findings · provider {result.provider} · model {result.model}")
            if args.open_report:
                webbrowser.open((job_dir / "report.html").as_uri())
            return 0
        if args.command == "batch":
            state, batch_path = run_batch(Path(args.manifest).expanduser(), settings,
                                          provider_name=args.provider, text_only=args.text_only,
                                          skip_transcript=args.skip_transcript, skip_ocr=args.skip_ocr)
            print(f"Batch status: {state['status']}")
            print(f"Checked {state['completed']} of {state['total']} · failed {state['failed']}")
            print(f"Batch record: {batch_path}")
            return 0 if state["status"] == "review_complete" else 2
        if args.command == "ready":
            state, batch_path = mark_ready(args.batch_id, settings)
            print(f"Ready for {settings.reviewer_label}: {state['ready']} of {state['total']}")
            print(f"Batch record: {batch_path}")
            return 0
        if args.command == "status":
            from .util import read_json, slugify
            path = settings.work_dir / "batches" / f"{slugify(args.batch_id)}.json"
            state = read_json(path)
            if not state:
                raise BatchError(f"Unknown batch: {args.batch_id}")
            print(json.dumps({
                "batch_id": state["batch_id"], "editor": state["editor"], "status": state["status"],
                "total": state["total"], "checked": state.get("completed", 0),
                "failed": state.get("failed", 0), "ready": state.get("ready", 0),
            }, indent=2))
            return 0
        if args.command == "relay":
            serve(args.host, args.port, Path(args.db).expanduser(), Path(args.relay_config).expanduser())
            return 0
    except (BatchError, FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
