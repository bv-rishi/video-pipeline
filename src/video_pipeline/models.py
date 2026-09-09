from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


VALID_SEVERITIES = {"required", "suggestion", "needs_decision"}


@dataclass
class Issue:
    timestamp_sec: float
    title: str
    problem: str
    fix: str
    severity: str = "suggestion"
    category: str = "editorial"
    confidence: float = 0.5
    end_sec: float | None = None
    evidence_frame: str | None = None
    source: str = "glm"
    rule_version: str = "draft-review/0.1"
    issue_id: str = ""

    def __post_init__(self) -> None:
        if self.severity not in VALID_SEVERITIES:
            self.severity = "needs_decision"
        self.timestamp_sec = max(0.0, float(self.timestamp_sec or 0))
        self.confidence = min(1.0, max(0.0, float(self.confidence or 0)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewResult:
    job_id: str
    title: str
    editor: str
    video_path: str
    script_path: str
    video_sha256: str
    script_sha256: str
    status: str
    reviewer_label: str = "final reviewer"
    media: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider: str = "none"
    model: str = "none"
    created_at: str = ""
    completed_at: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["issues"] = [issue.to_dict() for issue in self.issues]
        return value


@dataclass
class ReviewRequest:
    video: Path
    script: Path
    editor: str
    title: str
    batch_id: str | None = None
