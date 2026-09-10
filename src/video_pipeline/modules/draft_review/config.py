from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any

from ...config import Settings


@dataclass
class ReviewAgentSettings:
    adapter: str = "auto"
    command: list[str] | None = None
    timeout_sec: int = 600
    max_retries: int = 2
    api_base_url: str = ""
    api_key: str = ""
    api_model: str = ""
    claude_code_command: str = "claude"
    claude_code_model: str = "sonnet"
    claude_code_max_budget_usd: float = 0.10


@dataclass
class DraftReviewSettings:
    chunk_length_sec: int = 300
    max_images_per_chunk: int = 18
    max_agent_calls_per_video: int = 6
    agent: ReviewAgentSettings = field(default_factory=ReviewAgentSettings)

    @classmethod
    def from_core(cls, settings: Settings) -> "DraftReviewSettings":
        values = settings.module_config("draft_review")
        agent_values = values.get("agent", {})
        if not isinstance(agent_values, dict):
            agent_values = {}
        legacy = settings.legacy_values
        env = os.environ

        command: Any = agent_values.get("command") or legacy.get("glm_command")
        command_json = (
            env.get("VIDEO_PIPELINE_DRAFT_REVIEW_AGENT_COMMAND_JSON")
            or env.get("VIDEO_PIPELINE_GLM_COMMAND_JSON")
        )
        if command_json:
            command = json.loads(command_json)
        if command is not None and not (
            isinstance(command, list) and all(isinstance(item, str) and item for item in command)
        ):
            raise ValueError("draft-review agent command must be a JSON array of non-empty strings")

        adapter = (
            env.get("VIDEO_PIPELINE_DRAFT_REVIEW_AGENT")
            or agent_values.get("adapter")
            or "auto"
        )
        result = cls(
            chunk_length_sec=int(
                env.get("VIDEO_PIPELINE_DRAFT_REVIEW_CHUNK_LENGTH")
                or values.get("chunk_length_sec")
                or legacy.get("chunk_length_sec", 300)
            ),
            max_images_per_chunk=int(
                env.get("VIDEO_PIPELINE_DRAFT_REVIEW_MAX_IMAGES")
                or values.get("max_images_per_chunk")
                or legacy.get("max_images_per_chunk", 18)
            ),
            max_agent_calls_per_video=int(
                env.get("VIDEO_PIPELINE_DRAFT_REVIEW_MAX_AGENT_CALLS")
                or env.get("VIDEO_PIPELINE_MAX_GLM_CALLS")
                or values.get("max_agent_calls_per_video")
                or legacy.get("max_glm_calls_per_video", 6)
            ),
            agent=ReviewAgentSettings(
                adapter=str(adapter),
                command=command,
                timeout_sec=int(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_AGENT_TIMEOUT")
                    or agent_values.get("timeout_sec")
                    or legacy.get("glm_timeout_sec", 600)
                ),
                max_retries=int(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_AGENT_RETRIES")
                    or agent_values.get("max_retries")
                    or legacy.get("glm_max_retries", 2)
                ),
                api_base_url=(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_API_BASE_URL")
                    or env.get("VIDEO_PIPELINE_GLM_BASE_URL")
                    or agent_values.get("api_base_url")
                    or legacy.get("glm_base_url", "")
                ),
                api_key=(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_API_KEY")
                    or env.get("VIDEO_PIPELINE_GLM_API_KEY")
                    or agent_values.get("api_key")
                    or legacy.get("glm_api_key", "")
                ),
                api_model=(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_API_MODEL")
                    or env.get("VIDEO_PIPELINE_GLM_MODEL")
                    or agent_values.get("api_model")
                    or legacy.get("glm_model", "")
                ),
                claude_code_command=(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_CLAUDE_COMMAND")
                    or env.get("VIDEO_PIPELINE_CLAUDE_COMMAND")
                    or agent_values.get("claude_code_command")
                    or legacy.get("claude_code_command", "claude")
                ),
                claude_code_model=(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_CLAUDE_MODEL")
                    or env.get("VIDEO_PIPELINE_CLAUDE_MODEL")
                    or agent_values.get("claude_code_model")
                    or legacy.get("claude_code_model", "sonnet")
                ),
                claude_code_max_budget_usd=float(
                    env.get("VIDEO_PIPELINE_DRAFT_REVIEW_CLAUDE_MAX_BUDGET_USD")
                    or env.get("VIDEO_PIPELINE_CLAUDE_MAX_BUDGET_USD")
                    or agent_values.get("claude_code_max_budget_usd")
                    or legacy.get("claude_code_max_budget_usd", 0.10)
                ),
            ),
        )
        if result.chunk_length_sec <= 0 or result.max_images_per_chunk <= 0:
            raise ValueError("draft-review chunk length and image limit must be greater than zero")
        if result.max_agent_calls_per_video <= 0:
            raise ValueError("draft-review max agent calls must be greater than zero")
        if result.agent.timeout_sec <= 0 or result.agent.max_retries < 0:
            raise ValueError("draft-review agent timeout/retries are invalid")
        if result.agent.claude_code_max_budget_usd <= 0:
            raise ValueError("draft-review Claude Code budget must be greater than zero")
        return result
