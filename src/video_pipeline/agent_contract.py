from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Protocol

from .util import read_json, write_json


AGENT_CONTRACT_VERSION = "video-pipeline-agent-task/1"


class AgentError(RuntimeError):
    pass


def validate_agent_output(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate the small JSON Schema subset used by pipeline module contracts."""
    errors: list[str] = []
    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected] if expected else []
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected_types and not any(type_checks.get(name, lambda item: True)(value) for name in expected_types):
        return [f"{path} must be {' or '.join(expected_types)}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} is not an allowed value")
    if isinstance(value, dict):
        required = schema.get("required", [])
        errors.extend(f"{path}.{key} is required" for key in required if key not in value)
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_agent_output(item, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key} is not allowed")
    elif isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            errors.append(f"{path} has too few items")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{path} has too many items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_agent_output(item, item_schema, f"{path}[{index}]"))
    elif isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            errors.append(f"{path} is too short")
        if schema.get("pattern") and not re.search(str(schema["pattern"]), value):
            errors.append(f"{path} does not match the required pattern")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} is below the minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} is above the maximum")
    return errors


@dataclass
class AgentTask:
    module: str
    task: str
    system_prompt: str
    prompt: str
    response_schema: dict[str, Any]
    evidence_files: list[Path] = field(default_factory=list)
    contract_version: str = AGENT_CONTRACT_VERSION

    def serializable(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "module": self.module,
            "task": self.task,
            "system_prompt": self.system_prompt,
            "prompt": self.prompt,
            "response_schema": self.response_schema,
            "evidence_files": [str(path.resolve()) for path in self.evidence_files if path.exists()],
        }

    def signature(self, adapter: str, model: str) -> str:
        material = self.serializable()
        material["adapter"] = adapter
        material["model"] = model
        material["evidence"] = [
            (path.name, path.stat().st_size, path.stat().st_mtime_ns)
            for path in self.evidence_files if path.exists()
        ]
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class AgentResult:
    output: Any
    adapter: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    complete: bool = True


class AgentAdapter(Protocol):
    name: str
    model: str

    def run(self, task: AgentTask, cache_path: Path) -> AgentResult: ...


class CommandAgent:
    """Run any configured agent command without invoking a shell.

    The command may use ``{request_file}``, ``{response_file}``, or
    ``{evidence_manifest}`` placeholders. It writes JSON to the response file
    or stdout. This adapter deliberately has no Codex, Claude, or GLM logic.
    """

    name = "command"

    def __init__(self, command: list[str], *, timeout_sec: int = 600, model: str = "configured-command"):
        if not command:
            raise AgentError("An agent command is not configured")
        self.command = command
        self.timeout_sec = timeout_sec
        self.model = model

    def run(self, task: AgentTask, cache_path: Path) -> AgentResult:
        signature = task.signature(self.name, self.model)
        if cache_path.exists():
            cached = read_json(cache_path, {})
            if cached.get("signature") == signature:
                return AgentResult(
                    output=cached.get("output"), adapter=self.name, model=self.model,
                    usage={**cached.get("usage", {}), "cached": True},
                )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        request_path = cache_path.with_suffix(".request.json")
        response_path = cache_path.with_suffix(".response.json")
        evidence_path = cache_path.with_suffix(".evidence.json")
        response_path.unlink(missing_ok=True)
        write_json(request_path, task.serializable())
        write_json(evidence_path, [str(path.resolve()) for path in task.evidence_files if path.exists()])
        replacements = {
            "{request_file}": str(request_path),
            "{response_file}": str(response_path),
            "{evidence_manifest}": str(evidence_path),
        }
        args = []
        for configured in self.command:
            value = configured
            for key, replacement in replacements.items():
                value = value.replace(key, replacement)
            args.append(value)
        result = subprocess.run(
            args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=self.timeout_sec, check=False,
        )
        if result.returncode:
            raise AgentError(f"Agent command exited with {result.returncode}: {result.stderr[-500:]}")
        raw = response_path.read_text(encoding="utf-8") if response_path.exists() else result.stdout
        try:
            output = json.loads(raw)
        except json.JSONDecodeError as error:
            raise AgentError(f"Agent command did not return JSON: {error}") from error
        validation_errors = validate_agent_output(output, task.response_schema)
        if validation_errors:
            raise AgentError("Agent command returned schema-invalid JSON: " + "; ".join(validation_errors[:8]))
        usage = {"calls": 1, "cached": False}
        write_json(cache_path, {
            "contract_version": task.contract_version,
            "output": output,
            "usage": usage,
            "adapter": self.name,
            "model": self.model,
            "signature": signature,
        })
        return AgentResult(output=output, adapter=self.name, model=self.model, usage=usage)


class NoAgent:
    name = "none"
    model = "none"

    def run(self, task: AgentTask, cache_path: Path) -> AgentResult:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(cache_path.with_suffix(".request.json"), task.serializable())
        write_json(cache_path, {
            "contract_version": task.contract_version,
            "status": "awaiting_agent",
            "adapter": self.name,
            "model": self.model,
            "usage": {"calls": 0, "cached": False},
            "signature": task.signature(self.name, self.model),
        })
        return AgentResult(
            output={}, adapter=self.name, model=self.model,
            usage={"calls": 0, "cached": False}, complete=False,
        )
