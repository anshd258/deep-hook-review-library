"""Review agent builder.

Uses ``create_agent`` from LangChain to create a compiled graph that
handles the LLM ⇄ tool loop automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


def build_review_agent(
    llm: BaseChatModel,
    *,
    tools: Sequence[BaseTool] = (),
    system_prompt: str = "",
):
    """Create a review agent with automatic tool handling.

    Parameters
    ----------
    llm
        LangChain chat model instance.
    tools
        MCP or other LangChain tools the agent may call during review.
    system_prompt
        System prompt that instructs the model on review format / guidelines.
    """
    return create_agent(
        llm,
        tools=list(tools) if tools else None,
        system_prompt=system_prompt or None,
    )
