from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ...config import Settings
from ...media import analyse_media, collapse_screen_states
from ...models import Issue, ReviewRequest, ReviewResult
from ...providers import ProviderError, make_provider
from ...report import write_reports
from .prompt import SYSTEM_PROMPT
from .rules import deduplicate_issues, deterministic_issues
from ...util import read_json, sha256_file, slugify, utc_now, write_json


def _job_identity(request: ReviewRequest) -> tuple[str, str, str]:
    video_hash = sha256_file(request.video)
    script_hash = sha256_file(request.script)
    job_id = f"{slugify(request.title)}-{video_hash[:12]}-{script_hash[:8]}"
    return job_id, video_hash, script_hash


def _chunk_prompt(title: str, script: str, media: dict[str, Any], frames: list[dict[str, Any]],
                  start: float, end: float, chunk_index: int, chunk_total: int) -> tuple[str, list[Path]]:
    transcript = [item for item in media.get("transcript", []) if item.get("end_sec", 0) > start and item.get("start_sec", 0) < end]
    ocr = [item for item in frames if start <= float(item.get("time_sec", 0)) < end]
    frame_dir = Path(media["frame_dir"])
    images = [frame_dir / item["frame"] for item in ocr if (frame_dir / item["frame"]).exists()]
    evidence = [{
        "time_sec": item.get("time_sec", 0),
        "frame": item.get("frame"),
        "screen_text": item.get("text", "")[:1800],
        "error_terms": item.get("error_terms", []),
    } for item in ocr]
    prompt = "\n".join([
        f"VIDEO TITLE: {title}",
        f"REVIEW CHUNK: {chunk_index + 1} of {chunk_total}, {start:.1f}s to {end:.1f}s",
        "",
        "APPROVED SCRIPT:", script,
        "",
        "TIMESTAMPED TRANSCRIPT FOR THIS CHUNK:", json.dumps(transcript, ensure_ascii=False),
        "",
        "TIMESTAMPED SCREEN EVIDENCE FOR THIS CHUNK:", json.dumps(evidence, ensure_ascii=False),
        "",
        "The attached images use the filenames in the screen evidence. Return only the issue JSON.",
    ])
    return prompt, images


def run_review(request: ReviewRequest, settings: Settings, *, provider_name: str = "auto",
               text_only: bool = False, skip_transcript: bool = False, skip_ocr: bool = False,
               force: bool = False) -> tuple[ReviewResult, Path]:
    for path, label in ((request.video, "video"), (request.script, "script")):
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"The {label} file does not exist: {path}")
    settings.ensure_dirs()
    job_id, video_hash, script_hash = _job_identity(request)
    job_dir = settings.work_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    final_path = job_dir / "report.json"
    if final_path.exists() and not force:
        payload = read_json(final_path, {})
        result = ReviewResult(
            **{key: value for key, value in payload.items() if key != "issues"},
            issues=[Issue(**item) for item in payload.get("issues", [])],
        )
        return result, job_dir

    started = utc_now()
    write_json(job_dir / "job.json", {
        "job_id": job_id, "title": request.title, "editor": request.editor,
        "video_path": str(request.video.resolve()), "script_path": str(request.script.resolve()),
        "video_sha256": video_hash, "script_sha256": script_hash,
        "batch_id": request.batch_id, "status": "running", "created_at": started,
    })
    script = request.script.read_text(encoding="utf-8")
    media, warnings = analyse_media(request.video, job_dir, settings,
                                    skip_transcript=skip_transcript, skip_ocr=skip_ocr)
    media["frame_dir"] = str(job_dir / "analysis" / "frames")
    issues = deterministic_issues(media, script)

    provider = make_provider(provider_name, settings, text_only=text_only)
    duration = float(media.get("duration_sec") or 0)
    total_chunks = max(1, int((duration + settings.chunk_length_sec - 1) // settings.chunk_length_sec))
    usage: dict[str, Any] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_calls": 0}
    chunk_failures = 0
    chunks_to_run = min(total_chunks, settings.max_glm_calls_per_video)
    if chunks_to_run < total_chunks:
        chunk_failures += total_chunks - chunks_to_run
        warnings.append(
            f"GLM review stopped at the configured limit of {settings.max_glm_calls_per_video} calls; "
            f"{total_chunks - chunks_to_run} video chunk(s) were not model-reviewed."
        )
    valid_frames = {item.get("frame") for item in media.get("ocr", [])}
    for chunk_index in range(chunks_to_run):
        start = chunk_index * settings.chunk_length_sec
        end = min(duration, (chunk_index + 1) * settings.chunk_length_sec) if duration else settings.chunk_length_sec
        raw_frames = [item for item in media.get("ocr", []) if start <= float(item.get("time_sec", 0)) < end]
        frames = collapse_screen_states(raw_frames, settings.max_images_per_chunk)
        prompt, images = _chunk_prompt(request.title, script, media, frames, start, end, chunk_index, total_chunks)
        cache_path = job_dir / "analysis" / f"glm-chunk-{chunk_index:03d}.json"
        try:
            model_issues, chunk_usage = provider.review(SYSTEM_PROMPT, prompt, images, cache_path)
            for item in model_issues:
                if item.evidence_frame not in valid_frames:
                    item.evidence_frame = None
                if duration:
                    item.timestamp_sec = min(item.timestamp_sec, duration)
            issues.extend(model_issues)
            if chunk_usage.get("cached"):
                usage["cached_calls"] += 1
            else:
                usage["calls"] += int(chunk_usage.get("calls", 1))
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage[key] += int(chunk_usage.get(key, 0) or 0)
        except ProviderError as error:
            chunk_failures += 1
            warnings.append(f"GLM chunk {chunk_index + 1} could not be reviewed: {error}")

    completed = utc_now()
    status = "needs_attention" if chunk_failures else "review_complete"
    result = ReviewResult(
        job_id=job_id, title=request.title, editor=request.editor,
        video_path=str(request.video.resolve()), script_path=str(request.script.resolve()),
        video_sha256=video_hash, script_sha256=script_hash, status=status,
        reviewer_label=settings.reviewer_label,
        media={key: value for key, value in media.items() if key not in {"transcript", "ocr", "frame_dir"}},
        issues=deduplicate_issues(issues), warnings=warnings,
        provider=provider.name, model=provider.model, created_at=started, completed_at=completed, usage=usage,
    )
    write_reports(result, job_dir)
    job = read_json(job_dir / "job.json", {})
    job.update({"status": result.status, "completed_at": completed, "issues": {
        "required": sum(item.severity == "required" for item in result.issues),
        "suggestion": sum(item.severity == "suggestion" for item in result.issues),
        "needs_decision": sum(item.severity == "needs_decision" for item in result.issues),
    }})
    write_json(job_dir / "job.json", job)
    return result, job_dir
