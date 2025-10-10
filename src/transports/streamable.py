"""Streamable HTTP transport for the MCP Calculator server."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import StreamingResponse  # noqa: F401 imported to ensure dependency is present
import uvicorn

from src.server import mcp

__all__ = ["app", "run_streamable", "StreamingResponse"]

_streamable_app = mcp.http_app(path="/mcp", transport="streamable-http")

app = FastAPI(
    title="MCP Calculator - Streamable HTTP Transport",
    lifespan=_streamable_app.lifespan,
)
app.mount("/", _streamable_app)


def run_streamable(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Run the server using the streamable HTTP transport.

    Args:
        host: Hostname to bind the server to.
        port: TCP port to listen on.
    """
    print(f"Starting MCP Calculator Server with Streamable HTTP on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_streamable()
