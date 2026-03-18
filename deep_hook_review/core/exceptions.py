"""Centralized exception hierarchy for Deek Hook - Review."""


class DeepHookError(Exception):
    """Base exception for all Deek Hook - Review errors."""


class ConfigError(DeepHookError):
    """Configuration loading or validation error."""


class LLMError(DeepHookError):
    """LLM provider error (auth, timeout, API failure)."""


class AgentError(DeepHookError):
    """Agent orchestration error."""
