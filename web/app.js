const API_URL = "http://localhost:8000";
const API_KEY = "";

const messageContainer = document.getElementById("message-container");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

// Button Elements
const lightningBtn = document.getElementById("lightning-btn");
const settingsBtn = document.getElementById("settings-btn");
const settingsModal = document.getElementById("settings-modal");
const saveSettingsBtn = document.getElementById("save-settings-btn");
const closeSettingsBtn = document.getElementById("close-settings-btn");

// Console and Artifact Elements
const systemConsole = document.getElementById("system-console");
const artifactContainer = document.getElementById("artifact-container");
const toggleActivityBtn = document.getElementById("toggle-activity-btn");
const activityPanel = document.querySelector(".activity-panel");

// Settings values (local state)
let currentApiUrl = API_URL;
let currentApiKey = API_KEY;
let openaiApiKey = ""; // Default

let lightningMode = false;

// Tab Navigation
const navItems = document.querySelectorAll(".nav-item");
const tabPanels = document.querySelectorAll(".tab-panel");

navItems.forEach(item => {
    item.addEventListener("click", () => {
        const targetTab = item.getAttribute("data-tab");

        navItems.forEach(nav => nav.classList.remove("active"));
        item.classList.add("active");

        tabPanels.forEach(panel => {
            panel.classList.toggle("hidden", panel.id !== `${targetTab}-panel`);
        });

        if (targetTab === "agents") fetchAgents();
        if (targetTab === "skills") fetchSkills();
    });
});

// Panel Toggle Logic
toggleActivityBtn.addEventListener("click", () => {
    activityPanel.classList.toggle("collapsed");
    toggleActivityBtn.textContent = activityPanel.classList.contains("collapsed") ? "⟪" : "⟫";
});

function logActivity(message, type = "LOG") {
    const timestamp = new Date().toLocaleTimeString([], { hour12: false });
    const logLine = `[${timestamp}] [${type}] ${message}\n`;
    systemConsole.innerText += logLine;
    systemConsole.scrollTop = systemConsole.scrollHeight;
}

function updateArtifact(content, title = "Generated Artifact") {
    // Reveal panel if collapsed
    activityPanel.classList.remove("collapsed");
    toggleActivityBtn.textContent = "⟫";

    if (content.trim().startsWith("```")) {
        // Simple code block extraction
        const code = content.replace(/```[a-z]*\n/g, "").replace(/```/g, "");
        artifactContainer.innerHTML = `
            <div class="code-header glass">
                <span>${title}</span>
                <button class="btn-small" onclick="navigator.clipboard.writeText(\`${code.replace(/`/g, "\\`")}\`)">Copy</button>
            </div>
            <pre class="code-block">${code}</pre>
        `;
    } else {
        artifactContainer.innerHTML = `<div class="artifact-text">${content}</div>`;
    }
}

async function addMessage(text, role, meta = "") {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role} glass`;

    msgDiv.innerHTML = `
        <div class="msg-content">${text}</div>
        <div class="msg-meta">${meta || (role === 'ai' ? 'OMNIOS Core' : 'User Session')}</div>
    `;

    messageContainer.appendChild(msgDiv);
    messageContainer.scrollTop = messageContainer.scrollHeight;
}

async function processRequest(query) {
    addMessage(query, "user");
    userInput.value = "";
    logActivity(`User Query: ${query.substring(0, 30)}...`, "INPUT");

    try {
        logActivity("Routing request to Coordinator Agent...", "AGENT");
        const response = await fetch(`${currentApiUrl}/process`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": currentApiKey
            },
            body: JSON.stringify({
                query,
                context: {
                    mode: lightningMode ? "fast" : "reasoning",
                    openai_api_key: openaiApiKey,
                    user_id: "default_user"
                }
            })
        });

        const data = await response.json();

        if (data.status === "success" || data.response) {
            const resp = data.response || data;
            const responseText = typeof resp === 'string'
                ? resp
                : JSON.stringify(resp, null, 2);

            // OpenClaw-style Artifact check: If there's a code block, move it to the panel
            if (responseText.includes("```")) {
                const codeMatch = responseText.match(/```[\s\S]*?```/);
                if (codeMatch) {
                    updateArtifact(codeMatch[0]);
                    const cleanText = responseText.replace(codeMatch[0], "\n*(Code extracted to Artifacts panel)*");
                    addMessage(cleanText, "ai", lightningMode ? "Fast Engine" : "Reasoning Engine");
                } else {
                    addMessage(responseText, "ai", lightningMode ? "Fast Engine" : "Reasoning Engine");
                }
            } else {
                addMessage(responseText, "ai", lightningMode ? "Fast Engine" : "Reasoning Engine");
            }
            logActivity("Response received and processed.", "DONE");
        } else {
            const errorMsg = data.detail || (data.error && data.error.message) || data.message || "Unknown error";
            addMessage(`Error: ${errorMsg}`, "ai", "System Error");
            logActivity(`Error: ${errorMsg}`, "ERROR");
            if (errorMsg.includes("API key")) {
                addMessage("TIP: Update your OpenAI API Key in the Settings (⚙️) panel.", "ai", "System Tip");
            }
        }
    } catch (err) {
        addMessage(`Failed to connect to OMNIOS API.`, "ai", "Connection Error");
        logActivity("Connection failed.", "ERROR");
    }
}

// Data Fetching
async function fetchAgents() {
    const container = document.getElementById("agents-list");
    container.innerHTML = "<p>Analyzing Agent Fabric...</p>";
    try {
        const res = await fetch(`${currentApiUrl}/agents`, { headers: { "X-API-Key": currentApiKey } });
        const data = await res.json();
        container.innerHTML = data.agents.map(a => `
            <div class="status-card glass">
                <div class="status-icon">${a.name.includes("Tool") ? "🔧" : "🧠"}</div>
                <div class="status-info">
                    <h3>${a.name}</h3>
                    <div class="tags">
                        ${a.capabilities.map(c => `<span class="tag">${c}</span>`).join('')}
                    </div>
                </div>
            </div>
        `).join("");
    } catch (e) { container.innerHTML = "Error loading agents."; }
}

async function fetchSkills() {
    const container = document.getElementById("skills-list");
    container.innerHTML = "<p>Discovering Skills...</p>";
    try {
        const res = await fetch(`${currentApiUrl}/skills`, { headers: { "X-API-Key": currentApiKey } });
        const data = await res.json();
        container.innerHTML = data.skills.map(s => `
            <div class="grid-card glass">
                <h3>${s.name}</h3>
                <p>${s.description}</p>
                <button class="btn-small" onclick="processRequest('Use skill: ${s.name}')">Import</button>
            </div>
        `).join("");
    } catch (e) { container.innerHTML = "Error loading skills."; }
}

// Workflow Execution
document.querySelectorAll("#workflow-list .btn-small").forEach(btn => {
    btn.addEventListener("click", () => {
        const workflowName = btn.parentElement.querySelector("h3").innerText;
        executeWorkflow(workflowName);
    });
});

async function executeWorkflow(name) {
    logActivity(`Executing Workflow: ${name}`, "WORKFLOW");
    addMessage(`Command: Run ${name}`, "user");

    // Switch to Chat tab to see feedback
    document.querySelector('[data-tab="chat"]').click();

    try {
        const response = await fetch(`${currentApiUrl}/workflows/execute`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": currentApiKey
            },
            body: JSON.stringify({ name })
        });
        const data = await response.json();

        if (data.status === "success") {
            addMessage(data.response, "ai", "Workflow Engine");
            logActivity(`Workflow ${name} completed successfully.`, "DONE");
        } else {
            addMessage(`Workflow Error: ${data.detail}`, "ai", "Workflow Engine");
            logActivity(`Workflow ${name} failed.`, "ERROR");
        }
    } catch (e) {
        addMessage(`Failed to connect to Workflow Engine.`, "ai", "Connection Error");
        logActivity(`Workflow ${name} connection error.`, "ERROR");
    }
}
sendBtn.addEventListener("click", () => {
    const val = userInput.value.trim();
    if (val) processRequest(val);
});

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
    }
});

lightningBtn.addEventListener("click", () => {
    lightningMode = !lightningMode;
    lightningBtn.style.color = lightningMode ? "var(--accent-green)" : "white";
    lightningBtn.style.textShadow = lightningMode ? "0 0 10px var(--accent-green)" : "none";
    addMessage(`System mode switched to: ${lightningMode ? 'FAST (Latency Optimized)' : 'REASONING (Advanced Logic)'}`, "ai", "System Notification");
});

settingsBtn.addEventListener("click", () => {
    settingsModal.classList.remove("hidden");
});

closeSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.add("hidden");
});

saveSettingsBtn.addEventListener("click", () => {
    currentApiUrl = document.getElementById("setting-api-url").value;
    currentApiKey = document.getElementById("setting-api-key").value;
    openaiApiKey = document.getElementById("setting-api-key").value; // Reuse password field for simplicity in this PoC
    settingsModal.classList.add("hidden");
    addMessage("Connection settings and LLM keys updated successfully.", "ai", "System Notification");
});
