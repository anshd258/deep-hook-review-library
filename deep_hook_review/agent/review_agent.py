"""High-level entry point that wires together agent + LLM + optional MCP."""

from __future__ import annotations

import logging
from typing import Optional

from deep_hook_review.agent.graph import build_review_agent
from deep_hook_review.agent.parser import parse_review_output
from deep_hook_review.core.exceptions import AgentError
from deep_hook_review.core.models import DeepConfig, GitLabChange, ReviewResult
from deep_hook_review.core.prompts import build_review_prompt, build_system_prompt
from deep_hook_review.llm.provider import get_llm
from deep_hook_review.mcp.tools import load_mcp_tools

logger = logging.getLogger(__name__)


async def run_review(
    changes: list[GitLabChange],
    config: DeepConfig,
    *,
    previous_review: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ReviewResult:
    """Execute a full code review on a list of GitLab-style changes.

    Async: use ``await run_review(...)``. From sync code use
    ``asyncio.run(run_review(...))``. MCP tool load failures propagate
    and abort the review.

    Parameters
    ----------
    changes
        File changes — typically from the GitLab
        ``GET /projects/:id/merge_requests/:mr/changes`` API.
    config
        Active ``DeepConfig`` (can be loaded from YAML or constructed inline).
    previous_review
        Optional. Summary or full text of the previous review (e.g. from your
        memory/DB). When provided, the model is prompted to check if those
        issues were addressed and to avoid re-reporting fixed items.

    Returns
    -------
    ReviewResult
        Structured review output with issues, walkthrough, etc.
    """
    if not changes:
        return ReviewResult(tldr=["No changes to review."])

    non_empty = [c for c in changes if c.diff.strip()]
    if not non_empty:
        return ReviewResult(tldr=["All changes are empty (mode-only or binary)."])

    tools = await load_mcp_tools(config)
    llm = get_llm(config, api_key)

    system_prompt = build_system_prompt(config)
    user_message = build_review_prompt(
        non_empty,
        config,
        previous_review=previous_review,
    )

    agent = build_review_agent(
        llm,
        tools=tools,
        system_prompt=system_prompt,
    )

    try:
        final_state = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
        )
    except Exception as exc:
        raise AgentError(f"Agent execution failed: {exc}") from exc

    messages = final_state["messages"]
    tool_calls_used = _extract_tool_call_names(messages)

    last_msg = messages[-1]
    raw = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    try:
        result = parse_review_output(raw)
        return result.model_copy(update={"tool_calls_used": tool_calls_used})
    except Exception as exc:
        logger.warning("Parse warning: %s", exc)
        return ReviewResult(raw_output=raw, tool_calls_used=tool_calls_used)


def _extract_tool_call_names(messages: list) -> list[str]:
    """Collect tool names from agent messages (each AIMessage.tool_calls)."""
    names: list[str] = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if isinstance(tc, dict) and "name" in tc:
                    names.append(tc["name"])
                elif hasattr(tc, "get"):
                    names.append(tc.get("name", ""))
    return names

