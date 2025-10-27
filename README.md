# MCP Calculator Server

Full-featured MCP (Model Context Protocol) server with calculator tools, supporting multiple transports.

## Features

- ✅ 17 tools (calculator operations, web utilities, reminders, messaging, documents, and deep research trigger)
- ✅ 4 transport options (STDIO, SSE, Streamable HTTP, REST API)
- ✅ Interactive playground with optional LangChain integration
- ✅ Built with FastMCP and Python

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
cd playground/backend && pip install -r requirements.txt
```

### 2. Run MCP Server (choose one transport)

```bash
# STDIO
python -m src.transports.stdio

# SSE (port 8000)
python -m src.transports.sse

# Streamable HTTP (port 8001)
python -m src.transports.streamable

# REST API (port 8002)
python -m src.transports.api
```

> **Note:** The playground backend requires the REST API transport. Start it with
> `python -m src.transports.api` before launching the playground services.
>
> For LangChain-powered `/calculate` requests, also start the SSE transport:
> `python -m src.transports.sse` (default URL `http://localhost:8000/sse`).

### 3. Run Playground

```bash
# Start backend
cd playground/backend
python -m main

# Open frontend (in browser)
open ../frontend/index.html  # macOS
# or use your preferred method to open the HTML file.
```

## Transport Details

| Transport        | Port | Use Case                    |
|------------------|------|-----------------------------|
| STDIO            | -    | CLI tools, direct integration |
| SSE              | 8000 | Real-time streaming         |
| Streamable HTTP  | 8001 | HTTP streaming clients      |
| REST API         | 8002 | Simple HTTP requests        |

## Available Tools

- `add(a, b)` - Add two numbers
- `subtract(a, b)` - Subtract b from a
- `multiply(a, b)` - Multiply two numbers
- `divide(a, b)` - Divide a by b
- `power(base, exponent)` - Raise `base` to `exponent`
- `sqrt(value)` - Square root
- `factorial(value)` - Factorial
- `percentage(value, percent)` - Calculate a percentage
- `fetch_web_content(url, timeout=10)` - Fetch web content over HTTP/HTTPS
- `web_search(query, country='us', language='en', num_results=5)` - Search the web via Serper
- `pdf_generate(title, content, filename=None, author=None)` - Generate a PDF document with supplied text
- `docx_generate(title, content, filename=None, author=None)` - Generate a DOCX document with supplied text
- `schedule_reminder(...)`, `list_reminders(limit=20)`, `cancel_reminder(reminder_id)` - Manage scheduled reminders via webhook
- `send_message(to, message)` - Dispatch an immediate notification to the webhook
- `deep_research(search_topic, email)` - Trigger the n8n deep research workflow with structured payload

### Configuration Notes

- Environment variables from a `.env` file in the project root are loaded automatically when the server starts.
- Set `SERPER_API_KEY` with your Serper API token to enable the `web_search` tool.
- Set `REMINDER_WEBHOOK_URL`, `MESSAGE_WEBHOOK_URL`, and `DEEP_RESEARCH_WEBHOOK_URL` to wire webhook-based tools.

## Playground Usage

1. Start REST API transport: `python -m src.transports.api`
2. Start playground backend: `cd playground/backend && python -m main`
3. Open `playground/frontend/index.html` in your browser
4. Select tools, provide arguments, and execute operations
5. Optionally enter natural-language instructions (enable LangChain to process fully)

## Integration Tests

- Run `python3 scripts/run_full_test.py` from the project root to exercise calculator tools, document generators, web utilities, reminder workflows, and REST/SSE/streamable transports.
- The harness spins up a local webhook recorder and skips the Serper search test unless `SERPER_API_KEY` is configured.

## License

MIT
