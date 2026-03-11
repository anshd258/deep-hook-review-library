"""Core domain models for Deep Hook.

All Pydantic v2 models used across the system live here.
This module has no internal dependencies to avoid circular imports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class Language(str, Enum):
    FLUTTER = "flutter"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    OTHER = "other"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


# ── GitLab Change (input model) ───────────────────────────────────

class GitLabChange(BaseModel):
    """A single file change from the GitLab merge request API.

    This is the primary input format — consumers pass a list of these
    directly from the GitLab ``/merge_requests/:id/changes`` response.
    """
    old_path: str = ""
    new_path: str = ""
    a_mode: str = "100644"
    b_mode: str = "100644"
    diff: str = ""
    new_file: bool = False
    renamed_file: bool = False
    deleted_file: bool = False


# ── Configuration Models ──────────────────────────────────────────

class LLMConfig(BaseModel):
    provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    model: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    base_url: Optional[str] = Field(default=None, description="Custom API base URL (required for Ollama)")
    api_key: Optional[str] = Field(default=None, description="API key override (reads from env if None)")


class MCPConfig(BaseModel):
    """Configuration for an MCP server that provides additional review guidelines."""
    server_url: Optional[str] = Field(default=None, description="MCP server endpoint URL")
    tool_name: Optional[str] = Field(default=None, description="MCP tool to call for fetching guidelines")
    headers: dict[str, str] = Field(default_factory=dict, description="Extra headers for MCP calls")

    @property
    def enabled(self) -> bool:
        return bool(self.server_url and self.tool_name)


class FileGuideline(BaseModel):
    """Guidelines that apply to files matching a pattern."""
    pattern: str = Field(description="Glob pattern to match file paths (e.g. '*.py', 'src/api/**')")
    guidelines: list[str] = Field(default_factory=list)


class ReviewConfig(BaseModel):
    max_diff_lines: int = Field(default=3000, ge=100, le=10000)


class DeepConfig(BaseModel):
    language: Language = Field(default=Language.PYTHON)
    guidelines: list[str] = Field(default_factory=list, description="Global guidelines applied to all files")
    file_guidelines: list[FileGuideline] = Field(default_factory=list, description="Per-file-pattern guidelines")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)


# ── Review Models ─────────────────────────────────────────────────

class FileChange(BaseModel):
    file: str
    change: str


class Issue(BaseModel):
    file: str
    line: Optional[int] = None
    message: str
    severity: Severity

    @property
    def location(self) -> str:
        if self.line:
            return f"{self.file}:{self.line}"
        return self.file


class ReviewResult(BaseModel):
    tldr: list[str] = Field(default_factory=list)
    context: str = ""
    walkthrough: list[FileChange] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    flow: str = ""
    raw_output: str = ""

    @property
    def critical(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.CRITICAL]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def suggestions(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.SUGGESTION]

    @property
    def has_critical(self) -> bool:
        return len(self.critical) > 0

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def total_issues(self) -> int:
        return len(self.issues)
