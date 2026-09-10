from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tomllib


DEFAULT_WORK_DIR = Path.home() / "Library" / "Application Support" / "Video Pipeline"


@dataclass
class Settings:
    work_dir: Path = DEFAULT_WORK_DIR
    whisper_model: Path | None = None
    frame_interval_sec: float = 2.0
    chunk_length_sec: int = 300
    max_images_per_chunk: int = 18
    glm_base_url: str = "https://api.z.ai/api/paas/v4"
    glm_api_key: str = ""
    glm_model: str = "glm-4.6v"
    glm_timeout_sec: int = 600
    glm_max_retries: int = 2
    max_glm_calls_per_video: int = 6
    glm_command: list[str] | None = None
    claude_code_command: str = "claude"
    claude_code_model: str = "sonnet"
    claude_code_max_budget_usd: float = 0.10
    relay_url: str = ""
    relay_token: str = ""
    reviewer_label: str = "final reviewer"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        values: dict = {}
        default_path = Path.home() / ".config" / "video-pipeline" / "config.toml"
        if path is None and default_path.exists():
            path = default_path
        if path:
            with path.open("rb") as handle:
                values = tomllib.load(handle)
            values = values.get("video_pipeline", values)

        env = os.environ
        command = values.get("glm_command")
        if env.get("VIDEO_PIPELINE_GLM_COMMAND_JSON"):
            command = json.loads(env["VIDEO_PIPELINE_GLM_COMMAND_JSON"])

        whisper = env.get("VIDEO_PIPELINE_WHISPER_MODEL") or values.get("whisper_model")
        settings = cls(
            work_dir=Path(env.get("VIDEO_PIPELINE_WORK_DIR") or values.get("work_dir") or DEFAULT_WORK_DIR).expanduser(),
            whisper_model=Path(whisper).expanduser() if whisper else None,
            frame_interval_sec=float(env.get("VIDEO_PIPELINE_FRAME_INTERVAL") or values.get("frame_interval_sec", 2.0)),
            chunk_length_sec=int(env.get("VIDEO_PIPELINE_CHUNK_LENGTH") or values.get("chunk_length_sec", 300)),
            max_images_per_chunk=int(env.get("VIDEO_PIPELINE_MAX_IMAGES") or values.get("max_images_per_chunk", 18)),
            glm_base_url=env.get("VIDEO_PIPELINE_GLM_BASE_URL") or values.get("glm_base_url", "https://api.z.ai/api/paas/v4"),
            glm_api_key=env.get("VIDEO_PIPELINE_GLM_API_KEY") or values.get("glm_api_key", ""),
            glm_model=env.get("VIDEO_PIPELINE_GLM_MODEL") or values.get("glm_model", "glm-4.6v"),
            glm_timeout_sec=int(env.get("VIDEO_PIPELINE_GLM_TIMEOUT") or values.get("glm_timeout_sec", 600)),
            glm_max_retries=int(env.get("VIDEO_PIPELINE_GLM_RETRIES") or values.get("glm_max_retries", 2)),
            max_glm_calls_per_video=int(env.get("VIDEO_PIPELINE_MAX_GLM_CALLS") or values.get("max_glm_calls_per_video", 6)),
            glm_command=command,
            claude_code_command=env.get("VIDEO_PIPELINE_CLAUDE_COMMAND") or values.get("claude_code_command", "claude"),
            claude_code_model=env.get("VIDEO_PIPELINE_CLAUDE_MODEL") or values.get("claude_code_model", "sonnet"),
            claude_code_max_budget_usd=float(
                env.get("VIDEO_PIPELINE_CLAUDE_MAX_BUDGET_USD")
                or values.get("claude_code_max_budget_usd", 0.10)
            ),
            relay_url=env.get("VIDEO_PIPELINE_RELAY_URL") or values.get("relay_url", ""),
            relay_token=env.get("VIDEO_PIPELINE_RELAY_TOKEN") or values.get("relay_token", ""),
            reviewer_label=env.get("VIDEO_PIPELINE_REVIEWER_LABEL") or values.get("reviewer_label", "final reviewer"),
        )
        if settings.frame_interval_sec <= 0:
            raise ValueError("frame_interval_sec must be greater than zero")
        if settings.chunk_length_sec <= 0 or settings.max_images_per_chunk <= 0:
            raise ValueError("chunk_length_sec and max_images_per_chunk must be greater than zero")
        if settings.max_glm_calls_per_video <= 0:
            raise ValueError("max_glm_calls_per_video must be greater than zero")
        if settings.claude_code_max_budget_usd <= 0:
            raise ValueError("claude_code_max_budget_usd must be greater than zero")
        return settings

    def ensure_dirs(self) -> None:
        for child in ("jobs", "batches", "feedback", "tools"):
            (self.work_dir / child).mkdir(parents=True, exist_ok=True)
