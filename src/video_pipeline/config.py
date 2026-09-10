from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any
import tomllib


DEFAULT_WORK_DIR = Path.home() / "Library" / "Application Support" / "Video Pipeline"


@dataclass
class Settings:
    """Shared local settings only.

    Model and agent choices belong to individual modules. ``legacy_values`` is
    retained so module loaders can translate existing private configurations
    without making the shared core depend on a provider.
    """

    work_dir: Path = DEFAULT_WORK_DIR
    whisper_model: Path | None = None
    frame_interval_sec: float = 2.0
    relay_url: str = ""
    relay_token: str = ""
    reviewer_label: str = "final reviewer"
    modules: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    legacy_values: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        document: dict[str, Any] = {}
        default_path = Path.home() / ".config" / "video-pipeline" / "config.toml"
        if path is None and default_path.exists():
            path = default_path
        if path:
            with path.open("rb") as handle:
                document = tomllib.load(handle)

        if "video_pipeline" in document:
            core_values = document.get("video_pipeline", {})
            module_values = document.get("modules", {})
        else:
            core_values = document
            module_values = document.get("modules", {}) if isinstance(document, dict) else {}
        if not isinstance(core_values, dict):
            core_values = {}
        if not isinstance(module_values, dict):
            module_values = {}

        env = os.environ
        whisper = env.get("VIDEO_PIPELINE_WHISPER_MODEL") or core_values.get("whisper_model")
        settings = cls(
            work_dir=Path(env.get("VIDEO_PIPELINE_WORK_DIR") or core_values.get("work_dir") or DEFAULT_WORK_DIR).expanduser(),
            whisper_model=Path(whisper).expanduser() if whisper else None,
            frame_interval_sec=float(
                env.get("VIDEO_PIPELINE_FRAME_INTERVAL") or core_values.get("frame_interval_sec", 2.0)
            ),
            relay_url=env.get("VIDEO_PIPELINE_RELAY_URL") or core_values.get("relay_url", ""),
            relay_token=env.get("VIDEO_PIPELINE_RELAY_TOKEN") or core_values.get("relay_token", ""),
            reviewer_label=(
                env.get("VIDEO_PIPELINE_REVIEWER_LABEL")
                or core_values.get("reviewer_label", "final reviewer")
            ),
            modules={
                str(name): value for name, value in module_values.items()
                if isinstance(value, dict)
            },
            legacy_values=dict(core_values),
        )
        if settings.frame_interval_sec <= 0:
            raise ValueError("frame_interval_sec must be greater than zero")
        return settings

    def module_config(self, name: str) -> dict[str, Any]:
        return dict(self.modules.get(name, {}))

    def ensure_dirs(self) -> None:
        for child in ("jobs", "batches", "feedback", "tools"):
            (self.work_dir / child).mkdir(parents=True, exist_ok=True)
