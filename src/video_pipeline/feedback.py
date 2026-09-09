from __future__ import annotations

import json
from pathlib import Path
import re
import uuid
from typing import Any

from .config import Settings
from .util import read_json, utc_now


KINDS = {"incorrect", "missed", "approved"}
SCOPES = {"video", "draft-review", "shared"}


class FeedbackError(RuntimeError):
    pass


def record_feedback(settings: Settings, *, job_id: str, kind: str, scope: str, note: str,
                    issue_id: str | None = None, timestamp_sec: float | None = None) -> dict[str, Any]:
    if kind not in KINDS or scope not in SCOPES:
        raise FeedbackError("Invalid feedback kind or scope")
    if not note.strip():
        raise FeedbackError("Feedback note cannot be empty")
    if Path(job_id).name != job_id or not re.fullmatch(r"[a-z0-9-]+", job_id):
        raise FeedbackError("Invalid job ID")
    job_dir = settings.work_dir / "jobs" / job_id
    job = read_json(job_dir / "job.json")
    report = read_json(job_dir / "report.json")
    if not job or not report:
        raise FeedbackError(f"Unknown completed job: {job_id}")
    if kind in {"incorrect", "approved"}:
        if not issue_id:
            raise FeedbackError(f"--issue-id is required for {kind} feedback")
        if issue_id not in {item.get("issue_id") for item in report.get("issues", [])}:
            raise FeedbackError(f"Unknown issue ID for this report: {issue_id}")
    record = {
        "feedback_id": str(uuid.uuid4()), "created_at": utc_now(), "job_id": job_id,
        "video_sha256": job.get("video_sha256"), "script_sha256": job.get("script_sha256"),
        "module": "draft-review", "kind": kind, "scope": scope, "issue_id": issue_id,
        "timestamp_sec": timestamp_sec, "note": note.strip(), "status": "recorded",
    }
    target = settings.work_dir / "feedback" / "feedback.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
