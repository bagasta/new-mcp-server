"""Server-Sent Events (SSE) transport for the MCP Calculator server."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from fastapi import FastAPI, HTTPException
from fastmcp.server.context import Context
from fastmcp.tools.tool import Tool, ToolResult
from mcp.types import ContentBlock
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse  # noqa: F401 imported to ensure dependency is present
import uvicorn

from src.server import mcp

__all__ = ["app", "run_sse", "EventSourceResponse"]

_sse_app = mcp.http_app(path="/sse", transport="sse")


class ToolRequest(BaseModel):
    """Request model for executing a tool over the SSE transport."""

    tool_name: str = Field(..., description="Name of the tool to execute.")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the tool."
    )


class ToolMetadata(BaseModel):
    """Metadata describing an available tool."""

    name: str
    description: str | None
    parameters: Dict[str, Any]
    output_schema: Dict[str, Any] | None


def _serialize_tool(tool: Tool) -> ToolMetadata:
    """Convert a FastMCP Tool into API-friendly metadata."""
    return ToolMetadata(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters or {},
        output_schema=tool.output_schema,
    )


def _serialize_content(blocks: Iterable[ContentBlock]) -> List[Dict[str, Any]]:
    """Convert content blocks to JSON-serializable dictionaries."""
    return [block.model_dump(mode="json") for block in blocks]


def _serialize_tool_result(result: ToolResult) -> Dict[str, Any]:
    """Normalize a ToolResult for JSON responses."""
    if result.structured_content is not None:
        return result.structured_content
    return {"content": _serialize_content(result.content)}


app = FastAPI(
    title="MCP Calculator - SSE Transport",
    lifespan=_sse_app.lifespan,
)


@app.get("/")
async def root() -> Dict[str, Any]:
    """Return transport metadata."""
    return {
        "message": "MCP Calculator SSE transport",
        "version": "0.1.0",
        "sse_endpoint": "/sse",
    }


@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List available tools (mirrors REST transport)."""
    tools = await mcp.get_tools()
    serialized = [_serialize_tool(tool) for tool in tools.values()]
    return {"tools": serialized}


@app.post("/execute")
async def execute_tool(request: ToolRequest) -> Dict[str, Any]:
    """Execute a tool using the same payload format as the REST transport."""
    try:
        async with Context(fastmcp=mcp):
            tool_result = await mcp._call_tool(request.tool_name, request.arguments)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surface clean error
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "result": _serialize_tool_result(tool_result)}


app.mount("/", _sse_app)


def run_sse(host: str = "0.0.0.0", port: int = 8190) -> None:
    """Run the server using the SSE transport.

    Args:
        host: Hostname to bind the server to.
        port: TCP port to listen on.
    """
    print(f"Starting MCP Calculator Server with SSE transport on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_sse()
