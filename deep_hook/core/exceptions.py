"""Centralized exception hierarchy for Deep Hook."""


class DeepHookError(Exception):
    """Base exception for all Deep Hook errors."""


class ConfigError(DeepHookError):
    """Configuration loading or validation error."""


class LLMError(DeepHookError):
    """LLM provider error (auth, timeout, API failure)."""


class AgentError(DeepHookError):
    """Agent orchestration error."""
