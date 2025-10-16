# MCP Calculator Playground

Interactive UI for testing the MCP Calculator Server with optional LangChain integration.

## Setup

1. Ensure the MCP server is running (REST API transport on port 8002).
   - For LangChain features, also start the SSE transport on port 8000:
     ```bash
     python -m src.transports.sse
     ```
2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Start the backend:
   ```bash
   python -m main
   ```
4. Open `frontend/index.html` in your browser.

## Features

- View all available calculator tools
- Execute tools with custom parameters
- Natural-language calculations via LangChain (requires OpenAI API key)
- Fetch web content through the MCP server
- Run Serper-powered web searches (requires `SERPER_API_KEY`)
- Generate PDFs directly from tool responses
- Generate DOCX files without templates
- Real-time result display

## Configuration

The backend listens on port `8003` by default. To change the port:

- Update the port in `backend/main.py` (`uvicorn.run`)
- Update `API_URL` in `frontend/script.js`

LangChain uses the MCP SSE endpoint. Configure the URL via the
`MCP_SSE_URL` environment variable (defaults to `http://localhost:8000/sse`).
Set `SERPER_API_KEY` to enable the `web_search` tool on the MCP server.

## LangChain Integration

To enable full LangChain functionality:

1. Set the environment variable: `export OPENAI_API_KEY=your_key_here`
2. (Optional) Set a custom SSE endpoint: `export MCP_SSE_URL=http://host:port/sse`
2. Uncomment the LangChain integration code in `backend/main.py`
3. Restart the backend server
