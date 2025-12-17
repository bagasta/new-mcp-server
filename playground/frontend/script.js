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

    if (!tool || !tool.parameters) {
        return;
    }

    const parameters = tool.parameters.properties || {};
    Object.entries(parameters).forEach(([name, param]) => {
        const div = document.createElement('div');
        div.className = 'argument-input';
        const typeLabel = param.type || 'value';
        const description = param.description || '';
        let inputHtml = '';

        if (param.type === 'object') {
            inputHtml = `
                <textarea
                    id="arg-${name}"
                    placeholder='Enter JSON, e.g. {"to": "whatsapp:+62812XXXXXXX", "message": "text"}'
                    rows="4"
                    spellcheck="false"
                ></textarea>
            `;
        } else {
            const inputType =
                param.type === 'integer' || param.type === 'number'
                    ? 'number'
                    : 'text';
            const stepAttr = param.type === 'integer' ? ' step="1"' : '';
            inputHtml = `
                <input
                    type="${inputType}"
                    id="arg-${name}"
                    placeholder="${description}"
                    ${stepAttr}
                >
            `;
        }

        div.innerHTML = `
            <label for="arg-${name}">${name} (${typeLabel}):</label>
            ${inputHtml}
        `;
        container.appendChild(div);
    });
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

    let parseError = null;
    for (const [name, param] of Object.entries(params)) {
        const input = document.getElementById(`arg-${name}`);
        if (!input) {
            continue;
        }
        const rawValue = input.value ?? '';
        if (rawValue.trim() === '') {
            continue;
        }
        try {
            argumentsPayload[name] = transformArgumentValue(name, param, rawValue);
        } catch (error) {
            parseError = error instanceof Error ? error.message : String(error);
            break;
        }
    }

    if (parseError) {
        document.getElementById('result').textContent = `Error: ${parseError}`;
        return;
    }

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

function transformArgumentValue(name, param, rawValue) {
    if (param.type === 'integer') {
        const value = parseInt(rawValue, 10);
        if (Number.isNaN(value)) {
            throw new Error(`Invalid integer value for ${name}.`);
        }
        return value;
    }
    if (param.type === 'number') {
        const value = parseFloat(rawValue);
        if (Number.isNaN(value)) {
            throw new Error(`Invalid number value for ${name}.`);
        }
        return value;
    }
    if (param.type === 'object') {
        try {
            return JSON.parse(rawValue);
        } catch (error) {
            const details = error instanceof Error ? error.message : String(error);
            throw new Error(`Invalid JSON for ${name}: ${details}`);
        }
    }
    return rawValue;
}
