from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModuleDescriptor:
    name: str
    command: str
    status: str
    purpose: str
    agent_policy: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


MODULES = (
    ModuleDescriptor(
        name="draft-review",
        command="video-draft-review",
        status="production_mvp",
        purpose="Review an edited tutorial against its approved script and editing rules.",
        agent_policy="optional_per_module_adapter",
    ),
    ModuleDescriptor(
        name="conformer",
        command="video-conformer",
        status="benchmark_components",
        purpose="Conform host takes and match screen footage into a Final Cut rough cut.",
        agent_policy="optional_per_module_adapter",
    ),
)


def list_modules() -> list[dict[str, str]]:
    return [module.to_dict() for module in MODULES]
