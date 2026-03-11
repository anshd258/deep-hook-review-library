"""High-level entry point that wires together graph + LLM + optional MCP."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional, Union

from deep_hook.agent.graph import build_review_graph
from deep_hook.core.exceptions import AgentError
from deep_hook.core.models import DeepConfig, GitLabChange, ReviewResult
from deep_hook.llm.provider import get_llm

logger = logging.getLogger(__name__)

MCPFetcher = Callable[[list[GitLabChange]], Union[str, Awaitable[str]]]


def run_review(
    changes: list[GitLabChange],
    config: DeepConfig,
    *,
    mcp_fetcher: Optional[MCPFetcher] = None,
    previous_review: Optional[str] = None,
) -> ReviewResult:
    """Execute a full code review on a list of GitLab-style changes.

    Parameters
    ----------
    changes
        File changes — typically from the GitLab
        ``GET /projects/:id/merge_requests/:mr/changes`` API.
    config
        Active ``DeepConfig`` (can be loaded from YAML or constructed inline).
    mcp_fetcher
        Optional callable that receives the change list and returns
        extra review guidelines as a string.  This lets the consumer
        plug in any MCP server or external service for context-aware
        guidelines (e.g. fetching team coding standards, ADRs, or
        component ownership info).

        Signature: ``(changes: list[GitLabChange]) -> str``

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

    extra_guidelines = _fetch_mcp_guidelines(mcp_fetcher, non_empty)

    llm = get_llm(config)
    graph = build_review_graph(
        llm,
        config,
        non_empty,
        extra_guidelines=extra_guidelines,
        previous_review=previous_review,
    )

    initial_state = {
        "messages": [],
        "review_result": None,
        "error": None,
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        raise AgentError(f"Agent execution failed: {exc}") from exc

    result: ReviewResult = final_state.get("review_result") or ReviewResult(
        raw_output="Agent produced no result.",
        tldr=["Review agent did not produce a structured result."],
    )

    error = final_state.get("error")
    if error:
        logger.warning("Agent completed with parse warning: %s", error)

    return result


def _fetch_mcp_guidelines(
    fetcher: Optional[MCPFetcher],
    changes: list[GitLabChange],
) -> str:
    if fetcher is None:
        return ""
    try:
        result = fetcher(changes)
        if hasattr(result, "__await__"):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(result)
        return result if isinstance(result, str) else str(result)
    except Exception as exc:
        logger.warning("MCP guideline fetch failed (continuing without): %s", exc)
        return ""
