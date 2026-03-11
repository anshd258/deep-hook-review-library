"""Agent state definition for the LangGraph review workflow."""

from __future__ import annotations

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from deep_hook.core.models import ReviewResult


class ReviewState(TypedDict):
    """State that flows through the LangGraph review pipeline.

    Fields
    ------
    messages
        LangChain message list (system + human + AI).  Uses the built-in
        ``add_messages`` reducer so each node can append.
    review_result
        Parsed structured review produced by the parser node.
    error
        Set by any node that encounters a non-recoverable failure.
    """

    messages: Annotated[list, add_messages]
    review_result: Optional[ReviewResult]
    error: Optional[str]
