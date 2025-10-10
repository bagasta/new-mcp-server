"""Async client for interacting with the MCP Calculator REST API."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx


logger = logging.getLogger("playground.mcp_client")


class MCPClient:
    """Client for communicating with the MCP Calculator REST transport."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL of the MCP REST API. If omitted, the client uses the
                ``MCP_API_BASE_URL`` environment variable or defaults to
                ``http://localhost:8002``.
        """
        fallback_url = os.getenv("MCP_API_BASE_URL", "http://localhost:8002")
        resolved_base_url = (base_url or fallback_url).rstrip("/")
        self.base_url = resolved_base_url
        self._client = httpx.AsyncClient(base_url=self.base_url)
        logger.info("Initialized MCPClient with base URL %s", self.base_url)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Retrieve the list of available tools.

        Returns:
            A list of tool metadata dictionaries.
        """
        response = await self._request("GET", "/tools")
        payload = response.json()
        tools = payload.get("tools", [])
        logger.info("Retrieved %d tools from MCP REST API", len(tools))
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a specific tool.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments to pass to the tool.

        Returns:
            The tool execution result.

        Raises:
            ValueError: If the response indicates a failure.
        """
        logger.info(
            "Executing MCP tool '%s' with arguments %s",
            tool_name,
            arguments,
        )
        response = await self._request(
            "POST",
            "/execute",
            json={"tool_name": tool_name, "arguments": arguments},
        )
        payload = response.json()
        if not payload.get("success", False):
            logger.error("MCP tool '%s' execution failed: %s", tool_name, payload)
            raise ValueError(f"Tool execution failed: {payload}")
        logger.info("MCP tool '%s' execution succeeded", tool_name)
        return payload.get("result")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
        logger.info("Closed MCPClient HTTP session")

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Issue an HTTP request with standardized error handling."""
        full_url = f"{self.base_url}{url}"
        logger.info("MCPClient request %s %s", method, full_url)
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "MCPClient request %s %s returned status %s",
                method,
                full_url,
                exc.response.status_code,
            )
            raise
        except httpx.RequestError as exc:  # noqa: BLE001 - provide user guidance
            logger.error(
                "MCPClient request %s %s failed: %s",
                method,
                full_url,
                exc,
            )
            raise ConnectionError(
                "Unable to reach the MCP REST API. "
                "Ensure `python -m src.transports.api` is running "
                f"at {self.base_url}."
            ) from exc

        logger.info(
            "MCPClient request %s %s completed with status %s",
            method,
            full_url,
            response.status_code,
        )
        return response
