const API_URL = 'http://localhost:8003';

let availableTools = [];

document.addEventListener('DOMContentLoaded', () => {
    loadTools();
    setupEventListeners();
});

async function loadTools() {
    try {
        const response = await fetch(`${API_URL}/tools`);
        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }
        const data = await response.json();
        availableTools = data.tools || [];
        displayTools(availableTools);
        populateToolSelect(availableTools);
    } catch (error) {
        document.getElementById('tools-list').innerHTML =
            `<p class="error">Error loading tools: ${error.message}</p>`;
    }
}

function displayTools(tools) {
    const toolsList = document.getElementById('tools-list');
    if (!tools.length) {
        toolsList.innerHTML = '<p class="error">No tools available.</p>';
        return;
    }

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

function handleToolSelect(event) {
    const toolName = event.target.value;
    const tool = availableTools.find(t => t.name === toolName);
    const container = document.getElementById('arguments-container');
    container.innerHTML = '';

    if (tool && tool.parameters) {
        const parameters = tool.parameters.properties || {};
        Object.entries(parameters).forEach(([name, param]) => {
            const div = document.createElement('div');
            div.className = 'argument-input';
            const inputType = param.type === 'integer' ? 'number' : 'text';
            const stepAttr = param.type === 'integer' ? ' step="1"' : '';

            div.innerHTML = `
                <label for="arg-${name}">${name} (${param.type || 'value'}):</label>
                <input
                    type="${inputType}"
                    id="arg-${name}"
                    placeholder="${param.description || ''}"
                    ${stepAttr}
                >
            `;
            container.appendChild(div);
        });
    }
}

async function executeTool() {
    const toolName = document.getElementById('tool-select').value;
    if (!toolName) {
        document.getElementById('result').textContent = 'Please select a tool.';
        return;
    }

    const tool = availableTools.find(t => t.name === toolName);
    const params = tool?.parameters?.properties || {};
    const argumentsPayload = {};

    Object.entries(params).forEach(([name, param]) => {
        const input = document.getElementById(`arg-${name}`);
        const rawValue = input?.value ?? '';
        if (rawValue === '') {
            return;
        }
        if (param.type === 'integer') {
            argumentsPayload[name] = parseInt(rawValue, 10);
        } else if (param.type === 'number') {
            argumentsPayload[name] = parseFloat(rawValue);
        } else {
            argumentsPayload[name] = rawValue;
        }
    });

    try {
        const response = await fetch(`${API_URL}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tool_name: toolName, arguments: argumentsPayload })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Execution failed');
        }

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
            'Please enter an expression.';
        return;
    }

    try {
        const response = await fetch(`${API_URL}/calculate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ expression })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Calculation failed');
        }

        document.getElementById('langchain-result').textContent =
            JSON.stringify(data, null, 2);
    } catch (error) {
        document.getElementById('langchain-result').textContent =
            `Error: ${error.message}`;
    }
}
