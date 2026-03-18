"""LLM provider abstraction.

Returns a LangChain ``BaseChatModel`` configured from ``DeepConfig.llm``.
The rest of the system never imports provider-specific classes directly.
"""

from __future__ import annotations

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from deep_hook_review.core.exceptions import LLMError
from deep_hook_review.core.models import DeepConfig, LLMProvider


def get_llm(config: DeepConfig, api_key: Optional[str] = None) -> BaseChatModel:
    """Build and return a chat model from the active configuration."""
    llm_cfg = config.llm

    match llm_cfg.provider:
        case LLMProvider.OPENAI:
            return _build_openai(llm_cfg.model, llm_cfg.temperature, api_key, llm_cfg.base_url)
        case LLMProvider.ANTHROPIC:
            return _build_anthropic(llm_cfg.model, llm_cfg.temperature, api_key, llm_cfg.base_url)
        case LLMProvider.OLLAMA:
            return _build_ollama(llm_cfg.model, llm_cfg.temperature, llm_cfg.base_url)
        case _:
            raise LLMError(f"Unknown LLM provider: {llm_cfg.provider}")


# ── Provider builders ──────────────────────────────────────────────

def _build_openai(
    model: str,
    temperature: float,
    api_key: str | None,
    base_url: str | None,
) -> BaseChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise LLMError("Install langchain-openai: pip install langchain-openai") from exc

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise LLMError(
            "OpenAI API key not found. Set OPENAI_API_KEY env var or add api_key to deep.yml"
        )

    kwargs: dict = {"model": model, "temperature": temperature, "api_key": key}
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)


def _build_anthropic(
    model: str,
    temperature: float,
    api_key: str | None,
    base_url: str | None,
) -> BaseChatModel:
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise LLMError("Install langchain-anthropic: pip install langchain-anthropic") from exc

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError(
            "Anthropic API key not found. Set ANTHROPIC_API_KEY env var or add api_key to deep.yml"
        )

    kwargs: dict = {"model": model, "temperature": temperature, "api_key": key}
    if base_url:
        kwargs["base_url"] = base_url

    return ChatAnthropic(**kwargs)


def _build_ollama(
    model: str,
    temperature: float,
    base_url: str | None,
) -> BaseChatModel:
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise LLMError("Install langchain-ollama: pip install langchain-ollama") from exc

    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url or "http://localhost:11434",
    )
