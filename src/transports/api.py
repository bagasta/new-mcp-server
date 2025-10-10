"""REST API transport for the MCP Calculator server."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from fastapi import FastAPI, HTTPException
from fastmcp.server.context import Context
from fastmcp.tools.tool import Tool, ToolResult
from mcp.types import ContentBlock
from pydantic import BaseModel, Field
import uvicorn

from src.server import mcp


class ToolRequest(BaseModel):
    """Request model for executing a calculator tool."""

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


app = FastAPI(title="MCP Calculator - REST API Transport")


def _serialize_tool(tool: Tool) -> ToolMetadata:
    """Convert a FastMCP Tool to API-friendly metadata."""
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


@app.get("/")
async def root() -> Dict[str, Any]:
    """Return API metadata."""
    return {
        "message": "MCP Calculator REST API",
        "version": "0.1.0",
    }


@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List available calculator tools."""
    tools = await mcp.get_tools()
    serialized = [_serialize_tool(tool) for tool in tools.values()]
    return {"tools": serialized}


@app.post("/execute")
async def execute_tool(request: ToolRequest) -> Dict[str, Any]:
    """Execute a calculator tool."""
    try:
        async with Context(fastmcp=mcp):
            tool_result = await mcp._call_tool(request.tool_name, request.arguments)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - return clean error message
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "result": _serialize_tool_result(tool_result)}


def run_api(host: str = "0.0.0.0", port: int = 8002) -> None:
    """Run the REST API transport.

    Args:
        host: Hostname to bind the server to.
        port: TCP port to listen on.
    """
    print(f"Starting MCP Calculator Server with REST API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_api()
