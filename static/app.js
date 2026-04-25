let currentProject = null;
let currentTab = 'readme';

async function init() {
    await fetchStats();
    await fetchProjects();
}

async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        const container = document.getElementById('global-stats');
        container.innerHTML = `
            <div class="stat-card">
                <span class="stat-label">Total Projects</span>
                <span class="stat-value">${stats.total_projects}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Live Deployments</span>
                <span class="stat-value">${stats.active_deployments}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Monthly Cloud Spend</span>
                <span class="stat-value">$${stats.total_monthly_cost}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Security Risks</span>
                <span class="stat-value">${stats.total_security_issues}</span>
            </div>
        `;
    } catch (e) {
        console.error("Failed to fetch stats", e);
    }
}

async function fetchProjects() {
    try {
        const response = await fetch('/api/projects');
        const projects = await response.json();
        
        const grid = document.getElementById('projects-grid');
        grid.innerHTML = projects.map(p => `
            <div class="project-card" onclick="openProject('${p.slug}')">
                <div class="project-card-header">
                    <div>
                        <div class="project-slug">${p.slug}</div>
                        <span class="project-provider">${p.provider}</span>
                    </div>
                    <span class="status-badge status-${p.status}">${p.status}</span>
                </div>
                <div class="project-card-body">
                    <p class="project-prompt">${p.prompt || 'No description provided.'}</p>
                    <div class="project-meta">
                        <div class="meta-item">
                            <span class="meta-label">Est. Cost</span>
                            <span class="meta-value">$${p.estimated_cost}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Security</span>
                            <span class="meta-value">${p.security_issues} issues</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error("Failed to fetch projects", e);
    }
}

async function openProject(slug) {
    currentProject = slug;
    document.getElementById('modal-project-slug').innerText = slug;
    document.getElementById('project-modal').style.display = 'flex';
    switchTab('readme');
}

function closeModal() {
    document.getElementById('project-modal').style.display = 'none';
}

async function switchTab(tab) {
    currentTab = tab;
    
    // Update UI active state
    document.querySelectorAll('.modal-tabs .tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.innerText.toLowerCase().includes(tab));
    });

    const contentArea = document.getElementById('modal-body-content');
    contentArea.innerHTML = '<p>Loading...</p>';

    try {
        if (tab === 'readme') {
            const res = await fetch(`/api/projects/${currentProject}/readme`);
            const data = await res.json();
            contentArea.innerHTML = `<pre class="log-view">${data.content}</pre>`;
        } else if (tab === 'code') {
            const res = await fetch(`/api/projects/${currentProject}/code`);
            const data = await res.json();
            let html = '';
            for (const [filename, content] of Object.entries(data)) {
                html += `<h3>${filename}</h3><pre><code>${content.replace(/</g, '&lt;')}</code></pre><br>`;
            }
            contentArea.innerHTML = html;
        } else if (tab === 'finance') {
            const res = await fetch(`/api/projects/${currentProject}/report`);
            const data = await res.json();
            contentArea.innerHTML = `<pre class="log-view">${data.content}</pre>`;
        } else if (tab === 'logs') {
            contentArea.innerHTML = `
                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <button class="tab-btn active" onclick="loadSpecificLog('terraform_plan')">Plan</button>
                    <button class="tab-btn" onclick="loadSpecificLog('terraform_apply')">Apply</button>
                    <button class="tab-btn" onclick="loadSpecificLog('terraform_destroy')">Destroy</button>
                </div>
                <div id="log-display-area">Select a log type above</div>
            `;
            loadSpecificLog('terraform_plan');
        }
    } catch (e) {
        contentArea.innerHTML = `<p style="color: var(--status-failed)">Error loading content: ${e.message}</p>`;
    }
}

async function loadSpecificLog(type) {
    const area = document.getElementById('log-display-area');
    area.innerHTML = 'Loading log...';
    try {
        const res = await fetch(`/api/projects/${currentProject}/logs/${type}`);
        const data = await res.json();
        area.innerHTML = `<pre class="log-view">${data.content}</pre>`;
    } catch (e) {
        area.innerHTML = 'Log file not found.';
    }
}

function refreshData() {
    init();
}

// ─── Phase 7: Multi-Cloud Logic ────────────────────────────────────

function switchCredTab(provider) {
    document.querySelectorAll('[id^="cred-panel-"]').forEach(p => p.style.display = 'none');
    document.getElementById(`cred-panel-${provider}`).style.display = (provider === 'gcp') ? 'block' : 'grid';
    
    // Update button active states
    event.target.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
}

// ─── Phase 6b/7: Generation Logic ────────────────────────────────────

let logInterval = null;

async function generateInfra() {
    const prompt = document.getElementById('infra-prompt').value;
    const budget = document.getElementById('infra-budget').value;
    const apply = document.getElementById('infra-apply').checked;
    
    // Collect credentials for all clouds
    const credentials = {
        AWS_ACCESS_KEY_ID: document.getElementById('aws-key').value,
        AWS_SECRET_ACCESS_KEY: document.getElementById('aws-secret').value,
        AWS_DEFAULT_REGION: document.getElementById('aws-region').value,
        ARM_CLIENT_ID: document.getElementById('az-client-id').value,
        ARM_CLIENT_SECRET: document.getElementById('az-client-secret').value,
        ARM_SUBSCRIPTION_ID: document.getElementById('az-subscription-id').value,
        ARM_TENANT_ID: document.getElementById('az-tenant-id').value,
        GOOGLE_CREDENTIALS: document.getElementById('gcp-json').value
    };

    // Collect AI configuration
    const ai_config = {
        provider: document.getElementById('ai-provider').value,
        model: document.getElementById('ai-model').value,
        key: document.getElementById('ai-key').value
    };


    if (!prompt) {
        alert("Please enter an infrastructure requirement.");
        return;
    }

    // Update UI
    document.getElementById('gen-status').style.display = 'inline-block';
    document.getElementById('live-console-container').style.display = 'block';
    const consoleElem = document.getElementById('live-console');
    consoleElem.innerText = "🚀 Requesting generation...";

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, budget, apply, credentials, ai_config })
        });
        
        const data = await response.json();
        consoleElem.innerText = "✅ Workflow queued. Streaming logs...\n";
        startPollingLogs();
    } catch (e) {
        consoleElem.innerText = "❌ Error: " + e.message;
    }
}

function startPollingLogs() {
    if (logInterval) clearInterval(logInterval);
    
    logInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/logs/active');
            const data = await res.json();
            const consoleElem = document.getElementById('live-console');
            
            // Auto-scroll if at bottom
            const isAtBottom = consoleElem.scrollHeight - consoleElem.clientHeight <= consoleElem.scrollTop + 1;
            consoleElem.innerText = data.logs;
            if (isAtBottom) {
                consoleElem.scrollTop = consoleElem.scrollHeight;
            }

            if (data.logs.includes('✅ Workflow Finished')) {
                stopPollingLogs();
                document.getElementById('gen-status').style.display = 'none';
                init(); // Refresh grid to show new project
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }, 1000);
}

function stopPollingLogs() {
    if (logInterval) {
        clearInterval(logInterval);
        logInterval = null;
    }
}

// Close modal on outside click

window.onclick = function(event) {
    const modal = document.getElementById('project-modal');
    if (event.target == modal) closeModal();
}

init();
