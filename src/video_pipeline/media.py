from __future__ import annotations

import json
import math
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .config import Settings
from .util import read_json, run, write_json


class MediaError(RuntimeError):
    pass


def _required_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError(f"Required program is missing: {name}")
    return path


def probe_video(video: Path) -> dict[str, Any]:
    result = run([
        _required_program("ffprobe"), "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(video),
    ])
    payload = json.loads(result.stdout)
    video_stream = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in payload.get("streams", []) if item.get("codec_type") == "audio"), {})
    frame_rate = video_stream.get("avg_frame_rate", "0/1")
    try:
        numerator, denominator = frame_rate.split("/")
        fps = float(numerator) / max(float(denominator), 1.0)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {
        "duration_sec": float(payload.get("format", {}).get("duration") or 0),
        "size_bytes": int(payload.get("format", {}).get("size") or video.stat().st_size),
        "format": payload.get("format", {}).get("format_name", ""),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": round(fps, 3),
        "video_codec": video_stream.get("codec_name", ""),
        "audio_codec": audio_stream.get("codec_name", ""),
        "sample_rate": int(audio_stream.get("sample_rate") or 0),
    }


def extract_audio(video: Path, job_dir: Path) -> Path:
    target = job_dir / "analysis" / "audio.wav"
    if target.exists() and target.stat().st_size:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    run([
        _required_program("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target),
    ])
    return target


def measure_audio(video: Path) -> dict[str, Any]:
    process = subprocess.run(
        [_required_program("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    blocks = re.findall(r"\{\s*\"input_i\".*?\}", process.stderr, re.DOTALL)
    if not blocks:
        return {"available": False, "reason": "FFmpeg did not return loudness measurements"}
    try:
        value = json.loads(blocks[-1])
        return {
            "available": True,
            "integrated_lufs": float(value["input_i"]),
            "true_peak_dbtp": float(value["input_tp"]),
            "loudness_range_lu": float(value["input_lra"]),
            "measured_threshold": float(value["input_thresh"]),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {"available": False, "reason": "Could not parse FFmpeg loudness measurements"}


def transcribe(audio: Path, job_dir: Path, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    output = job_dir / "analysis" / "transcript.json"
    warnings: list[str] = []
    if output.exists():
        return _transcript_segments(read_json(output, {})), warnings
    if not settings.whisper_model or not settings.whisper_model.exists():
        warnings.append("Transcription skipped: configure VIDEO_PIPELINE_WHISPER_MODEL with a local whisper.cpp model.")
        return [], warnings
    whisper = _required_program("whisper-cli")
    prefix = output.with_suffix("")
    run([
        whisper, "-m", str(settings.whisper_model), "-f", str(audio), "-l", "en",
        "-ojf", "-osrt", "-of", str(prefix), "-np",
    ], timeout=max(600, settings.glm_timeout_sec))
    if not output.exists():
        raise MediaError("whisper-cli finished without creating transcript.json")
    return _transcript_segments(read_json(output, {})), warnings


def _transcript_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    segments = []
    for item in payload.get("transcription", []):
        offsets = item.get("offsets", {})
        segments.append({
            "start_sec": round(float(offsets.get("from", 0)) / 1000, 3),
            "end_sec": round(float(offsets.get("to", 0)) / 1000, 3),
            "text": str(item.get("text", "")).strip(),
        })
    return segments


def extract_frames(video: Path, job_dir: Path, interval_sec: float) -> Path:
    frames = job_dir / "analysis" / "frames"
    marker = frames / ".complete"
    if marker.exists() and any(frames.glob("*.jpg")):
        return frames
    frames.mkdir(parents=True, exist_ok=True)
    for stale in frames.glob("*.jpg"):
        stale.unlink()
    run([
        _required_program("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-vf", f"fps=1/{interval_sec},scale='min(1280,iw)':-2", "-q:v", "4",
        str(frames / "frame_%06d.jpg"),
    ], timeout=3600)
    marker.touch()
    return frames


def compile_vision_ocr(settings: Settings) -> Path:
    source = Path(__file__).with_name("vision_ocr.swift")
    target = settings.work_dir / "tools" / "vision_ocr"
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    swiftc = _required_program("swiftc")
    target.parent.mkdir(parents=True, exist_ok=True)
    run([swiftc, str(source), "-O", "-o", str(target)], timeout=300)
    return target


def run_ocr(frames: Path, job_dir: Path, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    output = job_dir / "analysis" / "ocr.jsonl"
    warnings: list[str] = []
    if not output.exists():
        try:
            tool = compile_vision_ocr(settings)
            run([str(tool), str(frames), "draft", str(output), "fast"], timeout=3600, capture=False)
        except (MediaError, RuntimeError) as error:
            warnings.append(f"Screen-text extraction skipped: {error}")
            return [], warnings
    records = []
    for line in output.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        match = re.search(r"(\d+)", item.get("frame", ""))
        frame_number = int(match.group(1)) if match else len(records) + 1
        item["time_sec"] = round((frame_number - 1) * settings.frame_interval_sec, 3)
        records.append(item)
    return records, warnings


def collapse_screen_states(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if not records:
        return []
    chosen = [records[0]]
    for item in records[1:]:
        prior = chosen[-1]
        try:
            distance = (int(item.get("dhash", "0"), 16) ^ int(prior.get("dhash", "0"), 16)).bit_count()
        except ValueError:
            distance = 64
        left = set(re.findall(r"[a-z0-9]{2,}", item.get("text", "").lower()))
        right = set(re.findall(r"[a-z0-9]{2,}", prior.get("text", "").lower()))
        similarity = len(left & right) / max(len(left | right), 1)
        if distance > 9 and similarity < 0.78:
            chosen.append(item)
    if len(chosen) <= limit:
        return chosen
    indices = sorted({round(index * (len(chosen) - 1) / max(limit - 1, 1)) for index in range(limit)})
    return [chosen[index] for index in indices]


def analyse_media(video: Path, job_dir: Path, settings: Settings, *, skip_transcript: bool = False,
                  skip_ocr: bool = False) -> tuple[dict[str, Any], list[str]]:
    summary_path = job_dir / "analysis" / "summary.json"
    analysis_config = {
        "version": 1, "frame_interval_sec": settings.frame_interval_sec,
        "skip_transcript": skip_transcript, "skip_ocr": skip_ocr,
        "whisper_model": str(settings.whisper_model or ""),
    }
    if summary_path.exists():
        payload = read_json(summary_path, {})
        if payload.get("analysis_config") == analysis_config:
            return payload, payload.get("warnings", [])

    warnings: list[str] = []
    media = probe_video(video)
    media["audio"] = measure_audio(video)
    audio = extract_audio(video, job_dir)
    if skip_transcript:
        transcript = []
        warnings.append("Transcription disabled for this run.")
    else:
        transcript, items = transcribe(audio, job_dir, settings)
        warnings.extend(items)
    frames = extract_frames(video, job_dir, settings.frame_interval_sec)
    if skip_ocr:
        ocr = []
        warnings.append("Screen-text extraction disabled for this run.")
    else:
        ocr, items = run_ocr(frames, job_dir, settings)
        warnings.extend(items)
    payload = {**media, "transcript": transcript, "ocr": ocr, "warnings": warnings,
               "analysis_config": analysis_config}
    write_json(summary_path, payload)
    return payload, warnings
