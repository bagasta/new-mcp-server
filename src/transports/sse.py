"""Server-Sent Events (SSE) transport for the MCP Calculator server."""

from __future__ import annotations

from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse  # noqa: F401 imported to ensure dependency is present
import uvicorn

from src.server import mcp

__all__ = ["app", "run_sse", "EventSourceResponse"]

_sse_app = mcp.http_app(path="/sse", transport="sse")

app = FastAPI(
    title="MCP Calculator - SSE Transport",
    lifespan=_sse_app.lifespan,
)
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
