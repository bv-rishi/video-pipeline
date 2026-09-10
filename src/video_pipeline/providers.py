"""Compatibility imports for the pre-0.2 draft-review provider API.

New code should import from ``video_pipeline.modules.draft_review.providers``.
The shared core does not depend on this module.
"""

from .modules.draft_review.providers import (
    BaseProvider,
    ClaudeCodeProvider,
    CommandProvider,
    ISSUE_RESPONSE_SCHEMA,
    MockProvider,
    NoneProvider,
    OpenAICompatibleProvider,
    ProviderError,
    make_provider,
    parse_issues,
)

__all__ = [
    "BaseProvider",
    "ClaudeCodeProvider",
    "CommandProvider",
    "ISSUE_RESPONSE_SCHEMA",
    "MockProvider",
    "NoneProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "make_provider",
    "parse_issues",
]
