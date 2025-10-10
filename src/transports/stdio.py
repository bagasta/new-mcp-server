"""STDIO transport entry point for the MCP Calculator server."""

from __future__ import annotations

import sys

from src.server import mcp


def run_stdio() -> None:
    """Run the server using the STDIO transport."""
    print("Starting MCP Calculator Server with STDIO transport...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
