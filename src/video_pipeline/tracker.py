from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings
from .models import ReviewRequest
from .modules.draft_review import run_review
from .util import read_json, slugify, utc_now, write_json


class BatchError(RuntimeError):
    pass


def load_manifest(path: Path) -> dict[str, Any]:
    value = read_json(path, {})
    required = {"batch_id", "editor", "videos"}
    if not required.issubset(value):
        raise BatchError(f"Batch manifest must contain: {', '.join(sorted(required))}")
    if not isinstance(value["videos"], list) or not value["videos"]:
        raise BatchError("Batch manifest must contain at least one video")
    return value


def run_batch(manifest_path: Path, settings: Settings, *, provider_name: str = "auto",
              text_only: bool = False, skip_transcript: bool = False, skip_ocr: bool = False) -> tuple[dict[str, Any], Path]:
    manifest = load_manifest(manifest_path)
    manifest_dir = manifest_path.resolve().parent
    batch_id = slugify(str(manifest["batch_id"]))
    batch_path = settings.work_dir / "batches" / f"{batch_id}.json"
    state = read_json(batch_path, {
        "batch_id": batch_id, "editor": str(manifest["editor"]).lower(), "status": "running",
        "total": len(manifest["videos"]), "completed": 0, "failed": 0, "ready": 0,
        "jobs": [], "created_at": utc_now(),
    })
    known = {item.get("source_index"): item for item in state.get("jobs", [])}
    for index, item in enumerate(manifest["videos"]):
        if known.get(index, {}).get("status") in {"review_complete", "ready_for_reviewer"}:
            continue
        entry = {"source_index": index, "title": item.get("title") or Path(item["video"]).stem,
                 "status": "running", "started_at": utc_now()}
        known[index] = entry
        state["jobs"] = [known[key] for key in sorted(known)]
        _update_counts(state)
        write_json(batch_path, state)
        try:
            video = Path(item["video"]).expanduser()
            script = Path(item["script"]).expanduser()
            if not video.is_absolute():
                video = manifest_dir / video
            if not script.is_absolute():
                script = manifest_dir / script
            request = ReviewRequest(video=video, script=script,
                                    editor=state["editor"], title=entry["title"], batch_id=batch_id)
            result, job_dir = run_review(request, settings, provider_name=provider_name, text_only=text_only,
                                         skip_transcript=skip_transcript, skip_ocr=skip_ocr)
            entry.update({"status": result.status, "job_id": result.job_id, "job_dir": str(job_dir),
                          "completed_at": utc_now()})
        except Exception as error:
            entry.update({"status": "failed", "error": str(error), "completed_at": utc_now()})
        state["jobs"] = [known[key] for key in sorted(known)]
        _update_counts(state)
        write_json(batch_path, state)
    if state.get("ready", 0) == state["total"]:
        state["status"] = "ready_for_reviewer"
    elif state["completed"] == state["total"]:
        state["status"] = "review_complete"
    else:
        state["status"] = "needs_attention"
    state["updated_at"] = utc_now()
    write_json(batch_path, state)
    if state["status"] != "ready_for_reviewer":
        notify(state, settings, event="review_complete")
    write_json(batch_path, state)
    return state, batch_path


def _update_counts(state: dict[str, Any]) -> None:
    state["completed"] = sum(item.get("status") in {"review_complete", "ready_for_reviewer"} for item in state.get("jobs", []))
    state["failed"] = sum(item.get("status") in {"failed", "needs_attention"} for item in state.get("jobs", []))
    state["ready"] = sum(item.get("status") == "ready_for_reviewer" for item in state.get("jobs", []))


def mark_ready(batch_id: str, settings: Settings) -> tuple[dict[str, Any], Path]:
    batch_path = settings.work_dir / "batches" / f"{slugify(batch_id)}.json"
    state = read_json(batch_path)
    if not state:
        raise BatchError(f"Unknown batch: {batch_id}")
    if state.get("completed", 0) != state.get("total", 0):
        raise BatchError("The editor cannot mark this batch ready because not every video has a completed review")
    for item in state.get("jobs", []):
        if item.get("status") == "review_complete":
            item["status"] = "ready_for_reviewer"
    _update_counts(state)
    state["status"] = "ready_for_reviewer"
    state["ready_confirmed_at"] = utc_now()
    write_json(batch_path, state)
    notify(state, settings, event="ready_for_reviewer")
    write_json(batch_path, state)
    return state, batch_path


def notify(state: dict[str, Any], settings: Settings, event: str) -> dict[str, Any] | None:
    if not settings.relay_url or not settings.relay_token:
        return None
    event_id = hashlib.sha256(
        f"{state['batch_id']}:{event}:{state.get('completed', 0)}:{state.get('ready', 0)}:{state.get('failed', 0)}".encode()
    ).hexdigest()
    payload = {
        "event_id": event_id, "event": event, "batch_id": state["batch_id"],
        "editor": state["editor"], "total": state["total"], "checked": state.get("completed", 0),
        "failed": state.get("failed", 0), "ready": state.get("ready", 0), "sent_at": utc_now(),
    }
    request = Request(settings.relay_url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {settings.relay_token}", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        state.setdefault("notification_errors", []).append({"event": event, "error": str(error), "at": utc_now()})
        return None
