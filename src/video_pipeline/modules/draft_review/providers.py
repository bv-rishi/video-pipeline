from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...agent_contract import AgentError, AgentTask, CommandAgent, NoAgent, validate_agent_output
from ...models import Issue
from ...util import read_json, write_json
from .config import DraftReviewSettings


class ProviderError(RuntimeError):
    pass


def _decode_json_value(value: str | dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise ProviderError("The agent did not return valid issue JSON")
            value = json.loads(cleaned[start:end + 1])
    return value


def parse_issues(value: str | dict[str, Any] | list[Any], source: str = "agent") -> list[Issue]:
    value = _decode_json_value(value)
    rows = value if isinstance(value, list) else value.get("issues", [])
    if not isinstance(rows, list):
        raise ProviderError("The agent response has no issues array")
    issues = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("title"):
            continue
        issues.append(Issue(
            timestamp_sec=row.get("timestamp_sec", 0), end_sec=row.get("end_sec"),
            title=str(row.get("title", "Review issue")), problem=str(row.get("problem", "")),
            fix=str(row.get("fix", "Inspect and correct this section.")),
            severity=str(row.get("severity", "needs_decision")),
            category=str(row.get("category", "editorial")), confidence=row.get("confidence", 0.5),
            evidence_frame=row.get("evidence_frame"), source=source,
        ))
    return issues


ISSUE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp_sec": {"type": "number", "minimum": 0},
                    "end_sec": {"type": ["number", "null"], "minimum": 0},
                    "title": {"type": "string"},
                    "problem": {"type": "string"},
                    "fix": {"type": "string"},
                    "severity": {"type": "string", "enum": ["required", "suggestion", "needs_decision"]},
                    "category": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_frame": {"type": ["string", "null"]},
                },
                "required": ["timestamp_sec", "title", "problem", "fix", "severity", "category", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["issues"],
    "additionalProperties": False,
}


class BaseProvider:
    name = "base"
    model = "none"
    semantic_complete = True

    def review(self, system_prompt: str, prompt: str, images: list[Path], cache_path: Path) -> tuple[list[Issue], dict[str, Any]]:
        raise NotImplementedError

    def signature(self, system_prompt: str, prompt: str, images: list[Path]) -> str:
        material = {
            "provider": self.name,
            "model": self.model,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "images": [(path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in images if path.exists()],
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


class NoneProvider(BaseProvider):
    """Complete deterministic preparation without pretending semantic review ran."""

    name = "none"
    model = "none"
    semantic_complete = False

    def __init__(self):
        self.agent = NoAgent()

    def review(self, system_prompt: str, prompt: str, images: list[Path], cache_path: Path) -> tuple[list[Issue], dict[str, Any]]:
        task = AgentTask(
            module="draft-review", task="review-chunk", system_prompt=system_prompt,
            prompt=prompt, response_schema=ISSUE_RESPONSE_SCHEMA, evidence_files=images,
        )
        result = self.agent.run(task, cache_path)
        return [], {**result.usage, "semantic_complete": result.complete}


class MockProvider(BaseProvider):
    name = "mock"
    model = "deterministic-test"

    def review(self, system_prompt: str, prompt: str, images: list[Path], cache_path: Path) -> tuple[list[Issue], dict[str, Any]]:
        signature = self.signature(system_prompt, prompt, images)
        if cache_path.exists():
            cached = read_json(cache_path, {})
            if cached.get("signature") == signature:
                return [], {"calls": 0, "cached": True}
        payload = {"issues": [], "usage": {"calls": 0, "cached": False}, "signature": signature}
        write_json(cache_path, payload)
        return [], payload["usage"]


class OpenAICompatibleProvider(BaseProvider):
    name = "openai-compatible"

    def __init__(self, settings: DraftReviewSettings, text_only: bool = False):
        if not (settings.agent.api_key and settings.agent.api_base_url and settings.agent.api_model):
            raise ProviderError("The draft-review compatible API URL, model and key are not fully configured")
        self.settings = settings
        self.model = settings.agent.api_model
        self.text_only = text_only

    def signature(self, system_prompt: str, prompt: str, images: list[Path]) -> str:
        base = super().signature(system_prompt, prompt, images)
        return hashlib.sha256(f"{base}:text_only={self.text_only}".encode()).hexdigest()

    def review(self, system_prompt: str, prompt: str, images: list[Path], cache_path: Path) -> tuple[list[Issue], dict[str, Any]]:
        signature = self.signature(system_prompt, prompt, images)
        if cache_path.exists():
            cached = read_json(cache_path, {})
            if cached.get("signature") == signature:
                return parse_issues(cached.get("response", cached), self.name), {**cached.get("usage", {}), "cached": True}

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if not self.text_only:
            for image in images:
                mime = mimetypes.guess_type(image.name)[0] or "image/jpeg"
                encoded = base64.b64encode(image.read_bytes()).decode("ascii")
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}})
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}],
            "temperature": 0.1,
            "stream": False,
        }
        base = self.settings.agent.api_base_url.rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.settings.agent.max_retries + 1):
            try:
                request = Request(url, data=body, method="POST", headers={
                    "Authorization": f"Bearer {self.settings.agent.api_key}",
                    "Content-Type": "application/json",
                })
                with urlopen(request, timeout=self.settings.agent.timeout_sec) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                answer = raw["choices"][0]["message"]["content"]
                parsed_answer = _decode_json_value(answer)
                validation_errors = validate_agent_output(parsed_answer, ISSUE_RESPONSE_SCHEMA)
                if validation_errors:
                    raise ProviderError("Compatible API returned schema-invalid JSON: " + "; ".join(validation_errors[:8]))
                stored = {
                    "response": parsed_answer,
                    "usage": raw.get("usage", {}),
                    "model": raw.get("model", self.model),
                    "signature": signature,
                }
                write_json(cache_path, stored)
                return parse_issues(parsed_answer, self.name), {**raw.get("usage", {}), "calls": 1, "cached": False}
            except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError, ProviderError) as error:
                last_error = error
                if attempt < self.settings.agent.max_retries:
                    time.sleep(min(2 ** attempt, 4))
        raise ProviderError(
            f"OpenAI-compatible request failed after {self.settings.agent.max_retries + 1} attempts: {last_error}"
        )


class CommandProvider(BaseProvider):
    name = "command"

    def __init__(self, settings: DraftReviewSettings):
        if not settings.agent.command:
            raise ProviderError("The draft-review agent command is not configured")
        model_hash = hashlib.sha256(json.dumps(settings.agent.command).encode()).hexdigest()[:12]
        self.model = "command-" + model_hash
        self.agent = CommandAgent(
            settings.agent.command,
            timeout_sec=settings.agent.timeout_sec,
            model=self.model,
        )

    def review(self, system_prompt: str, prompt: str, images: list[Path], cache_path: Path) -> tuple[list[Issue], dict[str, Any]]:
        task = AgentTask(
            module="draft-review", task="review-chunk", system_prompt=system_prompt,
            prompt=prompt, response_schema=ISSUE_RESPONSE_SCHEMA, evidence_files=images,
        )
        try:
            result = self.agent.run(task, cache_path)
        except AgentError as error:
            raise ProviderError(str(error)) from error
        return parse_issues(result.output, self.name), result.usage


class ClaudeCodeProvider(BaseProvider):
    """Optional adapter for an existing Claude Code route and its configured model."""

    name = "claude-code"

    def __init__(self, settings: DraftReviewSettings, text_only: bool = False):
        executable = shutil.which(settings.agent.claude_code_command)
        if not executable:
            raise ProviderError(f"Claude Code command is not installed: {settings.agent.claude_code_command}")
        self.settings = settings
        self.executable = executable
        self.text_only = text_only
        self.model = settings.agent.claude_code_model

    def signature(self, system_prompt: str, prompt: str, images: list[Path]) -> str:
        base = super().signature(system_prompt, prompt, images)
        return hashlib.sha256(
            f"{base}:text_only={self.text_only}:budget={self.settings.agent.claude_code_max_budget_usd}".encode()
        ).hexdigest()

    def review(self, system_prompt: str, prompt: str, images: list[Path], cache_path: Path) -> tuple[list[Issue], dict[str, Any]]:
        signature = self.signature(system_prompt, prompt, images)
        if cache_path.exists():
            cached = read_json(cache_path, {})
            if cached.get("signature") == signature:
                return parse_issues(cached.get("response", cached), self.name), {**cached.get("usage", {}), "cached": True}

        usable_images = [path.resolve() for path in images if path.exists()] if not self.text_only else []
        model_prompt = prompt
        if usable_images:
            model_prompt += "\n\nLOCAL EVIDENCE IMAGES (read only these files):\n" + "\n".join(
                f"- {path}" for path in usable_images
            )
        args = [
            self.executable, "--print", "--output-format", "json",
            "--json-schema", json.dumps(ISSUE_RESPONSE_SCHEMA, separators=(",", ":")),
            "--no-session-persistence", "--disable-slash-commands", "--no-chrome",
            "--setting-sources", "user", "--permission-mode", "dontAsk",
            "--model", self.model,
            "--max-budget-usd", str(self.settings.agent.claude_code_max_budget_usd),
            "--system-prompt", system_prompt,
        ]
        if usable_images:
            args.extend(["--tools", "Read", "--allowedTools", "Read"])
            for directory in sorted({str(path.parent) for path in usable_images}):
                args.extend(["--add-dir", directory])
        else:
            args.extend(["--tools", ""])
        result = subprocess.run(
            args, input=model_prompt, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=self.settings.agent.timeout_sec, check=False, cwd=cache_path.parent,
        )
        if result.returncode:
            detail = result.stderr.strip()[-500:] or result.stdout.strip()[-500:]
            raise ProviderError(f"Claude Code exited with {result.returncode}: {detail}")
        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ProviderError(f"Claude Code did not return its JSON result envelope: {error}") from error
        if envelope.get("is_error"):
            raise ProviderError(f"Claude Code reported an error: {envelope.get('result', 'unknown error')}")
        answer = envelope.get("structured_output")
        if answer is None:
            answer = envelope.get("result", envelope)
        answer = _decode_json_value(answer)
        validation_errors = validate_agent_output(answer, ISSUE_RESPONSE_SCHEMA)
        if validation_errors:
            raise ProviderError("Claude Code returned schema-invalid JSON: " + "; ".join(validation_errors[:8]))
        issues = parse_issues(answer, self.name)
        raw_usage = envelope.get("usage", {}) if isinstance(envelope, dict) else {}
        usage = {
            "calls": 1,
            "cached": False,
            "prompt_tokens": int(raw_usage.get("input_tokens", raw_usage.get("prompt_tokens", 0)) or 0),
            "completion_tokens": int(raw_usage.get("output_tokens", raw_usage.get("completion_tokens", 0)) or 0),
        }
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        stored = {
            "response": {"issues": [item.to_dict() for item in issues]},
            "usage": usage,
            "model": envelope.get("model", self.model) if isinstance(envelope, dict) else self.model,
            "signature": signature,
        }
        write_json(cache_path, stored)
        return issues, usage


def make_provider(name: str, settings: DraftReviewSettings, text_only: bool = False) -> BaseProvider:
    selected = name
    if selected == "auto" and settings.agent.adapter != "auto":
        selected = settings.agent.adapter
    if selected == "auto":
        if settings.agent.command:
            selected = "command"
        elif shutil.which(settings.agent.claude_code_command):
            selected = "claude-code"
        elif settings.agent.api_key and settings.agent.api_base_url and settings.agent.api_model:
            selected = "openai-compatible"
        else:
            selected = "none"
    if selected == "none":
        return NoneProvider()
    if selected == "mock":
        return MockProvider()
    if selected == "claude-code":
        return ClaudeCodeProvider(settings, text_only=text_only)
    if selected == "command":
        return CommandProvider(settings)
    if selected in {"glm", "openai-compatible"}:
        return OpenAICompatibleProvider(settings, text_only=text_only)
    raise ProviderError(f"Unknown draft-review agent adapter: {selected}")
