"""Load MCP tools from configured servers using langchain-mcp-adapters."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StreamableHttpConnection

from deep_hook_review.core.models import DeepConfig

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


async def load_mcp_tools(config: DeepConfig) -> list[BaseTool]:
    """Discover and return LangChain tools from all configured MCP servers.

    Returns an empty list when MCP is not configured.
    Raises on failure so the caller can abort the review.
    """
    if not config.mcp or not config.mcp.enabled:
        return []

    connections: dict = {}
    for server in config.mcp.servers:
        connections[server.name] = StreamableHttpConnection(
            transport="streamable_http",
            url=server.url,
            headers=server.headers or None,
        )

    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    logger.info("Loaded %d MCP tool(s) from %d server(s)", len(tools), len(connections))
    return tools
