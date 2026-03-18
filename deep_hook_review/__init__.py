"""Deek Hook - Review — AI-powered code review as an importable Python package.

Usage::

    from deep_hook_review import run_review, GitLabChange, config_from_yml

    changes = [
        GitLabChange(
            old_path="VERSION",
            new_path="VERSION",
            diff="@@ -1 +1 @@\\n-1.9.7\\n+1.9.8",
        ),
    ]

    config = config_from_yml("deep.yml")  # or config_from_yml() for cwd deep.yml
    result = run_review(changes, config)

    for issue in result.issues:
        print(f"[{issue.severity.value}] {issue.location}: {issue.message}")
"""

__version__ = "3.0.0"
__author__ = "anshdeep"

from deep_hook_review.agent.review_agent import run_review
from deep_hook_review.config.loader import config_from_yml, load_config
from deep_hook_review.core.exceptions import AgentError, ConfigError, DeepHookError, LLMError
from deep_hook_review.core.markdown import format_previous_review, generate_review_markdown
from deep_hook_review.core.models import (
    DeepConfig,
    FileChange,
    FileGuideline,
    GitLabChange,
    Issue,
    Language,
    LLMConfig,
    LLMProvider,
    MCPConfig,
    MCPServerConfig,
    ReviewConfig,
    ReviewResult,
    Severity,
)
from deep_hook_review.mcp.tools import load_mcp_tools

__all__ = [
    # Main entry point
    "run_review",
    "config_from_yml",
    "load_config",
    "generate_review_markdown",
    "format_previous_review",
    # Input model
    "GitLabChange",
    # Config
    "DeepConfig",
    "LLMConfig",
    "MCPConfig",
    "MCPServerConfig",
    "ReviewConfig",
    "FileGuideline",
    "Language",
    "LLMProvider",
    # Output models
    "ReviewResult",
    "Issue",
    "FileChange",
    "Severity",
    # MCP integration
    "load_mcp_tools",
    # Exceptions
    "DeepHookError",
    "ConfigError",
    "LLMError",
    "AgentError",
]
