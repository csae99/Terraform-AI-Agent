let currentProject = null;
let logInterval = null;

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
    } catch (e) { console.error("Stats fetch error", e); }
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
                    <p class="project-prompt">${p.prompt || 'No description...'}</p>
                    <div class="project-meta">
                        <div class="meta-item"><span class="meta-label">Cost</span><span class="meta-value">$${p.estimated_cost}</span></div>
                        <div class="meta-item"><span class="meta-label">Security</span><span class="meta-value">${p.security_issues}</span></div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) { console.error("Project fetch error", e); }
}

async function openProject(slug) {
    try {
        const response = await fetch(`/api/projects/${slug}`);
        const project = await response.json();
        currentProject = project;

        document.getElementById('modal-project-slug').innerText = project.slug;
        document.getElementById('project-modal').style.display = 'flex';

        // Drift Status Badge
        const driftBadge = document.getElementById('modal-drift-status');
        if (project.drift_status) {
            driftBadge.innerText = project.drift_status === 'in_sync' ? '✅ In Sync' : '⚠️ Drifted';
            driftBadge.className = `status-badge status-${project.drift_status === 'in_sync' ? 'deployed' : 'failed'}`;
            driftBadge.style.display = 'inline-block';
        } else {
            driftBadge.style.display = 'none';
        }

        // Initialize Mermaid
        const mermaidContainer = document.getElementById('mermaid-container');
        if (project.mermaid_diagram) {
            mermaidContainer.innerHTML = project.mermaid_diagram;
            mermaidContainer.removeAttribute('data-processed');
        } else {
            mermaidContainer.innerHTML = "<p>No topology available.</p>";
        }

        switchModalTab('code');
    } catch (err) { console.error("Open project error", err); }
}

async function checkDrift() {
    if (!currentProject) return;
    const slug = currentProject.slug;
    const driftBadge = document.getElementById('modal-drift-status');
    driftBadge.innerText = "⏳ Scanning...";
    driftBadge.className = "status-badge status-generating";
    driftBadge.style.display = 'inline-block';

    try {
        const response = await fetch(`/api/projects/${slug}/drift`);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Server Error (${response.status}): ${text.substring(0, 100)}`);
        }
        const data = await response.json();
        alert(data.message);
        openProject(slug);
        fetchProjects();
    } catch (e) {
        alert("Drift scan failed: " + e.message);
        driftBadge.style.display = 'none';
        openProject(slug); // Reset badge
    }

}

function closeModal() {
    document.getElementById('project-modal').style.display = 'none';
}

async function switchModalTab(tabId) {
    document.querySelectorAll('.modal-tab-content').forEach(c => c.style.display = 'none');
    const activeContent = document.getElementById(`modal-tab-${tabId}`);
    if (activeContent) activeContent.style.display = 'block';

    document.querySelectorAll('.modal-tab').forEach(btn => {
        btn.classList.toggle('active', btn.innerText.toLowerCase().includes(tabId.slice(0, 4)));
    });

    if (tabId === 'code' && currentProject) {
        const res = await fetch(`/api/projects/${currentProject.slug}/code`);
        const files = await res.json();
        let html = '';
        for (const [f, c] of Object.entries(files)) {
            html += `<h4 style="color:var(--accent-blue)">${f}</h4><pre style="background:#000; padding:1rem; border-radius:4px; font-size:0.8rem"><code>${c.replace(/</g,'&lt;')}</code></pre>`;
        }
        document.getElementById('modal-tab-code-content').innerHTML = html;
    } else if (tabId === 'visual' && currentProject?.mermaid_diagram) {
        const container = document.getElementById('mermaid-container');
        mermaid.run({ nodes: [container] });
    } else if (tabId === 'evolution' && currentProject) {
        loadSnapshots(currentProject.slug);
    } else if (tabId === 'financial' && currentProject) {
        const res = await fetch(`/api/projects/${currentProject.slug}/report`);
        const data = await res.json();
        document.getElementById('modal-financial-report').innerText = data.content;
    } else if (tabId === 'logs' && currentProject) {
        const res = await fetch(`/api/projects/${currentProject.slug}/logs/terraform_plan`);
        const data = await res.json();
        document.getElementById('modal-tab-logs-content').innerHTML = `<pre class="log-view">${data.content}</pre>`;
    }
}


async function loadSnapshots(slug) {
    const res = await fetch(`/api/projects/${slug}/snapshots`);
    const snapshots = await res.json();
    const container = document.getElementById('snapshot-items');
    container.innerHTML = snapshots.map(s => `
        <div class="snapshot-item" onclick="viewDiff('${slug}', '${s.id}')" style="cursor:pointer; padding:0.5rem; margin-bottom:0.5rem; border:1px solid var(--border); border-radius:4px; font-size:0.8rem">
            ${s.timestamp}
        </div>
    `).join('') || '<p>No snapshots yet.</p>';
}

async function viewDiff(slug, snapshotId) {
    const res = await fetch(`/api/projects/${slug}/diff/${snapshotId}`);
    const data = await res.json();
    const viewer = document.getElementById('diff-viewer');
    
    // Simple diff highlighting
    const coloredDiff = data.diff.split('\n').map(line => {
        if (line.startsWith('+')) return `<span style="color:#4ade80">${line}</span>`;
        if (line.startsWith('-')) return `<span style="color:#f87171">${line}</span>`;
        if (line.startsWith('@@')) return `<span style="color:#60a5fa">${line}</span>`;
        return line;
    }).join('\n');
    
    viewer.innerHTML = `<pre style="white-space:pre-wrap"><code>${coloredDiff}</code></pre>`;
}

function switchCredTab(provider) {
    document.querySelectorAll('[id^="cred-panel-"]').forEach(p => p.style.display = 'none');
    document.getElementById(`cred-panel-${provider}`).style.display = (provider === 'gcp') ? 'block' : 'grid';
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
}

async function refreshData() {
    const btn = event?.target;
    if (btn) {
        btn.innerText = "⏳ Loading...";
        btn.disabled = true;
    }
    await init();
    if (btn) {
        btn.innerText = "Refresh";
        btn.disabled = false;
    }
}

async function generateInfra() {
    const prompt = document.getElementById('infra-prompt').value;
    const budget = document.getElementById('infra-budget').value;
    const apply = document.getElementById('infra-apply').checked;
    const genBtn = document.querySelector('button[onclick="generateInfra()"]');

    if (!prompt) return alert("Enter a prompt!");

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

    const ai_config = {
        provider: document.getElementById('ai-provider').value,
        model: document.getElementById('ai-model').value,
        key: document.getElementById('ai-key').value
    };

    // UI Feedback
    genBtn.disabled = true;
    genBtn.innerText = "🚀 Starting...";
    document.getElementById('gen-status').style.display = 'inline-block';
    
    // Open the Live Modal
    document.getElementById('live-console-modal').style.display = 'flex';
    const consoleElem = document.getElementById('live-console');
    consoleElem.innerText = "🚀 Connecting to Agent Engine...\n";

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, budget, apply, credentials, ai_config })
        });
        
        if (!response.ok) throw new Error(await response.text());
        
        startPollingLogs();
    } catch (e) { 
        consoleElem.innerText += "\n❌ Error: " + e.message;
        genBtn.disabled = false;
        genBtn.innerText = "Generate";
        document.getElementById('gen-status').style.display = 'none';
    }
}

function startPollingLogs() {
    const genBtn = document.querySelector('button[onclick="generateInfra()"]');
    if (logInterval) clearInterval(logInterval);
    
    logInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/logs/active');
            const data = await res.json();
            const consoleElem = document.getElementById('live-console');
            
            if (data.logs && data.logs !== "No active run.") {
                consoleElem.innerText = data.logs;
                consoleElem.scrollTop = consoleElem.scrollHeight;
            }

            if (data.logs.includes('✅ Workflow Finished')) {
                clearInterval(logInterval);
                genBtn.disabled = false;
                genBtn.innerText = "Generate";
                document.getElementById('gen-status').style.display = 'none';
                setTimeout(() => {
                    init();
                    alert("✅ Infrastructure Generation Complete!");
                }, 1000);
            }
        } catch (e) { console.error("Log polling error", e); }
    }, 1000);
}

function closeLiveModal() {
    document.getElementById('live-console-modal').style.display = 'none';
}

init();

