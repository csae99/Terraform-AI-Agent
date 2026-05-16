let currentProject = null;
let logInterval = null;
let currentUser = null;
let allProjects = [];
let currentCodeFiles = {};

// ─── Init ───────────────────────────────────────────────────────
async function init() {
    if (!await checkAuth()) return;
    await fetchStats();
    await fetchProjects();
}

// ─── Toast Notification System ──────────────────────────────────
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ─── Auth ───────────────────────────────────────────────────────
async function checkAuth() {
    try {
        const response = await apiFetch('/api/auth/me');
        if (!response.ok) { window.location.href = '/login'; return false; }
        currentUser = await response.json();
        updateHeaderUser();
        return true;
    } catch (e) { window.location.href = '/login'; return false; }
}

function updateHeaderUser() {
    const statusContainer = document.getElementById('connection-status');
    statusContainer.innerHTML = `
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span style="color: var(--text-secondary); font-size: 0.8rem;">Logged in as: <strong style="color: var(--accent-orange)">${currentUser.username}</strong></span>
            <a href="/api/auth/logout" class="status-badge status-failed" style="text-decoration: none; font-size: 0.7rem; padding: 0.2rem 0.5rem;">Logout</a>
            <span class="status-badge status-deployed">System Online</span>
        </div>
    `;
}

async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (res.status === 401) { window.location.href = '/login'; throw new Error("Unauthorized"); }
    return res;
}

// ─── Navigation ─────────────────────────────────────────────────
function switchPrimaryTab(tabId) {
    document.querySelectorAll('.primary-view').forEach(v => v.style.display = 'none');
    const target = document.getElementById(`view-${tabId}`);
    if (target) {
        target.style.display = 'block';
        target.style.animation = 'none';
        target.offsetHeight;
        target.style.animation = '';
    }
    document.querySelectorAll('.primary-nav-tab').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`nav-${tabId}`);
    if (btn) btn.classList.add('active');
}

// ─── Stats ──────────────────────────────────────────────────────
async function fetchStats() {
    try {
        const response = await apiFetch('/api/stats');
        const stats = await response.json();
        const container = document.getElementById('global-stats');
        container.innerHTML = `
            <div class="stat-card"><span class="stat-label">Total Projects</span><span class="stat-value">${stats.total_projects}</span></div>
            <div class="stat-card"><span class="stat-label">Live Deployments</span><span class="stat-value">${stats.active_deployments}</span></div>
            <div class="stat-card"><span class="stat-label">Monthly Cloud Spend</span><span class="stat-value">$${stats.total_monthly_cost}</span></div>
            <div class="stat-card"><span class="stat-label">Security Risks</span><span class="stat-value">${stats.total_security_issues}</span></div>
        `;
    } catch (e) { console.error("Stats fetch error", e); }
}

// ─── Projects ───────────────────────────────────────────────────
async function fetchProjects() {
    try {
        const response = await apiFetch('/api/projects');
        allProjects = await response.json();
        const badge = document.getElementById('workspace-count');
        if (badge) badge.innerText = allProjects.length;
        renderProjects(allProjects);
    } catch (e) { console.error("Project fetch error", e); }
}

function renderProjects(projects) {
    const grid = document.getElementById('projects-grid');
    if (projects.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <span class="empty-state-icon">🏗️</span>
                <h3>No projects yet</h3>
                <p>Build your first infrastructure project by switching to the Build tab and describing what you need.</p>
                <button class="btn-cta" onclick="switchPrimaryTab('build')">
                    <i class="fas fa-hammer"></i>&nbsp; Start Building
                </button>
            </div>
        `;
        return;
    }
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
}

// ─── Search & Filter ────────────────────────────────────────────
function filterProjects() {
    const query = (document.getElementById('search-input').value || '').toLowerCase();
    const status = document.getElementById('status-filter').value;
    const filtered = allProjects.filter(p => {
        const matchesSearch = !query || p.slug.toLowerCase().includes(query) || (p.prompt || '').toLowerCase().includes(query);
        const matchesStatus = status === 'all' || p.status === status;
        return matchesSearch && matchesStatus;
    });
    renderProjects(filtered);
}

// ─── Project Detail Modal ───────────────────────────────────────
async function openProject(slug) {
    try {
        const response = await apiFetch(`/api/projects/${slug}`);
        const project = await response.json();
        currentProject = project;
        document.getElementById('modal-project-slug').innerText = project.slug;
        document.getElementById('project-modal').style.display = 'flex';

        const driftBadge = document.getElementById('modal-drift-status');
        if (project.drift_status) {
            driftBadge.innerText = project.drift_status === 'in_sync' ? '✅ In Sync' : '⚠️ Drifted';
            driftBadge.className = `status-badge status-${project.drift_status === 'in_sync' ? 'deployed' : 'failed'}`;
            driftBadge.style.display = 'inline-block';
        } else { driftBadge.style.display = 'none'; }

        const mermaidContainer = document.getElementById('mermaid-container');
        if (project.mermaid_diagram) {
            mermaidContainer.innerHTML = project.mermaid_diagram;
            mermaidContainer.removeAttribute('data-processed');
        } else { mermaidContainer.innerHTML = "<p>No topology available.</p>"; }

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
        const response = await apiFetch(`/api/projects/${slug}/drift`);
        if (!response.ok) throw new Error(`Server Error (${response.status})`);
        const data = await response.json();
        showToast(data.message, data.status === 'in_sync' ? 'success' : 'error');
        openProject(slug);
        fetchProjects();
    } catch (e) {
        showToast("Drift scan failed: " + e.message, 'error');
        driftBadge.style.display = 'none';
    }
}

function closeModal() { document.getElementById('project-modal').style.display = 'none'; }

async function deleteProject() {
    if (!currentProject) return;
    const slug = currentProject.slug;
    if (!confirm(`Are you sure you want to permanently delete project "${slug}"?\n\nThis will remove all files and database records.`)) return;
    try {
        const res = await apiFetch(`/api/projects/${slug}`, { method: 'DELETE' });
        if (res.ok) {
            closeModal();
            await init();
            showToast(`Project "${slug}" deleted successfully.`, 'success');
        } else {
            const data = await res.json();
            showToast(`Failed to delete: ${data.error || 'Unknown error'}`, 'error');
        }
    } catch (e) { showToast(`Delete failed: ${e.message}`, 'error'); }
}

// ─── Modal Tabs ─────────────────────────────────────────────────
async function switchModalTab(tabId) {
    document.querySelectorAll('.modal-tab-content').forEach(c => c.style.display = 'none');
    const activeContent = document.getElementById(`modal-tab-${tabId}`);
    if (activeContent) activeContent.style.display = 'block';

    document.querySelectorAll('.modal-tab').forEach(btn => {
        btn.classList.toggle('active', btn.innerText.toLowerCase().includes(tabId.slice(0, 4)));
    });

    if (tabId === 'code' && currentProject) {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/code`);
        currentCodeFiles = await res.json();
        renderFileTabs(currentCodeFiles);
    } else if (tabId === 'visual' && currentProject?.mermaid_diagram) {
        const container = document.getElementById('mermaid-container');
        mermaid.run({ nodes: [container] });
    } else if (tabId === 'evolution' && currentProject) {
        loadSnapshots(currentProject.slug);
    } else if (tabId === 'financial' && currentProject) {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/report`);
        const data = await res.json();
        document.getElementById('modal-financial-report').innerText = data.content;
    } else if (tabId === 'logs' && currentProject) {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/logs/terraform_plan`);
        const data = await res.json();
        document.getElementById('modal-tab-logs-content').innerHTML = `<pre class="log-view">${data.content}</pre>`;
    }
}

// ─── File Tabs (Code Viewer) ────────────────────────────────────
function renderFileTabs(files) {
    const tabsContainer = document.getElementById('file-tabs');
    const codeContainer = document.getElementById('modal-tab-code-content');
    const fileNames = Object.keys(files);

    if (fileNames.length === 0) {
        tabsContainer.innerHTML = '';
        codeContainer.innerHTML = '<p class="empty-state">No Terraform files found.</p>';
        return;
    }

    tabsContainer.innerHTML = fileNames.map((f, i) =>
        `<button class="file-tab ${i === 0 ? 'active' : ''}" onclick="showFile('${f.replace(/'/g, "\\'")}', this)">${f}</button>`
    ).join('');

    showFileContent(fileNames[0]);
}

function showFile(fileName, btnEl) {
    document.querySelectorAll('.file-tab').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');
    showFileContent(fileName);
}

function showFileContent(fileName) {
    const content = currentCodeFiles[fileName] || '';
    const escaped = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    document.getElementById('modal-tab-code-content').innerHTML =
        `<pre style="background:#000; padding:1rem; border-radius:4px; font-size:0.8rem"><code>${escaped}</code></pre>`;
}

// ─── Snapshots / Evolution ──────────────────────────────────────
async function loadSnapshots(slug) {
    const res = await apiFetch(`/api/projects/${slug}/snapshots`);
    const snapshots = await res.json();
    const container = document.getElementById('snapshot-items');
    container.innerHTML = snapshots.map(s => `
        <div class="snapshot-item" onclick="viewDiff('${slug}', '${s.id}')">
            ${s.timestamp}
        </div>
    `).join('') || '<p>No snapshots yet.</p>';
}

async function viewDiff(slug, snapshotId) {
    const res = await apiFetch(`/api/projects/${slug}/diff/${snapshotId}`);
    const data = await res.json();
    const viewer = document.getElementById('diff-viewer');
    const coloredDiff = data.diff.split('\n').map(line => {
        if (line.startsWith('+')) return `<span style="color:#4ade80">${line}</span>`;
        if (line.startsWith('-')) return `<span style="color:#f87171">${line}</span>`;
        if (line.startsWith('@@')) return `<span style="color:#60a5fa">${line}</span>`;
        return line;
    }).join('\n');
    viewer.innerHTML = `<pre style="white-space:pre-wrap"><code>${coloredDiff}</code></pre>`;
}

// ─── Credential Tabs ────────────────────────────────────────────
function switchCredTab(provider) {
    document.querySelectorAll('[id^="cred-panel-"]').forEach(p => p.style.display = 'none');
    document.getElementById(`cred-panel-${provider}`).style.display = (provider === 'gcp') ? 'block' : 'grid';
    // Only toggle sibling buttons
    event.target.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
}

// ─── Refresh ────────────────────────────────────────────────────
async function refreshData() {
    const btn = event?.target;
    if (btn) { btn.innerText = "⏳ Loading..."; btn.disabled = true; }
    await init();
    if (btn) { btn.innerText = "Refresh"; btn.disabled = false; }
}

// ─── Generate Infrastructure ────────────────────────────────────
async function generateInfra() {
    const prompt = document.getElementById('infra-prompt').value;
    const budget = document.getElementById('infra-budget').value;
    const apply = document.getElementById('infra-apply').checked;
    const genBtn = document.getElementById('btn-generate');

    if (!prompt) return showToast("Please enter an infrastructure requirement.", "error");

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

    genBtn.disabled = true;
    genBtn.innerText = "🚀 Starting...";
    document.getElementById('gen-status').style.display = 'inline-block';

    document.getElementById('live-console-modal').style.display = 'flex';
    const consoleElem = document.getElementById('live-console');
    consoleElem.innerText = "🚀 Connecting to Agent Engine...\n";

    try {
        const response = await apiFetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, budget, apply, credentials, ai_config })
        });
        if (!response.ok) throw new Error(await response.text());
        showToast("Generation started! Watch the live stream.", "info");
        startPollingLogs();
    } catch (e) {
        consoleElem.innerText += "\n❌ Error: " + e.message;
        genBtn.disabled = false;
        genBtn.innerText = "Generate";
        document.getElementById('gen-status').style.display = 'none';
        showToast("Failed to start generation: " + e.message, "error");
    }
}

function startPollingLogs() {
    const genBtn = document.getElementById('btn-generate');
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

            if (data.logs && (data.logs.includes('✅ Workflow Finished') || data.logs.includes('❌ Workflow Finished'))) {
                clearInterval(logInterval);
                genBtn.disabled = false;
                genBtn.innerText = "Generate";
                document.getElementById('gen-status').style.display = 'none';

                const isSuccess = data.logs.includes('✅ Workflow Finished');
                setTimeout(() => {
                    init();
                    closeLiveModal();
                    switchPrimaryTab('workspaces');
                    showToast(
                        isSuccess ? "Infrastructure generation complete!" : "Workflow finished with errors. Check logs.",
                        isSuccess ? "success" : "error",
                        6000
                    );
                }, 1500);
            }
        } catch (e) { console.error("Log polling error", e); }
    }, 1000);
}

function closeLiveModal() {
    document.getElementById('live-console-modal').style.display = 'none';
}

// ─── Boot ───────────────────────────────────────────────────────
init();
