"""LangGraph review agent.

Simplified linear pipeline:

    prepare → review → parse → END

No tool-calling loop — all context (diffs, guidelines) is provided
upfront via the GitLabChange list.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from deep_hook.agent.parser import parse_review_output
from deep_hook.agent.state import ReviewState
from deep_hook.core.models import DeepConfig, GitLabChange, ReviewResult
from deep_hook.core.prompts import build_review_prompt, build_system_prompt


def build_review_graph(
    llm: BaseChatModel,
    config: DeepConfig,
    changes: list[GitLabChange],
    *,
    extra_guidelines: str = "",
    previous_review: str | None = None,
) -> StateGraph:
    """Construct and compile the review agent graph."""

    def prepare(state: ReviewState) -> dict:
        system = build_system_prompt(config)
        user = build_review_prompt(
            changes,
            config,
            extra_guidelines=extra_guidelines,
            previous_review=previous_review,
        )
        return {
            "messages": [SystemMessage(content=system), HumanMessage(content=user)],
        }

    def review(state: ReviewState) -> dict:
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    def parse(state: ReviewState) -> dict:
        last = state["messages"][-1]
        raw = last.content if hasattr(last, "content") else str(last)
        try:
            result = parse_review_output(raw)
        except Exception as exc:
            return {
                "review_result": ReviewResult(raw_output=raw),
                "error": f"Parse error: {exc}",
            }
        return {"review_result": result}

    graph = StateGraph(ReviewState)

    graph.add_node("prepare", prepare)
    graph.add_node("review", review)
    graph.add_node("parse", parse)

    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "review")
    graph.add_edge("review", "parse")
    graph.add_edge("parse", END)

    return graph.compile()
