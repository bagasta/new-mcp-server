# MCP Calculator Server with FastMCP

Buatkan MCP (Model Context Protocol) server dengan calculator tools menggunakan Python FastMCP, lengkap dengan 4 transport options dan playground untuk testing.

## Project Structure

```
mcp-calculator/
├── src/
│   ├── __init__.py
│   ├── server.py          # Main MCP server dengan FastMCP
│   ├── tools.py           # Calculator tools
│   └── transports/
│       ├── __init__.py
│       ├── sse.py         # SSE transport
│       ├── stdio.py       # STDIO transport
│       ├── streamable.py  # Streamable HTTP transport
│       └── api.py         # REST API transport
├── playground/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py        # FastAPI backend dengan LangChain
│   │   ├── mcp_client.py  # Client untuk connect ke MCP server
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── index.html
│   │   ├── script.js
│   │   └── style.css
│   └── README.md
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Step 1: Setup Project Dependencies

Buatkan `requirements.txt` dengan dependencies:
```
fastmcp>=0.2.0
pydantic>=2.0.0
uvicorn>=0.27.0
fastapi>=0.109.0
sse-starlette>=1.8.0
httpx>=0.26.0
langchain>=0.1.0
langchain-community>=0.0.20
python-multipart>=0.0.6
```

Buatkan `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mcp-calculator"
version = "0.1.0"
description = "MCP Calculator Server with multiple transports"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=0.2.0",
    "pydantic>=2.0.0",
    "uvicorn>=0.27.0",
    "fastapi>=0.109.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "black>=23.0.0", "ruff>=0.1.0"]
```

## Step 2: Implement Calculator Tools

Buatkan `src/tools.py`:
```python
"""Calculator tools for MCP server"""
from typing import Union
import operator
import math

class Calculator:
    """Calculator with basic and advanced operations"""
    
    @staticmethod
    def add(a: float, b: float) -> float:
        """Add two numbers"""
        return a + b
    
    @staticmethod
    def subtract(a: float, b: float) -> float:
        """Subtract b from a"""
        return a - b
    
    @staticmethod
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers"""
        return a * b
    
    @staticmethod
    def divide(a: float, b: float) -> float:
        """Divide a by b"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    
    @staticmethod
    def power(base: float, exponent: float) -> float:
        """Raise base to the power of exponent"""
        return base ** exponent
    
    @staticmethod
    def sqrt(n: float) -> float:
        """Calculate square root"""
        if n < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return math.sqrt(n)
    
    @staticmethod
    def factorial(n: int) -> int:
        """Calculate factorial"""
        if n < 0:
            raise ValueError("Factorial not defined for negative numbers")
        return math.factorial(n)
    
    @staticmethod
    def percentage(value: float, percent: float) -> float:
        """Calculate percentage of a value"""
        return (value * percent) / 100
```

## Step 3: Create Main MCP Server

Buatkan `src/server.py`:
```python
"""Main MCP Server using FastMCP"""
from fastmcp import FastMCP
from .tools import Calculator

# Initialize FastMCP server
mcp = FastMCP("Calculator Server")

calc = Calculator()

# Register tools
@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        Sum of a and b
    """
    return calc.add(a, b)

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a
    
    Args:
        a: Number to subtract from
        b: Number to subtract
    
    Returns:
        Difference of a and b
    """
    return calc.subtract(a, b)

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        Product of a and b
    """
    return calc.multiply(a, b)

@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b
    
    Args:
        a: Dividend
        b: Divisor
    
    Returns:
        Quotient of a divided by b
    
    Raises:
        ValueError: If b is zero
    """
    return calc.divide(a, b)

@mcp.tool()
def power(base: float, exponent: float) -> float:
    """Calculate base raised to exponent
    
    Args:
        base: Base number
        exponent: Exponent
    
    Returns:
        base^exponent
    """
    return calc.power(base, exponent)

@mcp.tool()
def sqrt(n: float) -> float:
    """Calculate square root
    
    Args:
        n: Number to calculate square root of
    
    Returns:
        Square root of n
    
    Raises:
        ValueError: If n is negative
    """
    return calc.sqrt(n)

@mcp.tool()
def factorial(n: int) -> int:
    """Calculate factorial of n
    
    Args:
        n: Non-negative integer
    
    Returns:
        n! (factorial of n)
    
    Raises:
        ValueError: If n is negative
    """
    return calc.factorial(n)

@mcp.tool()
def percentage(value: float, percent: float) -> float:
    """Calculate percentage of a value
    
    Args:
        value: Base value
        percent: Percentage to calculate
    
    Returns:
        percent% of value
    """
    return calc.percentage(value, percent)
```

## Step 4: Implement Transports

### STDIO Transport
Buatkan `src/transports/stdio.py`:
```python
"""STDIO transport for MCP server"""
import sys
from ..server import mcp

def run_stdio():
    """Run MCP server with STDIO transport"""
    print("Starting MCP Calculator Server with STDIO transport...", file=sys.stderr)
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_stdio()
```

### SSE Transport
Buatkan `src/transports/sse.py`:
```python
"""SSE transport for MCP server"""
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse
from ..server import mcp
import uvicorn

app = FastAPI(title="MCP Calculator - SSE Transport")

@app.get("/sse")
async def sse_endpoint():
    """SSE endpoint for MCP"""
    return EventSourceResponse(mcp.sse_handler())

def run_sse(host: str = "0.0.0.0", port: int = 8000):
    """Run MCP server with SSE transport"""
    print(f"Starting MCP Calculator Server with SSE transport on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_sse()
```

### Streamable HTTP Transport
Buatkan `src/transports/streamable.py`:
```python
"""Streamable HTTP transport for MCP server"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from ..server import mcp
import uvicorn

app = FastAPI(title="MCP Calculator - Streamable HTTP")

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Streamable HTTP endpoint for MCP"""
    body = await request.json()
    return StreamingResponse(
        mcp.handle_request(body),
        media_type="application/json"
    )

def run_streamable(host: str = "0.0.0.0", port: int = 8001):
    """Run MCP server with Streamable HTTP transport"""
    print(f"Starting MCP Calculator Server with Streamable HTTP on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_streamable()
```

### REST API Transport
Buatkan `src/transports/api.py`:
```python
"""REST API transport for MCP server"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
from ..server import mcp
import uvicorn

app = FastAPI(title="MCP Calculator - REST API")

class ToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "MCP Calculator REST API", "version": "0.1.0"}

@app.get("/tools")
async def list_tools():
    """List available tools"""
    tools = mcp.list_tools()
    return {"tools": tools}

@app.post("/execute")
async def execute_tool(request: ToolRequest):
    """Execute a calculator tool"""
    try:
        result = mcp.call_tool(request.tool_name, request.arguments)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def run_api(host: str = "0.0.0.0", port: int = 8002):
    """Run MCP server with REST API transport"""
    print(f"Starting MCP Calculator Server with REST API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_api()
```

## Step 5: Create Playground Backend

Buatkan `playground/backend/requirements.txt`:
```
fastapi>=0.109.0
uvicorn>=0.27.0
langchain>=0.1.0
langchain-community>=0.0.20
httpx>=0.26.0
pydantic>=2.0.0
python-multipart>=0.0.6
```

Buatkan `playground/backend/mcp_client.py`:
```python
"""MCP Client for connecting to calculator server"""
import httpx
from typing import Any, Dict, List
from pydantic import BaseModel

class MCPClient:
    """Client for MCP Calculator Server"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        response = await self.client.get(f"{self.base_url}/tools")
        return response.json()["tools"]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool"""
        response = await self.client.post(
            f"{self.base_url}/execute",
            json={"tool_name": tool_name, "arguments": arguments}
        )
        result = response.json()
        if result["success"]:
            return result["result"]
        raise Exception(f"Tool execution failed: {result}")
    
    async def close(self):
        """Close client connection"""
        await self.client.aclose()
```

Buatkan `playground/backend/main.py`:
```python
"""FastAPI backend with LangChain for MCP testing"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List
from .mcp_client import MCPClient
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

app = FastAPI(title="MCP Calculator Playground")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp_client = MCPClient()

class CalculationRequest(BaseModel):
    expression: str

class ToolExecutionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "MCP Calculator Playground API"}

@app.get("/tools")
async def get_tools():
    """Get available calculator tools"""
    try:
        tools = await mcp_client.list_tools()
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute")
async def execute_tool(request: ToolExecutionRequest):
    """Execute a specific tool"""
    try:
        result = await mcp_client.execute_tool(
            request.tool_name,
            request.arguments
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/calculate")
async def calculate(request: CalculationRequest):
    """
    Use LangChain agent to process natural language calculation
    Note: Requires OpenAI API key in environment
    """
    try:
        # Get available tools from MCP
        mcp_tools = await mcp_client.list_tools()
        
        # Create LangChain tools from MCP tools
        langchain_tools = []
        for tool in mcp_tools:
            async def tool_func(tool_name=tool["name"], **kwargs):
                return await mcp_client.execute_tool(tool_name, kwargs)
            
            langchain_tools.append(
                Tool(
                    name=tool["name"],
                    func=tool_func,
                    description=tool.get("description", "")
                )
            )
        
        # Create agent (requires OpenAI API key)
        # llm = ChatOpenAI(model="gpt-4")
        # agent = create_tool_calling_agent(llm, langchain_tools, prompt)
        # agent_executor = AgentExecutor(agent=agent, tools=langchain_tools)
        
        # For now, return simple response
        return {
            "success": True,
            "message": "LangChain integration ready",
            "expression": request.expression,
            "note": "Set OPENAI_API_KEY to enable full agent functionality"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown():
    await mcp_client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
```

## Step 6: Create Playground Frontend

Buatkan `playground/frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Calculator Playground</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>🧮 MCP Calculator Playground</h1>
            <p>Test your MCP Calculator Server with multiple transports</p>
        </header>

        <div class="main-content">
            <section class="tools-section">
                <h2>Available Tools</h2>
                <div id="tools-list" class="tools-list">
                    <p class="loading">Loading tools...</p>
                </div>
            </section>

            <section class="test-section">
                <h2>Test Calculator</h2>
                
                <div class="test-form">
                    <label for="tool-select">Select Tool:</label>
                    <select id="tool-select">
                        <option value="">-- Select a tool --</option>
                    </select>

                    <div id="arguments-container"></div>

                    <button id="execute-btn" class="btn btn-primary">Execute</button>
                </div>

                <div class="result-container">
                    <h3>Result:</h3>
                    <pre id="result"></pre>
                </div>
            </section>

            <section class="langchain-section">
                <h2>LangChain Natural Language</h2>
                <div class="langchain-form">
                    <label for="expression">Enter calculation in natural language:</label>
                    <input 
                        type="text" 
                        id="expression" 
                        placeholder="e.g., What is 25 plus 75?"
                    >
                    <button id="langchain-btn" class="btn btn-secondary">Calculate</button>
                </div>
                <div class="result-container">
                    <h3>LangChain Result:</h3>
                    <pre id="langchain-result"></pre>
                </div>
            </section>
        </div>
    </div>

    <script src="script.js"></script>
</body>
</html>
```

Buatkan `playground/frontend/style.css`:
```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    overflow: hidden;
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 40px;
    text-align: center;
}

header h1 {
    font-size: 2.5rem;
    margin-bottom: 10px;
}

header p {
    font-size: 1.1rem;
    opacity: 0.9;
}

.main-content {
    padding: 40px;
}

section {
    margin-bottom: 40px;
}

h2 {
    color: #333;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 2px solid #667eea;
}

.tools-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 15px;
}

.tool-card {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 10px;
    border-left: 4px solid #667eea;
}

.tool-card h3 {
    color: #667eea;
    font-size: 1.1rem;
    margin-bottom: 8px;
}

.tool-card p {
    color: #666;
    font-size: 0.9rem;
}

.test-form, .langchain-form {
    background: #f8f9fa;
    padding: 25px;
    border-radius: 10px;
    margin-bottom: 20px;
}

label {
    display: block;
    margin-bottom: 8px;
    color: #333;
    font-weight: 600;
}

select, input[type="text"], input[type="number"] {
    width: 100%;
    padding: 12px;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-size: 1rem;
    margin-bottom: 15px;
    transition: border-color 0.3s;
}

select:focus, input:focus {
    outline: none;
    border-color: #667eea;
}

.argument-input {
    margin-bottom: 15px;
}

.btn {
    padding: 12px 30px;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}

.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.btn-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.btn-secondary {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
}

.result-container {
    margin-top: 20px;
}

.result-container h3 {
    color: #333;
    margin-bottom: 10px;
}

pre {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 8px;
    border-left: 4px solid #667eea;
    overflow-x: auto;
    color: #333;
    font-family: 'Courier New', monospace;
}

.loading {
    color: #666;
    font-style: italic;
}

.error {
    color: #f5576c;
    font-weight: 600;
}
```

Buatkan `playground/frontend/script.js`:
```javascript
const API_URL = 'http://localhost:8003';

let availableTools = [];

// Load tools on page load
document.addEventListener('DOMContentLoaded', () => {
    loadTools();
    setupEventListeners();
});

async function loadTools() {
    try {
        const response = await fetch(`${API_URL}/tools`);
        const data = await response.json();
        availableTools = data.tools;
        displayTools(availableTools);
        populateToolSelect(availableTools);
    } catch (error) {
        document.getElementById('tools-list').innerHTML = 
            `<p class="error">Error loading tools: ${error.message}</p>`;
    }
}

function displayTools(tools) {
    const toolsList = document.getElementById('tools-list');
    toolsList.innerHTML = tools.map(tool => `
        <div class="tool-card">
            <h3>${tool.name}</h3>
            <p>${tool.description || 'No description available'}</p>
        </div>
    `).join('');
}

function populateToolSelect(tools) {
    const select = document.getElementById('tool-select');
    tools.forEach(tool => {
        const option = document.createElement('option');
        option.value = tool.name;
        option.textContent = tool.name;
        select.appendChild(option);
    });
}

function setupEventListeners() {
    document.getElementById('tool-select').addEventListener('change', handleToolSelect);
    document.getElementById('execute-btn').addEventListener('click', executeTool);
    document.getElementById('langchain-btn').addEventListener('click', calculateWithLangChain);
}

function handleToolSelect(e) {
    const toolName = e.target.value;
    const tool = availableTools.find(t => t.name === toolName);
    
    const container = document.getElementById('arguments-container');
    container.innerHTML = '';
    
    if (tool && tool.parameters) {
        Object.entries(tool.parameters).forEach(([name, param]) => {
            const div = document.createElement('div');
            div.className = 'argument-input';
            div.innerHTML = `
                <label for="arg-${name}">${name} (${param.type}):</label>
                <input 
                    type="${param.type === 'integer' ? 'number' : 'text'}" 
                    id="arg-${name}" 
                    placeholder="${param.description || ''}"
                    ${param.type === 'integer' ? 'step="1"' : ''}
                >
            `;
            container.appendChild(div);
        });
    }
}

async function executeTool() {
    const toolName = document.getElementById('tool-select').value;
    if (!toolName) {
        document.getElementById('result').textContent = 'Please select a tool';
        return;
    }
    
    const tool = availableTools.find(t => t.name === toolName);
    const arguments = {};
    
    if (tool && tool.parameters) {
        Object.keys(tool.parameters).forEach(name => {
            const input = document.getElementById(`arg-${name}`);
            if (input) {
                const value = input.value;
                arguments[name] = tool.parameters[name].type === 'integer' 
                    ? parseInt(value) 
                    : parseFloat(value);
            }
        });
    }
    
    try {
        const response = await fetch(`${API_URL}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tool_name: toolName, arguments })
        });
        
        const data = await response.json();
        document.getElementById('result').textContent = 
            JSON.stringify(data, null, 2);
    } catch (error) {
        document.getElementById('result').textContent = 
            `Error: ${error.message}`;
    }
}

async function calculateWithLangChain() {
    const expression = document.getElementById('expression').value;
    if (!expression) {
        document.getElementById('langchain-result').textContent = 
            'Please enter an expression';
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/calculate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ expression })
        });
        
        const data = await response.json();
        document.getElementById('langchain-result').textContent = 
            JSON.stringify(data, null, 2);
    } catch (error) {
        document.getElementById('langchain-result').textContent = 
            `Error: ${error.message}`;
    }
}
```

## Step 7: Create Documentation

Buatkan `README.md`:
```markdown
# MCP Calculator Server

Full-featured MCP (Model Context Protocol) server with calculator tools, supporting multiple transports.

## Features

- ✅ 8 Calculator tools (add, subtract, multiply, divide, power, sqrt, factorial, percentage)
- ✅ 4 Transport options (STDIO, SSE, Streamable HTTP, REST API)
- ✅ Interactive playground with LangChain integration
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

### 3. Run Playground

```bash
# Start backend
cd playground/backend
python -m main

# Open frontend (in browser)
open playground/frontend/index.html
```

## Transport Details

| Transport | Port | Use Case |
|-----------|------|----------|
| STDIO | - | CLI tools, direct integration |
| SSE | 8000 | Real-time streaming |
| Streamable HTTP | 8001 | HTTP streaming |
| REST API | 8002 | Simple HTTP requests |

## Available Tools

- `add(a, b)` - Add two numbers
- `subtract(a, b)` - Subtract b from a
- `multiply(a, b)` - Multiply two numbers
- `divide(a, b)` - Divide a by b
- `power(base, exponent)` - Calculate power
- `sqrt(n)` - Square root
- `factorial(n)` - Factorial
- `percentage(value, percent)` - Calculate percentage

## Playground Usage

1. Start REST API transport: `python -m src.transports.api`
2. Start playground backend: `cd playground/backend && python -m main`
3. Open `playground/frontend/index.html` in browser
4. Select tools and test calculations
5. Try natural language queries (requires OpenAI API key)

## License

MIT
```

Buatkan `playground/README.md`:
```markdown
# MCP Calculator Playground

Interactive UI for testing MCP Calculator Server with LangChain integration.

## Setup

1. Make sure MCP server is running (REST API transport on port 8002)
2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Start backend:
   ```bash
   python -m main
   ```
4. Open `frontend/index.html` in your browser

## Features

- View all available calculator tools
- Execute tools with custom parameters
- Natural language processing with LangChain (requires OpenAI API key)
- Real-time results display

## Configuration

Backend runs on port 8003 by default. To change:
- Edit `backend/main.py` and update port in `uvicorn.run()`
- Update `API_URL` in `frontend/script.js`

## LangChain Integration

To enable full LangChain functionality:
1. Set environment variable: `export OPENAI_API_KEY=your_key_here`
2. Uncomment LangChain agent code in `backend/main.py`
3. Restart backend server
```

## Usage Instructions

1. **Initialize project**: Run Claude Code in project directory
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Choose and start a transport**:
   - For STDIO: `python -m src.transports.stdio`
   - For SSE: `python -m src.transports.sse`
   - For Streamable HTTP: `python -m src.transports.streamable`
   - For REST API: `python -m src.transports.api`
4. **Test with playground**:
   - Start REST API transport (port 8002)
   - Start playground backend: `cd playground/backend && python -m main`
   - Open `playground/frontend/index.html` in browser
5. **Verify everything works** by executing calculator operations

## Testing Examples

### Using REST API (curl)

```bash
# List tools
curl http://localhost:8002/tools

# Execute addition
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "add", "arguments": {"a": 10, "b": 20}}'

# Execute power
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "power", "arguments": {"base": 2, "exponent": 8}}'
```

### Using Playground

1. Select "add" from dropdown
2. Enter a=15, b=25
3. Click "Execute"
4. See result: 40

### Using LangChain (with OpenAI API key)

1. Set `OPENAI_API_KEY` environment variable
2. Enter natural language: "What is 25 percent of 200?"
3. Click "Calculate"
4. Agent will choose correct tool and execute

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Calculator Server                    │
│                      (FastMCP Core)                          │
└───────────────┬─────────────────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    │   Calculator Tools     │
    │  (8 operations)        │
    └───────────┬───────────┘
                │
    ┌───────────┴───────────────────────────────────┐
    │              Transports                        │
    ├──────────┬──────────┬──────────┬──────────────┤
    │  STDIO   │   SSE    │ Stream   │  REST API    │
    │          │  :8000   │  :8001   │   :8002      │
    └──────────┴──────────┴──────────┴──────────────┘
                                          │
                                          │
                            ┌─────────────┴──────────────┐
                            │    Playground Backend      │
                            │  (FastAPI + LangChain)     │
                            │        :8003               │
                            └─────────────┬──────────────┘
                                          │
                            ┌─────────────┴──────────────┐
                            │    Frontend UI             │
                            │  (HTML/CSS/JS)             │
                            └────────────────────────────┘
```

## File Checklist

Pastikan semua file berikut dibuat:

### Core MCP Server
- [ ] `src/__init__.py`
- [ ] `src/tools.py` - Calculator implementation
- [ ] `src/server.py` - FastMCP server with registered tools
- [ ] `src/transports/__init__.py`
- [ ] `src/transports/stdio.py` - STDIO transport
- [ ] `src/transports/sse.py` - SSE transport
- [ ] `src/transports/streamable.py` - Streamable HTTP
- [ ] `src/transports/api.py` - REST API transport

### Playground
- [ ] `playground/backend/__init__.py`
- [ ] `playground/backend/main.py` - FastAPI app
- [ ] `playground/backend/mcp_client.py` - MCP client
- [ ] `playground/backend/requirements.txt`
- [ ] `playground/frontend/index.html` - UI
- [ ] `playground/frontend/style.css` - Styling
- [ ] `playground/frontend/script.js` - Frontend logic
- [ ] `playground/README.md`

### Configuration
- [ ] `requirements.txt` - Main dependencies
- [ ] `pyproject.toml` - Project config
- [ ] `README.md` - Documentation

## Development Tips

1. **Start with STDIO** for basic testing
2. **Use REST API** for playground development
3. **Test each tool** individually before integration
4. **Check logs** in terminal for debugging
5. **Use browser DevTools** for frontend debugging

## Troubleshooting

### Port Already in Use
```bash
# Find process using port
lsof -i :8002
# Kill process
kill -9 <PID>
```

### CORS Issues
Backend already configured with CORS middleware. If issues persist:
- Check browser console
- Verify backend is running
- Ensure correct API_URL in `script.js`

### Module Import Errors
```bash
# Run from project root
python -m src.transports.api

# Not from src/ directory
cd src && python transports/api.py  # ❌ Wrong
```

### FastMCP Not Found
```bash
pip install --upgrade fastmcp
```

## Extending the Server

### Add New Tool

1. Add method to `Calculator` class in `src/tools.py`
2. Register tool in `src/server.py`:
   ```python
   @mcp.tool()
   def my_new_tool(param1: float) -> float:
       """Description"""
       return calc.my_new_method(param1)
   ```
3. Restart server
4. Tool appears automatically in playground

### Add New Transport

1. Create `src/transports/my_transport.py`
2. Implement transport logic using FastMCP
3. Add run function
4. Update README

## Performance

- **STDIO**: Lowest latency, best for CLI
- **SSE**: Good for streaming, persistent connection
- **Streamable HTTP**: Balanced, HTTP/2 friendly
- **REST API**: Simplest, best for testing

## Security Notes

- Playground has CORS enabled for all origins (development only)
- No authentication implemented (add for production)
- Input validation done by Pydantic models
- Division by zero handled gracefully

## Next Steps

1. ✅ Create all files as specified
2. ✅ Install dependencies
3. ✅ Run tests on each transport
4. ✅ Test playground end-to-end
5. 🚀 Extend with your own tools!

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [LangChain Docs](https://python.langchain.com)
- [FastAPI Docs](https://fastapi.tiangolo.com)

## Support

For issues or questions:
1. Check logs in terminal
2. Verify all dependencies installed
3. Ensure correct Python version (>=3.10)
4. Review error messages carefully

---

**Happy Coding! 🎉**

This MCP server is production-ready and can be extended with:
- Authentication & authorization
- Rate limiting
- Caching layer
- Database integration
- More calculator operations
- Custom tools for your domain