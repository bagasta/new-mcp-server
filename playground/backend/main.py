"""FastAPI backend for the MCP Calculator playground."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .mcp_client import MCPClient
except ImportError:  # pragma: no cover - fallback for direct execution
    from mcp_client import MCPClient  # type: ignore[no-redef]

app = FastAPI(title="MCP Calculator Playground API")

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("playground.backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SSE_URL = os.getenv("MCP_SSE_URL", "http://localhost:8190/sse")

mcp_client = MCPClient()


class CalculationRequest(BaseModel):
    """Request body for natural-language calculations."""

    expression: str = Field(..., description="Natural language calculation prompt.")


class ToolExecutionRequest(BaseModel):
    """Request body for invoking a calculator tool."""

    tool_name: str = Field(..., description="Name of the tool to execute.")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the tool."
    )


@app.get("/")
async def root() -> Dict[str, str]:
    """Health endpoint."""
    return {"message": "MCP Calculator Playground API"}


@app.get("/tools")
async def get_tools() -> Dict[str, Any]:
    """Return available tools from the MCP server."""
    try:
        tools = await mcp_client.list_tools()
    except ConnectionError as exc:  # pragma: no cover - connection guidance
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface detailed error
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    logger.info("GET /tools returning %d tools", len(tools))
    return {"tools": tools}


@app.post("/execute")
async def execute_tool(request: ToolExecutionRequest) -> Dict[str, Any]:
    """Execute a specific calculator tool."""
    logger.info("POST /execute - tool=%s args=%s", request.tool_name, request.arguments)
    try:
        result = await mcp_client.execute_tool(request.tool_name, request.arguments)
    except ConnectionError as exc:  # pragma: no cover - connection guidance
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - convert to HTTP error
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("POST /execute - tool=%s result=%s", request.tool_name, result)
    return {"success": True, "result": result}


@app.post("/calculate")
async def calculate(request: CalculationRequest) -> Dict[str, Any]:
    """Execute a natural-language calculation using the LangChain agent."""
    logger.info("POST /calculate - expression='%s'", request.expression)
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured. Add it to your .env file to enable LangChain.",
        )

    try:
        from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOpenAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise HTTPException(
                status_code=500,
                detail="LangChain OpenAI provider is not installed. Run `pip install langchain-openai`.",
            ) from exc

    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain.prompts import ChatPromptTemplate
    from langchain_mcp import MCPToolkit
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    import httpx

    if not MCP_SSE_URL:
        raise HTTPException(
            status_code=503,
            detail="MCP_SSE_URL is not configured. Set it in your .env file to enable LangChain.",
        )

    try:
        logger.info("Connecting to MCP SSE endpoint at %s", MCP_SSE_URL)
        async with sse_client(MCP_SSE_URL) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                toolkit = MCPToolkit(session=session)
                await toolkit.initialize()
                langchain_tools = toolkit.get_tools()

                if not langchain_tools:
                    raise HTTPException(
                        status_code=503,
                        detail="No MCP tools are currently available from the SSE server.",
                    )
                logger.info(
                    "Initialized MCP toolkit with tools: %s",
                    [tool.name for tool in langchain_tools],
                )

                llm = ChatOpenAI(model="gpt-4o", temperature=0)
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            (
                                "You are a helpful assistant with calculator and web-fetching tools. "
                                "Use MCP tools whenever they can satisfy the request. "
                                "If the user asks for web content and provides an HTTP or HTTPS URL, call "
                                "`fetch_web_content` exactly once, then summarize the snippet that tool returns. "
                                "Include any notes from the tool response and avoid calling the same tool repeatedly "
                                "unless the user requests a different URL. Provide concise explanations after tool usage."
                            ),
                        ),
                        (
                            "human",
                            "Previous steps: {agent_scratchpad}\nUser request: {input}",
                        ),
                    ]
                )

                agent = create_tool_calling_agent(llm, langchain_tools, prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=langchain_tools,
                    verbose=False,
                    max_iterations=6,
                    return_intermediate_steps=True,
                    handle_parsing_errors=True,
                )

                logger.info("Invoking LangChain agent with MCP tools")
                agent_response = await agent_executor.ainvoke(
                    {"input": request.expression}
                )
                logger.info("LangChain agent response: %s", agent_response)
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Unable to connect to MCP SSE endpoint at {MCP_SSE_URL}. "
                "Ensure `python -m src.transports.sse` is running."
            ),
        ) from exc
    except ConnectionError as exc:  # pragma: no cover - connection guidance
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    output = agent_response.get("output")
    intermediate_steps = agent_response.get("intermediate_steps")
    serialized_steps = (
        [str(step) for step in intermediate_steps] if intermediate_steps else []
    )
    if serialized_steps:
        logger.info("LangChain intermediate steps: %s", serialized_steps)
    logger.info("LangChain final output: %s", output)

    return {
        "success": True,
        "expression": request.expression,
        "output": output,
        "intermediate_steps": serialized_steps,
    }


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Close the MCP client on shutdown."""
    await mcp_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
