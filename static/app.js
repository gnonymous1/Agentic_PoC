// AgentOS Dashboard Logic
const API_BASE = "http://localhost:8000";

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    // Update Icon
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.innerText = theme === 'dark' ? '🌙' : '☀️';
    }
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = current === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    await fetchConfig(); // Load config before other inits if needed, though mostly for WS
    // ... existing init code ...
});
let isThinking = false;
let socket = null;
let inputTimeoutId = null; // Track timeout for auto-re-enabling input
let webChannelPort = 8766; // Default fallback

// Configuration Loading
async function fetchConfig() {
    try {
        const res = await fetch(`${API_BASE}/config/client`);
        if (res.ok) {
            const config = await res.json();
            if (config.web_channel_port) {
                webChannelPort = config.web_channel_port;
                console.log(`[Config] Loaded Web Channel Port: ${webChannelPort}`);
            }
        }
    } catch (e) {
        console.warn("[Config] Failed to fetch client config, using defaults", e);
    }
}

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = webChannelPort; // Use configured port

    try {
        socket = new WebSocket(`${protocol}//${host}:${port}`);

        socket.onopen = () => {
            console.log("WebSocket connected");
            document.querySelector('.status-indicator').innerText = "ONLINE (LIVE)";
            socket.send(JSON.stringify({ user_id: "dashboard_viewer" }));
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error("WS Parse Error", e);
            }
        };

        socket.onerror = (error) => {
            console.warn(`WebSocket error (port ${port} may not be running):`, error);
            document.querySelector('.status-indicator').innerText = "ONLINE";
        };

        socket.onclose = () => {
            console.log("WebSocket disconnected.");
            document.querySelector('.status-indicator').innerText = "ONLINE";
            // Don't auto-reconnect if WebSocket server isn't running
        };
    } catch (e) {
        console.warn("WebSocket not available:", e);
        document.querySelector('.status-indicator').innerText = "ONLINE";
    }
}

function handleWebSocketMessage(data) {
    if (data.type === "system_event") {
        if (data.event_type === "system_event" && data.data.action === "metric_recorded") {
            // Update Charts (TODO)
        } else if (data.event_type === "agent_message" || data.event_type === "system_event") {
            // Log to console
            const msg = `[${data.source}] ${JSON.stringify(data.data)}`;
            updateMonitor([msg]);
        }
    } else if (data.type === "message") {
        // Chat message
        const sender = data.from === "dashboard_viewer" ? "user" : "ai";
        addMessage(data.content, sender);
    }
}

// View Navigation
function switchView(viewId) {
    // Navigation active state
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.getAttribute('onclick').includes(`'${viewId}'`)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Content Switching
    document.querySelectorAll('.view').forEach(view => {
        view.style.display = 'none';
    });

    // Legacy mapping or direct ID
    const targetId = viewId.endsWith('-view') ? viewId : `${viewId}-view`;
    const targetElement = document.getElementById(targetId);

    if (targetElement) {
        targetElement.style.display = 'block';
    }

    // View-specific logic
    if (viewId === 'memory') {
        fetchMemory();
        checkHealth();
    } else if (viewId === 'workflows') {
        // Phase 18: Workflow Studio
        renderWorkflowSteps();
    } else if (viewId === 'skills') {
        fetchSkills();
    } else if (viewId === 'agents') {
        fetchAgents();
        if (!window.agentPollInterval) {
            window.agentPollInterval = setInterval(fetchAgents, 2000);
        }
    } else {
        if (window.agentPollInterval) {
            clearInterval(window.agentPollInterval);
            window.agentPollInterval = null;
        }
    }
}

async function toggleStepMode(enabled) {
    console.log(`Step Mode toggled: ${enabled}`);
    try {
        await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_mode: enabled })
        });
        addMessage(`System: Step Mode ${enabled ? 'ENABLED' : 'DISABLED'}.`, 'system');
    } catch (e) {
        console.error("Failed to toggle Step Mode:", e);
    }
}

function newChat(autoConfirm = false) {
    if (autoConfirm || confirm("Reset current session and start a new chat?")) {
        console.log("Resetting chat session...");
        const history = document.getElementById('chat-history');
        const monitor = document.getElementById('real-time-log');
        if (history) history.innerHTML = '<div class="message system"><div class="content">New session started. Waiting for input...</div></div>';
        if (monitor) monitor.innerHTML = '<div class="log-entry system">> Ready for deployment.</div>';
        addMessage("Session reset. Assistant is ready.", 'system');
    }
}

// Core Execution
async function sendMessage() {
    if (isThinking) return;

    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;

    setUIState(true);
    addMessage(text, 'user');
    input.value = '';

    const loadingId = addMessage('Thinking...', 'ai', true);

    // Safety timeout: auto-re-enable input after 30 seconds
    inputTimeoutId = setTimeout(() => {
        console.warn("Response timeout - re-enabling input");
        removeMessage(loadingId);
        addMessage("Response timeout. Please try again.", 'system');
        setUIState(false);
    }, 30000);

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();
        clearTimeout(inputTimeoutId); // Clear timeout on successful response
        removeMessage(loadingId);

        if (data.status === "AWAITING_APPROVAL") {
            addMessage(data.response, 'system');
            showHITLControls(true);
        } else {
            addMessage(data.response, 'ai');
            setUIState(false);
        }

        if (data.logs) updateMonitor(data.logs);
        fetchMemory();
    } catch (error) {
        clearTimeout(inputTimeoutId); // Clear timeout on error
        removeMessage(loadingId);
        addMessage(`Error: ${error.message}`, 'system');
        setUIState(false);
    }
}

async function stopExecution() {
    try {
        await fetch(`${API_BASE}/interrupt`, { method: 'POST' });
        updateMonitor(["!! Execution interrupted by user !!"]);
        addMessage("Execution stopped.", 'system');
        setUIState(false);
        showHITLControls(false);
    } catch (error) {
        console.error("Failed to stop", error);
    }
}

async function continueExecution() {
    showHITLControls(false);
    const loadingId = addMessage('Continuing...', 'ai', true);

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: "CONTINUE" })
        });

        const data = await response.json();
        removeMessage(loadingId);

        if (data.status === "AWAITING_APPROVAL") {
            addMessage(data.response, 'system');
            showHITLControls(true);
        } else {
            addMessage(data.response, 'ai');
            setUIState(false);
        }

        if (data.logs) updateMonitor(data.logs);
        fetchMemory();
    } catch (error) {
        removeMessage(loadingId);
        addMessage(`Error: ${error.message}`, 'system');
        setUIState(false);
    }
}

// UI State Management
function setUIState(thinking) {
    isThinking = thinking;
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    loadingStatus(thinking);

    if (thinking) {
        input.disabled = true;
        input.placeholder = "Agent is thinking...";
        sendBtn.disabled = true;
    } else {
        // Clear any pending timeout when re-enabling
        if (inputTimeoutId) {
            clearTimeout(inputTimeoutId);
            inputTimeoutId = null;
        }
        input.disabled = false;
        input.placeholder = "Enter command...";
        sendBtn.disabled = false;
        input.focus();
    }
}

function showHITLControls(show) {
    const hitlPanel = document.getElementById('hitl-controls');
    if (show) {
        hitlPanel.style.display = 'flex';
        isThinking = true;
    } else {
        hitlPanel.style.display = 'none';
    }
}

// --- Phase 17: Task Assignment & Profile Modals ---

// Task Modal
function openTaskModal() {
    const modal = document.getElementById('task-modal');
    modal.style.display = 'block';
    populateAgentSelector();
}

function closeTaskModal() {
    document.getElementById('task-modal').style.display = 'none';
}

async function populateAgentSelector() {
    const container = document.getElementById('agent-selector');
    container.innerHTML = '<div class="loader">Loading agents...</div>';

    try {
        const res = await fetch(`${API_BASE}/agents`);
        const data = await res.json();

        container.innerHTML = data.agents.map(agent => `
            <div class="agent-option" onclick="toggleAgentSelection(this, '${agent.name}')">
                ${agent.name}
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<div class="error">Failed to load agents</div>';
    }
}

function toggleAgentSelection(element, agentName) {
    element.classList.toggle('selected');
}

async function submitTask() {
    const objective = document.getElementById('task-objective').value;
    const priority = document.getElementById('task-priority').value;

    // Get selected agents
    const selectedAgents = Array.from(document.querySelectorAll('.agent-option.selected'))
        .map(el => el.innerText.trim());

    if (!objective) {
        alert("Please enter an objective.");
        return;
    }

    // Construct prompt
    let prompt = objective;
    if (selectedAgents.length > 0) {
        prompt += `\n\n[System Info: User explicitly requested these agents: ${selectedAgents.join(', ')}]`;
    }

    // Send to chat
    closeTaskModal();
    switchView('dashboard');

    const input = document.getElementById('user-input');
    input.value = prompt;
    sendMessage(); // Reuse existing chat logic
}

// Profile Modal
function openProfileModal(agentName) {
    // In a real app, fetch detailed profile. For PoC, use existing data/mock.
    const modal = document.getElementById('profile-modal');

    // Find agent data from the grid (shortcut) or fetch
    // For now, let's fetch list again or use a cache
    // Simplified: Just use what we have or generic

    document.getElementById('profile-name').innerText = agentName;
    document.getElementById('profile-status').innerText = "Fetching...";

    // Fetch details
    fetch(`${API_BASE}/agents`).then(res => res.json()).then(data => {
        const agent = data.agents.find(a => a.name === agentName);
        if (agent) {
            document.getElementById('profile-status').innerText = agent.status;
            document.getElementById('profile-role').innerText = agent.type;
            document.getElementById('profile-description').innerText = agent.description;

            // Mock capabilities based on type
            const caps = agent.type === 'worker' ? ['Execute Tasks', 'Report Status'] : ['Routing', 'Management'];
            document.getElementById('profile-capabilities').innerHTML = caps.map(c => `<li>${c}</li>`).join('');

            // Mock Activity
            document.getElementById('profile-logs').innerHTML = `
                <div class="log-entry">> Initialized at ${new Date().toLocaleTimeString()}</div>
                <div class="log-entry">> Status check: ${agent.status}</div>
            `;
        }
    });

    modal.style.display = 'block';
}

function closeProfileModal() {
    document.getElementById('profile-modal').style.display = 'none';
}

// Update renderAgents to make cards clickable
const originalRenderAgents = renderAgents;
renderAgents = function (agents) {
    const grid = document.getElementById('agents-grid');
    if (!grid) return;

    grid.innerHTML = agents.map(agent => `
        <div class="ecosystem-card agent-card ${agent.status}" onclick="openProfileModal('${agent.name}')" style="cursor: pointer;">
            <div class="card-header">
                <span class="card-title">${agent.name}</span>
                <div class="agent-status ${agent.status}">${agent.status}</div>
            </div>
            <div class="card-description">
                <strong>Type:</strong> ${agent.type}<br>
                ${agent.description || ''}
            </div>
        </div>
    `).join('');
}

// Close modals on outside click
window.onclick = function (event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = "none";
    }
}

function loadingStatus(active) {
    const indicator = document.querySelector('.status-indicator');
    if (active) {
        indicator.innerText = "EXECUTING...";
        indicator.classList.add('pulsing');
    } else {
        indicator.innerText = "ONLINE";
        indicator.classList.remove('pulsing');
    }
}

// Real-time Monitor
function updateMonitor(logs) {
    const monitor = document.getElementById('real-time-log');
    if (!monitor) return;

    logs.forEach(log => {
        const div = document.createElement('div');
        div.className = 'log-entry';
        if (log.includes('!!')) div.classList.add('error');
        if (log.startsWith('Node:')) div.classList.add('node-active');

        div.innerText = `> ${log}`;
        monitor.appendChild(div);
    });

    monitor.scrollTop = monitor.scrollHeight;

    // Also update Ops view if active
    updateOpsView(logs);
}

function updateOpsView(logs) {
    const opsContent = document.getElementById('ops-content');
    if (!opsContent) return;

    if (opsContent.querySelector('.empty-state')) opsContent.innerHTML = '';

    logs.forEach(log => {
        const div = document.createElement('div');
        div.className = 'ops-item';
        div.innerHTML = `<span class="timestamp">[${new Date().toLocaleTimeString()}]</span> ${log}`;
        opsContent.appendChild(div);
    });
}

// Messaging helpers
function addMessage(text, type, isLoading = false) {
    const history = document.getElementById('chat-history');
    const div = document.createElement('div');
    div.className = `message ${type}`;
    if (isLoading) div.id = `msg-${Date.now()}`;

    if (type === 'ai') {
        const parsed = marked.parse(text || "");
        div.innerHTML = `<div class="content">${parsed}</div>`;

        // Phase 15: Artifact Extraction
        const artifacts = extractArtifacts(text || "");
        if (artifacts.length > 0) {
            renderArtifacts(artifacts);
        }
    } else {
        div.innerHTML = `<div class="content">${text}</div>`;
    }

    history.appendChild(div);
    setTimeout(() => {
        history.scrollTo({ top: history.scrollHeight, behavior: 'smooth' });
    }, 50);

    return div.id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function handleEnter(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// Data Fetching
async function fetchMemory() {
    try {
        const res = await fetch(`${API_BASE}/memory`);
        if (!res.ok) {
            console.log("Memory endpoint not available");
            const list = document.getElementById('memory-list');
            if (list) {
                list.innerHTML = '<div class="empty-state">No memories found.</div>';
            }
            return;
        }

        const items = await res.json();
        const list = document.getElementById('memory-list');
        const count = document.getElementById('mem-count');

        if (list) {
            list.innerHTML = '';
        }
        if (count) {
            count.innerText = `${items.length} items`;
        }

        if (items.length === 0) {
            if (list) {
                list.innerHTML = '<div class="empty-state">No memories found.</div>';
            }
            return;
        }

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'memory-item';
            const content = typeof item.content === 'string' ? item.content : JSON.stringify(item.content);
            const metaStr = JSON.stringify(item.meta || {});

            div.innerHTML = `
                <div class="memory-meta">${metaStr}</div>
                <div class="memory-content">${content.substring(0, 200)}...</div>
            `;
            if (list) {
                list.appendChild(div);
            }
        });
    } catch (e) {
        console.log("Memory system not available");
        const list = document.getElementById('memory-list');
        if (list) {
            list.innerHTML = '<div class="empty-state">No memories found.</div>';
        }
    }
}

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        const dbStatus = document.getElementById('db-status');
        if (dbStatus) {
            dbStatus.className = data.memory_mode.includes("Mock") ? 'status-dot red' : 'status-dot green';
        }
    } catch (e) {
        console.error("Health check failed", e);
    }
}

async function wipeMemory() {
    if (!confirm("Wipe all memory clusters?")) return;
    await fetch(`${API_BASE}/wipe`, { method: 'POST' });
    fetchMemory();
    addMessage("Memory wiped.", 'system');
}

// Phase 7: Scripts & Workflows
async function executeScript(scriptName) {
    addMessage(`Executing script: ${scriptName}`, 'system');
    addLog(`[SCRIPT] Running ${scriptName}...`);

    try {
        const response = await fetch(`${API_BASE}/scripts/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script_name: scriptName })
        });

        if (response.ok) {
            const result = await response.json();
            addMessage(`Script completed: ${result.message || 'Success'}`, 'system');
        } else {
            addMessage(`Script execution via chat: ${scriptName}`, 'system');
            // Fallback: send as chat message
            document.getElementById('user-input').value = `Run script: ${scriptName}`;
            sendMessage();
        }
    } catch (e) {
        console.log(`Script API not available, using chat fallback`);
        document.getElementById('user-input').value = `Run script: ${scriptName}`;
        sendMessage();
    }
}

async function executeWorkflow(workflowName) {
    addMessage(`Starting workflow: ${workflowName}`, 'system');
    addLog(`[WORKFLOW] Initiating ${workflowName}...`);

    try {
        const response = await fetch(`${API_BASE}/workflows/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workflow_name: workflowName })
        });

        if (response.ok) {
            const result = await response.json();
            addMessage(`Workflow started: ${result.message || 'In progress'}`, 'system');
        } else {
            addMessage(`Workflow execution via chat: ${workflowName}`, 'system');
            // Fallback: send as chat message
            document.getElementById('user-input').value = `Start workflow: ${workflowName}`;
            sendMessage();
        }
    } catch (e) {
        console.log(`Workflow API not available, using chat fallback`);
        document.getElementById('user-input').value = `Start workflow: ${workflowName}`;
        sendMessage();
    }
}

// Workflow Studio Functions
let workflowSteps = [];

function renderWorkflowSteps() {
    const container = document.getElementById('workflow-steps');
    if (!container) return;

    container.innerHTML = '';

    if (workflowSteps.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No steps defined. Add a step to begin.</p></div>';
        return;
    }

    workflowSteps.forEach((step, index) => {
        const div = document.createElement('div');
        div.className = 'workflow-step-card';
        div.innerHTML = `
            <div class="step-number">${index + 1}</div>
            <div class="step-content">
                <select class="step-agent-select" onchange="updateStep(${index}, 'agent', this.value)">
                    <option value="Researcher" ${step.agent === 'Researcher' ? 'selected' : ''}>Researcher</option>
                    <option value="Analyst" ${step.agent === 'Analyst' ? 'selected' : ''}>Analyst</option>
                    <option value="Coder" ${step.agent === 'Coder' ? 'selected' : ''}>Coder</option>
                    <option value="Security" ${step.agent === 'Security' ? 'selected' : ''}>Security</option>
                    <option value="Architect" ${step.agent === 'Architect' ? 'selected' : ''}>Architect</option>
                </select>
                <textarea class="step-instruction" placeholder="Instruction for this agent..." onchange="updateStep(${index}, 'instruction', this.value)">${step.instruction || ''}</textarea>
                <button class="btn-remove" onclick="removeWorkflowStep(${index})">×</button>
            </div>
        `;
        container.appendChild(div);
    });
}

function addWorkflowStep() {
    workflowSteps.push({ agent: 'Researcher', instruction: '' });
    renderWorkflowSteps();
}

function removeWorkflowStep(index) {
    workflowSteps.splice(index, 1);
    renderWorkflowSteps();
}

function updateStep(index, field, value) {
    workflowSteps[index][field] = value;
}

// Generation Modal
function openGenerateModal() {
    const modal = document.getElementById('generate-modal');
    if (modal) {
        modal.style.display = 'block';
        document.getElementById('generate-prompt').focus();
    }
}

function closeGenerateModal() {
    const modal = document.getElementById('generate-modal');
    if (modal) modal.style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function (event) {
    const modal = document.getElementById('generate-modal');
    if (event.target == modal) {
        closeGenerateModal();
    }
}

async function generateWorkflow() {
    const prompt = document.getElementById('generate-prompt').value;
    if (!prompt) return alert("Please enter a prompt.");

    const generateBtn = document.querySelector('#generate-modal .btn.accent');
    const originalText = generateBtn.innerText;
    generateBtn.innerText = "Generating...";
    generateBtn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/workflows/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });

        if (!res.ok) throw new Error("Generation failed");

        const data = await res.json();

        // Populate UI
        document.getElementById('workflow-name').value = data.name || "AI Generated Workflow";
        workflowSteps = data.steps || [];
        renderWorkflowSteps();

        closeGenerateModal();
        alert("Workflow generated successfully!");

    } catch (e) {
        alert("Error generating workflow: " + e.message);
    } finally {
        generateBtn.innerText = originalText;
        generateBtn.disabled = false;
    }
}

async function saveWorkflow() {
    const name = document.getElementById('workflow-name').value;
    if (!name) return alert("Please enter a workflow name");

    const workflow = { name: name, steps: workflowSteps };

    try {
        const res = await fetch(`${API_BASE}/workflows/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(workflow)
        });
        if (res.ok) alert("Workflow saved!");
    } catch (e) {
        alert("Error saving workflow");
    }
}

async function runWorkflow() {
    const nameInput = document.getElementById('workflow-name');
    const logsDiv = document.getElementById('workflow-logs');
    const logContent = document.getElementById('workflow-log-content');
    logsDiv.style.display = 'block';

    // Clear previous logs
    logContent.innerHTML = '> Starting workflow...\n';

    const workflow = {
        name: nameInput ? nameInput.value : "Untitled",
        steps: workflowSteps
    };

    try {
        const response = await fetch(`${API_BASE}/workflows/execute_new`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(workflow)
        });

        if (!response.ok) {
            throw new Error(`Server Error: ${response.status} ${response.statusText}`);
        }

        const reader = response.body.getReader();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = new TextDecoder().decode(value);
            logContent.innerHTML += text;
            logContent.scrollTop = logContent.scrollHeight;
        }
    } catch (e) {
        logContent.innerHTML += `> Error: ${e.message}\n`;
    }
}

// Command Window
function handleCommandEnter(event) {
    if (event.key === 'Enter') {
        const input = document.getElementById('command-input');
        const cmd = input.value.trim();
        if (cmd) {
            addCommandLine(`> ${cmd}`);
            // Send command to agent
            sendMessage(); // Reuse existing chat logic
            input.value = '';
        }
    }
}

function addCommandLine(text) {
    const output = document.getElementById('command-output');
    const line = document.createElement('div');
    line.className = 'cmd-line';
    line.textContent = text;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
}

function toggleCommandWindow() {
    const cmdWindow = document.querySelector('.command-window');
    cmdWindow.classList.toggle('collapsed');
}

// Log Filtering
function filterLogs(level) {
    const logs = document.querySelectorAll('.log-entry');
    const buttons = document.querySelectorAll('.filter-btn');

    buttons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.level === level);
    });

    logs.forEach(log => {
        if (level === 'all') {
            log.style.display = 'block';
        } else {
            log.style.display = log.classList.contains(level) ? 'block' : 'none';
        }
    });
}

// Memory Search
async function searchMemory() {
    const query = document.getElementById('memory-search-input').value;
    if (!query) return;

    try {
        const response = await fetch(`${API_BASE}/memory?query=${encodeURIComponent(query)}`);
        const results = await response.json();
        displayMemoryResults(results);
    } catch (e) {
        console.error("Memory search failed:", e);
    }
}

function displayMemoryResults(results) {
    const container = document.getElementById('memory-results');
    if (!results || results.length === 0) {
        container.innerHTML = '<div class="empty-state">No memories found.</div>';
        return;
    }

    container.innerHTML = results.map(item => `
        <div class="memory-item">
            <div class="memory-content">${item.content}</div>
            <div class="memory-meta">${JSON.stringify(item.meta)}</div>
        </div>
    `).join('');
}

async function consolidateMemory() {
    addMessage("Consolidating memories...", 'system');
    // TODO: Call consolidation endpoint
    console.log("Consolidate memory");
}


// --- Remote View & Direct Control ---
let remoteViewMode = 'system'; // 'system' or 'browser'

function toggleRemoteView(mode) {
    remoteViewMode = mode;
    document.getElementById('btn-view-system').className = mode === 'system' ? 'btn small primary' : 'btn small secondary';
    document.getElementById('btn-view-browser').className = mode === 'browser' ? 'btn small primary' : 'btn small secondary';

    // Immediate update
    pollRemoteView();
}

async function pollRemoteView() {
    const img = document.getElementById('remote-feed');
    const status = document.getElementById('remote-status');
    if (!img) return;

    const filename = remoteViewMode === 'system' ? 'screen.png' : 'browser_screen.png';
    const url = `/dashboard/screenshots/${filename}?t=${Date.now()}`;

    // Pre-load image to avoid flickering
    const tempImg = new Image();
    tempImg.onload = () => {
        img.src = url;
        img.style.opacity = '1';
        status.innerText = remoteViewMode === 'system' ? 'Live System Feed' : 'Live Browser Feed';
        status.style.color = '#fff';
    };
    tempImg.onerror = () => {
        // If image doesn't exist yet, just show waiting
        status.innerText = "Waiting for feed...";
        status.style.color = '#aaa';
    };
    tempImg.src = url;
}

async function sendDirectCommand() {
    const input = document.getElementById('cmd-input');
    const cmd = input.value.trim();
    if (!cmd) return;

    // Send as a special system override message
    const overrideMsg = `SYSTEM OVERRIDE: Execute shell command: ${cmd}`;

    // Add to chat manually
    addMessage(`Direct Command: ${cmd}`, 'user');
    input.value = '';

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: overrideMsg })
        });
        const data = await response.json();
        addMessage(data.response, 'ai');
    } catch (e) {
        addMessage(`Error: ${e.message}`, 'system');
    }
}

// Settings Functions
async function saveSettings() {
    const model = document.getElementById('setting-llm').value;

    try {
        const response = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_mode: false })
        });

        if (response.ok) {
            addMessage('Settings saved successfully', 'system');
            addLog('[SETTINGS] Configuration updated');
        } else {
            addMessage('Failed to save settings', 'system');
        }
    } catch (e) {
        addMessage(`Error saving settings: ${e.message}`, 'system');
        console.error('Save settings error:', e);
    }
}

async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
            addMessage('Settings reloaded', 'system');
            addLog('[SETTINGS] Configuration reloaded');
        }
    } catch (e) {
        addMessage(`Error loading settings: ${e.message}`, 'system');
    }
}

async function saveApiKey() {
    const apiKey = document.getElementById('setting-api-key').value;
    if (!apiKey) {
        addMessage('Please enter an API key', 'system');
        return;
    }

    try {
        // Note: In a real implementation, you'd send this to a secure endpoint
        addMessage('API key saved (client-side only for demo)', 'system');
        document.getElementById('setting-api-key').value = '';
        addLog('[SETTINGS] API key updated');
    } catch (e) {
        addMessage(`Error saving API key: ${e.message}`, 'system');
    }
}

// Initialize
window.onload = () => {
    checkHealth();
    connectWebSocket();
    fetchMemory();
    setInterval(fetchMemory, 10000);
    setInterval(checkHealth, 30000);
};

// --- Phase 15: Artifacts & Tabs ---

function switchRightTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.onclick.toString().includes(tabName));
    });

    // Update content
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.toggle('active', tab.id === `tab-${tabName}`);
    });
}

function extractArtifacts(content) {
    // Regex to find code blocks: ```language\ncode\n```
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let match;
    let artifacts = [];

    while ((match = codeBlockRegex.exec(content)) !== null) {
        artifacts.push({
            language: match[1] || 'text',
            code: match[2],
            timestamp: new Date()
        });
    }
    return artifacts;
}

function renderArtifacts(artifacts) {
    const container = document.getElementById('artifacts-container');
    if (!container) return;

    // Remove empty state if we have artifacts
    if (artifacts.length > 0 && container.querySelector('.empty-state')) {
        container.innerHTML = '';
    }

    artifacts.forEach(art => {
        const id = 'art-' + Math.random().toString(36).substr(2, 9);
        const isPython = art.language.toLowerCase() === 'python' || art.language.toLowerCase() === 'py';

        const html = `
            <div class="artifact-item" id="${id}">
                <div class="artifact-header">
                    <span class="artifact-lang">${art.language}</span>
                    <span class="artifact-time" style="font-size: 0.7rem; color: #666;">${art.timestamp.toLocaleTimeString()}</span>
                </div>
                <div class="artifact-content">
                    <pre><code>${escapeHtml(art.code)}</code></pre>
                </div>
                <div class="artifact-actions">
                    <button class="btn small secondary" onclick="copyToClipboard('${id}')">Copy</button>
                    ${isPython ? `<button class="btn small primary" onclick="runArtifact('${id}')">Run ▶</button>` : ''}
                </div>
            </div>
        `;
        container.insertAdjacentHTML('afterbegin', html);
    });

    // Switch to artifacts tab if new artifacts found
    if (artifacts.length > 0) {
        switchRightTab('artifacts');
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function (m) { return map[m]; });
}

function copyToClipboard(id) {
    const el = document.getElementById(id);
    const code = el.querySelector('code').innerText;
    navigator.clipboard.writeText(code);
}

function runArtifact(id) {
    const el = document.getElementById(id);
    const code = el.querySelector('code').innerText;

    // Send to backend via execute_script or direct tool use
    // For PoC, we'll use the chat input with a system directive or hidden API
    // Let's use the execute_python tool via chat for visibility
    const input = document.getElementById('user-input');
    // Using a direct tool call pattern usually handled by the agent, 
    // but here we can just execute it via a specialized endpoint or simulate user request.
    // Simulating user request:
    sendMessage(`Execute this python code:\n\`\`\`python\n${code}\n\`\`\``);
    switchRightTab('terminal'); // Switch back to see output
}

function clearArtifacts() {
    const container = document.getElementById('artifacts-container');
    if (container) {
        container.innerHTML = '<div class="empty-state">No artifacts generated yet.</div>';
    }
}

// --- Phase 14: Platform Ecosystem Logic ---

async function fetchWorkflows() {
    try {
        const res = await fetch(`${API_BASE}/workflows`);
        const data = await res.json();
        // Ensure data.workflows is an array, handle if backend returns object with 'workflows' key
        // Based on server.py: return {"workflows": workflow_engine.list_workflows()}
        renderWorkflows(data.workflows || []);
    } catch (e) {
        console.error("Failed to fetch workflows", e);
    }
}

function renderWorkflows(workflows) {
    const grid = document.getElementById('workflows-grid');
    if (!grid) return;

    if (workflows.length === 0) {
        grid.innerHTML = '<div class="empty-state">No workflows found.</div>';
        return;
    }

    grid.innerHTML = workflows.map(wf => `
        <div class="ecosystem-card workflow-card">
            <div class="card-header">
                <span class="card-title">${wf.name || wf}</span>
                <span class="card-icon">🔄</span>
            </div>
            <div class="card-description">${wf.description || 'System Workflow'}</div>
            <div class="card-footer">
                <button class="btn primary small" onclick="executeWorkflow('${wf.name || wf}')">Run Workflow</button>
            </div>
        </div>
    `).join('');
}

async function fetchSkills() {
    try {
        const res = await fetch(`${API_BASE}/tools`);
        const tools = await res.json();
        renderSkills(tools);
    } catch (e) {
        console.error("Failed to fetch skills", e);
    }
}

function renderSkills(tools) {
    const grid = document.getElementById('skills-grid');
    if (!grid) return;

    grid.innerHTML = tools.map(tool => `
        <div class="ecosystem-card skill-card">
            <div class="card-header">
                <span class="card-title">${tool.name}</span>
                <span class="card-icon">⚡</span>
            </div>
            <div class="skill-args" title="${JSON.stringify(tool.args)}">Args: ${Object.keys(tool.args?.properties || {}).join(', ') || 'None'}</div>
            <div class="card-description">${tool.description || 'No description.'}</div>
            <div class="card-footer">
                <button class="btn secondary small" onclick="useSkill('${tool.name}')">Use Skill</button>
            </div>
        </div>
    `).join('');
}

function useSkill(toolName) {
    // Populate chat input
    const input = document.getElementById('user-input');
    input.value = `Use tool: ${toolName}`;
    input.focus();
}

async function fetchAgents() {
    try {
        const res = await fetch(`${API_BASE}/agents`);
        const data = await res.json();
        renderAgents(data.agents);
    } catch (e) {
        console.error("Failed to fetch agents", e);
    }
}

function renderAgents(agents) {
    const grid = document.getElementById('agents-grid');
    if (!grid) return;

    grid.innerHTML = agents.map(agent => `
        <div class="ecosystem-card agent-card ${agent.status}">
            <div class="card-header">
                <span class="card-title">${agent.name}</span>
                <div class="agent-status ${agent.status}">${agent.status}</div>
            </div>
            <div class="card-description">
                <strong>Type:</strong> ${agent.type}<br>
                ${agent.description || ''}
            </div>
        </div>
    `).join('');
}

function filterGrid(input, gridId) {
    const filter = input.value.toUpperCase();
    const grid = document.getElementById(gridId);
    if (!grid) return;

    const cards = grid.getElementsByClassName('ecosystem-card');
    for (let i = 0; i < cards.length; i++) {
        const title = cards[i].querySelector('.card-title');
        if (title.innerText.toUpperCase().indexOf(filter) > -1) {
            cards[i].style.display = "";
        } else {
            cards[i].style.display = "none";
        }
    }
}
