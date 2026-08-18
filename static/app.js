let currentProject = null;
let logInterval = null;
let currentUser = null;
let allProjects = [];
let currentCodeFiles = {};
let userOrgs = [];
let activeOrgId = null;

// ─── Init ───────────────────────────────────────────────────────
async function init() {
    if (!await checkAuth()) return;
    await fetchUserOrgs();
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

    if (tabId === 'audit') {
        loadAuditLogs();
    }
}

// ─── Stats ──────────────────────────────────────────────────────
async function fetchStats() {
    try {
        const url = activeOrgId ? `/api/stats?org_id=${activeOrgId}` : '/api/stats';
        const response = await apiFetch(url);
        const stats = await response.json();
        const container = document.getElementById('global-stats');
        container.innerHTML = `
            <div class="stat-card"><span class="stat-label">Total Projects</span><span class="stat-value">${stats.total_projects}</span></div>
            <div class="stat-card"><span class="stat-label">Live Deployments</span><span class="stat-value">${stats.active_deployments}</span></div>
            <div class="stat-card"><span class="stat-label">Monthly Cloud Spend</span><span class="stat-value">$${stats.total_monthly_cost}</span></div>
            <div class="stat-card"><span class="stat-label">Security Risks</span><span class="stat-value">${stats.total_security_issues}</span></div>
            <div class="stat-card"><span class="stat-label">Self-Healed Runs</span><span class="stat-value" style="color: var(--accent-orange);">${stats.total_healed_runs || 0}</span></div>
            <div class="stat-card"><span class="stat-label">Avg Runtime</span><span class="stat-value" style="color: var(--accent-blue);">${stats.avg_generation_time || 0}s</span></div>
        `;
    } catch (e) { console.error("Stats fetch error", e); }
}

// ─── Projects ───────────────────────────────────────────────────
async function fetchProjects() {
    try {
        const url = activeOrgId ? `/api/projects?org_id=${activeOrgId}` : '/api/projects';
        const response = await apiFetch(url);
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
    grid.innerHTML = projects.map(p => {
        const engine = p.engine || 'terraform';
        const engineBadge = engine === 'opentofu'
            ? `<span class="status-badge" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35); font-size: 0.7rem;">🧅 OpenTofu</span>`
            : `<span class="status-badge" style="background: rgba(147, 51, 234, 0.15); color: #c084fc; border: 1px solid rgba(147, 51, 234, 0.35); font-size: 0.7rem;">🟣 Terraform</span>`;
        const prBadge = p.pr_url ? `<span class="status-badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); margin-left: 0.5rem; font-size: 0.7rem;"><i class="fab fa-github"></i> PR #${p.pr_number || ''} (${p.approval_status || 'open'})</span>` : '';
        return `
        <div class="project-card" onclick="openProject('${p.slug}')">
            <div class="project-card-header">
                <div>
                    <div class="project-slug">${p.slug}</div>
                    <span class="project-provider">${p.provider}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.3rem;">
                    ${engineBadge}
                    ${prBadge}
                    <span class="status-badge status-${p.status}">${p.status}</span>
                </div>
            </div>
            <div class="project-card-body">
                <p class="project-prompt">${p.prompt || 'No description...'}</p>
                <div class="project-meta">
                    <div class="meta-item"><span class="meta-label">Cost</span><span class="meta-value">$${p.estimated_cost}</span></div>
                    <div class="meta-item"><span class="meta-label">Security</span><span class="meta-value">${p.security_issues}</span></div>
                </div>
            </div>
        </div>
    `;
    }).join('');
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

        const engineBadge = document.getElementById('modal-engine-badge');
        if (engineBadge) {
            const isTofu = (project.engine === 'opentofu');
            engineBadge.innerText = isTofu ? '🧅 OpenTofu' : '🟣 Terraform';
            engineBadge.style.background = isTofu ? 'rgba(245, 158, 11, 0.2)' : 'rgba(147, 51, 234, 0.2)';
            engineBadge.style.color = isTofu ? '#fbbf24' : '#c084fc';
            engineBadge.style.borderColor = isTofu ? 'rgba(245, 158, 11, 0.4)' : 'rgba(147, 51, 234, 0.4)';
        }

        const driftBadge = document.getElementById('modal-drift-status');
        if (project.drift_status) {
            driftBadge.innerText = project.drift_status === 'in_sync' ? '✅ In Sync' : '⚠️ Drifted';
            driftBadge.className = `status-badge status-${project.drift_status === 'in_sync' ? 'deployed' : 'failed'}`;
            driftBadge.style.display = 'inline-block';
        } else { driftBadge.style.display = 'none'; }

        const mermaidContainer = document.getElementById('mermaid-container');
        if (project.mermaid_diagram) {
            const diagramId = 'mermaid-' + Date.now();
            mermaidContainer.innerHTML = `<div class="mermaid" id="${diagramId}">${project.mermaid_diagram}</div>`;
            mermaidContainer.removeAttribute('data-processed');
            try {
                mermaid.run({ nodes: [document.getElementById(diagramId)] });
            } catch (e) {
                console.error("Mermaid render error in openProject:", e);
                mermaidContainer.innerHTML = `<pre style="background:#111;padding:1rem;border-radius:4px;color:#ccc;font-size:0.8rem;overflow-x:auto">${project.mermaid_diagram}</pre>`;
            }
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

function closeModal(modalId) {
    if (modalId) {
        const el = document.getElementById(modalId);
        if (el) el.style.display = 'none';
    } else {
        document.getElementById('project-modal').style.display = 'none';
    }
}

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
    } else if (tabId === 'gitops' && currentProject) {
        loadGitOpsDetails(currentProject.slug);
    } else if (tabId === 'visual' && currentProject?.mermaid_diagram) {
        const container = document.getElementById('mermaid-container');
        const diagramId = 'mermaid-tab-' + Date.now();
        container.innerHTML = `<div class="mermaid" id="${diagramId}">${currentProject.mermaid_diagram}</div>`;
        container.removeAttribute('data-processed');
        try {
            mermaid.run({ nodes: [document.getElementById(diagramId)] });
        } catch (e) {
            console.error("Mermaid run error:", e);
            container.innerHTML = `<pre style="background:#111;padding:1rem;border-radius:4px;color:#ccc;font-size:0.8rem;overflow-x:auto">${currentProject.mermaid_diagram}</pre>`;
        }
    } else if (tabId === 'evolution' && currentProject) {
        loadSnapshots(currentProject.slug);
    } else if (tabId === 'financial' && currentProject) {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/report`);
        const data = await res.json();
        
        let html = "";
        if (data.content) {
            // Parse markdown using marked
            html = typeof marked !== 'undefined' ? marked.parse(data.content) : `<pre>${data.content}</pre>`;
            
            // Regex to match "STATUS: OVER BUDGET" or "STATUS: WITHIN BUDGET" inside strong/heading tags
            // and wrap in beautiful CSS class-styled card elements
            html = html.replace(
                /(?:<h3>)?(⚠️|✅|🔴|🟢|🛑)?\s*<strong>STATUS:\s*(OVER BUDGET|WITHIN BUDGET)<\/strong>(?:<\/h3>)?/gi,
                (match, icon, status) => {
                    const isOver = status.toUpperCase().includes("OVER");
                    const finalIcon = icon || (isOver ? "⚠️" : "✅");
                    const alertClass = isOver ? "finops-danger" : "finops-success";
                    const desc = isOver 
                        ? "Projected monthly costs exceed the allocated budget limit." 
                        : "Projected monthly costs are compliant with the allocated budget.";
                    return `
                        <div class="finops-alert ${alertClass}">
                            <span class="alert-icon">${finalIcon}</span>
                            <div>
                                <div class="alert-title">STATUS: ${status.toUpperCase()}</div>
                                <p class="alert-desc">${desc}</p>
                            </div>
                        </div>
                    `;
                }
            );
        } else {
            html = "<p class='empty-state'>No FinOps report available.</p>";
        }
        
        document.getElementById('modal-financial-report').innerHTML = html;
    } else if (tabId === 'logs' && currentProject) {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/logs/terraform_plan`);
        const data = await res.json();
        document.getElementById('modal-tab-logs-content').innerHTML = `<pre class="log-view">${data.content}</pre>`;
    } else if (tabId === 'diagnostics' && currentProject) {
        // Set rounds and duration
        const rounds = currentProject.healing_rounds_taken || 1;
        const duration = currentProject.run_duration || 0;
        
        document.getElementById('diag-rounds').innerText = rounds;
        document.getElementById('diag-duration').innerText = duration > 0 ? `${duration}s` : 'N/A';
        
        // Healing Status Badge
        const statusBadge = document.getElementById('diag-status');
        if (currentProject.status === 'failed') {
            statusBadge.innerText = '❌ Failed';
            statusBadge.className = 'status-badge status-failed';
        } else if (rounds > 1) {
            statusBadge.innerText = '⚡ Self-Healed';
            statusBadge.className = 'status-badge status-remediated';
        } else {
            statusBadge.innerText = '✅ Clean Run';
            statusBadge.className = 'status-badge status-deployed';
        }
        
        // Render Remediation/Matched Patterns
        const remediationContainer = document.getElementById('diagnostics-remediation-history');
        const patterns = currentProject.patterns_applied || [];
        const errors = currentProject.errors_encountered || [];
        
        if (patterns.length === 0 && errors.length === 0) {
            remediationContainer.innerHTML = '<p class="text-muted">No self-healing events occurred during this execution (Clean single-pass run).</p>';
        } else {
            let html = '<div class="remediation-timeline">';
            
            // Render errors encountered
            if (errors.length > 0) {
                html += '<h4>⚠️ Errors Encountered:</h4><ul class="error-log-list">';
                errors.forEach((err, idx) => {
                    const firstLine = err.split('\n')[0];
                    html += `
                        <li>
                            <details class="error-details">
                                <summary><strong>Round ${idx + 1}:</strong> <code>${firstLine}</code></summary>
                                <pre class="raw-error-pre">${err}</pre>
                            </details>
                        </li>
                    `;
                });
                html += '</ul>';
            }
            
            // Render patterns matched
            if (patterns.length > 0) {
                html += '<h4>📚 Pattern Memory Fixes Applied:</h4><div class="matched-patterns-grid">';
                patterns.forEach(pat => {
                    html += `
                        <div class="matched-pattern-card">
                            <div class="pat-header">
                                <span class="pat-badge badge-${(pat.severity || 'medium').toLowerCase()}">${pat.severity || 'MEDIUM'}</span>
                                <span class="pat-category">Category: <strong>${pat.category || 'general'}</strong></span>
                            </div>
                            <div class="pat-substring">Matched signature: <code>"${pat.error_substring}"</code></div>
                            <div class="pat-desc">${pat.description || ''}</div>
                            <div class="pat-fix">🔧 <strong>Advice:</strong> ${pat.fix || ''}</div>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            // Render dynamic reflection advice if triggered
            if (currentProject.reflection_advice) {
                const ref = currentProject.reflection_advice;
                html += `
                    <div class="reflection-advice-container" style="margin-top: 1.5rem; background: rgba(139, 92, 246, 0.05); border: 1px dashed rgba(139, 92, 246, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
                        <h4 style="color: #a78bfa; margin-top: 0;"><i class="fas fa-brain"></i> Dynamic LLM Reflection Diagnosis</h4>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem;"><strong>Analysis of failure:</strong> ${ref.cause || ''}</p>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem;"><strong>Suggested Fix:</strong> ${ref.fix_advice || ''}</p>
                        <p style="font-size: 0.85rem; font-weight: bold; margin-bottom: 0.25rem; color: #a78bfa;">Corrected Code Snippet:</p>
                        <pre style="background: #09090b !important; padding: 0.75rem; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; overflow-x: auto; border: 1px solid rgba(139, 92, 246, 0.15);"><code style="color: #e9d5ff;">${(ref.corrected_snippet || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></pre>
                    </div>
                `;
            }
            
            html += '</div>';
            remediationContainer.innerHTML = html;
        }

        // Render Decision Trace
        const traceContainer = document.getElementById('diagnostics-decision-trace');
        const trace = currentProject.decision_trace || [];
        if (trace.length === 0) {
            traceContainer.innerHTML = '<p class="text-muted">No trace records available.</p>';
        } else {
            let traceHtml = '<div class="decision-trace-flow">';
            trace.forEach((step, idx) => {
                let badgeClass = 'badge-default';
                let stepLabel = step.replace(/_/g, ' ').toUpperCase();
                let icon = '⚙️';
                
                if (step.includes('started')) {
                    badgeClass = 'badge-started';
                    icon = '🚀';
                } else if (step.includes('failed')) {
                    badgeClass = 'badge-failed';
                    icon = '❌';
                } else if (step.includes('succeeded') || step.includes('success')) {
                    badgeClass = 'badge-success';
                    icon = '✅';
                } else if (step.includes('reflection')) {
                    badgeClass = 'badge-reflection';
                    icon = '🧠';
                } else if (step.includes('search')) {
                    badgeClass = 'badge-search';
                    icon = '🔍';
                } else if (step.includes('pattern')) {
                    badgeClass = 'badge-pattern';
                    icon = '📚';
                } else if (step.includes('apply') || step.includes('applied')) {
                    badgeClass = 'badge-apply';
                    icon = '🔧';
                }
                
                traceHtml += `
                    <div class="trace-step-badge ${badgeClass}">
                        <span>${icon}</span>
                        <span>${stepLabel}</span>
                    </div>
                `;
                if (idx < trace.length - 1) {
                    traceHtml += `
                        <span class="trace-arrow"><i class="fas fa-arrow-right"></i></span>
                    `;
                }
            });
            traceHtml += '</div>';
            traceContainer.innerHTML = traceHtml;
        }
        
        // Render QA Report
        const qaContainer = document.getElementById('diagnostics-qa-report');
        if (currentProject.qa_report) {
            qaContainer.innerHTML = typeof marked !== 'undefined' ? marked.parse(currentProject.qa_report) : `<pre>${currentProject.qa_report}</pre>`;
        } else {
            qaContainer.innerHTML = '<p class="text-muted">No QA behavior verification report available. Run was not deployed or verification skipped.</p>';
        }
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

// ─── GitOps Section Toggle ──────────────────────────────────────
function toggleGitOpsSection() {
    const isGitOps = document.getElementById('infra-gitops').checked;
    const details = document.getElementById('gitops-section');
    if (details) {
        details.open = isGitOps;
    }
}

// ─── Generate Infrastructure ────────────────────────────────────
async function generateInfra() {
    const prompt = document.getElementById('infra-prompt').value;
    const budget = document.getElementById('infra-budget').value;
    const apply = document.getElementById('infra-apply').checked;
    const new_project = document.getElementById('infra-new-project').checked;
    const gitops = document.getElementById('infra-gitops').checked;
    const git_repo = document.getElementById('gitops-repo').value.trim();
    const target_branch = document.getElementById('gitops-branch').value.trim() || 'main';
    const git_token = document.getElementById('gitops-token').value.trim();
    const engine = document.getElementById('infra-engine')?.value || 'terraform';
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
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
        
        const payload = { prompt, budget, apply, new_project, credentials, ai_config, gitops, git_repo, target_branch, git_token, engine };
        if (activeOrgId) payload.org_id = activeOrgId;

        const response = await apiFetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errData.detail || `Server error: ${response.status}`);
        }
        showToast("Generation started! Watch the live stream.", "info");
        startPollingLogs();
    } catch (e) {
        let errorMsg = e.message;
        if (e.name === 'AbortError') {
            errorMsg = "Request timed out. Is the server running?";
        } else if (errorMsg === 'Failed to fetch') {
            errorMsg = "Could not connect to server. Check if the dashboard is running on port 5000.";
        }
        consoleElem.innerText += "\n❌ Error: " + errorMsg;
        genBtn.disabled = false;
        genBtn.innerText = "Generate";
        document.getElementById('gen-status').style.display = 'none';
        showToast("Failed to start generation: " + errorMsg, "error");
    }
}

let eventSource = null;

function startPollingLogs() {
    const genBtn = document.getElementById('btn-generate');
    const consoleElem = document.getElementById('live-console');
    
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource('/api/logs/active');
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.logs && data.logs !== "No active run.") {
                consoleElem.innerText += data.logs;
                consoleElem.scrollTop = consoleElem.scrollHeight;
                
                const fullText = consoleElem.innerText;
                if (fullText.includes('✅ Workflow Finished') || fullText.includes('❌ Workflow Finished') || fullText.includes('❌ Error')) {
                    eventSource.close();
                    genBtn.disabled = false;
                    genBtn.innerText = "Generate";
                    document.getElementById('gen-status').style.display = 'none';

                    const isSuccess = fullText.includes('✅ Workflow Finished');
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
            }
        } catch (e) {
            console.error("SSE parsing error", e);
        }
    };
    
    eventSource.onerror = function() {
        console.error("SSE connection error");
        eventSource.close();
    };
}

function closeLiveModal() {
    document.getElementById('live-console-modal').style.display = 'none';
}

// ─── Organization & Workspace Context ───────────────────────────
async function fetchUserOrgs() {
    try {
        const response = await apiFetch('/api/orgs');
        userOrgs = await response.json();
        populateWorkspaceSelector();
    } catch (e) { console.error('Failed to fetch user orgs', e); }
}

function populateWorkspaceSelector() {
    const select = document.getElementById('workspace-context-select');
    if (!select) return;
    // Preserve current selection
    const prevVal = select.value;
    select.innerHTML = '<option value="personal">👤 Personal Workspace</option>';
    userOrgs.forEach(org => {
        const roleLabel = org.role ? ` (${org.role.toUpperCase()})` : '';
        select.innerHTML += `<option value="${org.id}">🏢 ${org.name}${roleLabel}</option>`;
    });
    // Restore selection if still valid
    if (prevVal && select.querySelector(`option[value="${prevVal}"]`)) {
        select.value = prevVal;
    }
    // Show/hide team button based on current context
    const teamBtn = document.getElementById('btn-manage-team');
    if (teamBtn) teamBtn.style.display = activeOrgId ? 'inline-flex' : 'none';
}

function handleWorkspaceContextChange() {
    const select = document.getElementById('workspace-context-select');
    const val = select.value;
    if (val === 'personal') {
        activeOrgId = null;
    } else {
        activeOrgId = parseInt(val);
    }
    const teamBtn = document.getElementById('btn-manage-team');
    if (teamBtn) teamBtn.style.display = activeOrgId ? 'inline-flex' : 'none';
    fetchStats();
    fetchProjects();
}

// ─── Create Organization Modal ──────────────────────────────────
function openCreateOrgModal() {
    document.getElementById('new-org-name').value = '';
    document.getElementById('modal-create-org').style.display = 'flex';
}

async function submitCreateOrg() {
    const name = document.getElementById('new-org-name').value.trim();
    if (!name) return showToast('Organization name is required.', 'error');
    try {
        const res = await apiFetch('/api/orgs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to create organization');
        }
        const org = await res.json();
        showToast(`Organization "${org.name}" created!`, 'success');
        closeModal('modal-create-org');
        await fetchUserOrgs();
        // Switch to the new org context
        activeOrgId = org.id;
        const select = document.getElementById('workspace-context-select');
        if (select) select.value = String(org.id);
        handleWorkspaceContextChange();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ─── Manage Team Members Modal ──────────────────────────────────
function openManageTeamModal() {
    if (!activeOrgId) return showToast('Select an organization first.', 'error');
    const org = userOrgs.find(o => o.id === activeOrgId);
    const titleEl = document.getElementById('org-modal-title-name');
    if (titleEl && org) titleEl.innerText = org.name;
    document.getElementById('invite-username').value = '';
    document.getElementById('modal-manage-team').style.display = 'flex';
    fetchOrgMembers();
}

async function fetchOrgMembers() {
    if (!activeOrgId) return;
    try {
        const res = await apiFetch(`/api/orgs/${activeOrgId}/members`);
        const members = await res.json();
        const tbody = document.getElementById('org-members-tbody');
        const currentOrg = userOrgs.find(o => o.id === activeOrgId);
        const isAdmin = currentOrg && ['owner', 'admin'].includes(currentOrg.role);

        if (!members.length) {
            tbody.innerHTML = '<tr><td colspan="4" style="padding:1rem;color:#888;text-align:center;">No members yet.</td></tr>';
            return;
        }
        tbody.innerHTML = members.map(m => {
            const roleColor = m.role === 'owner' ? '#f59e0b' : m.role === 'admin' ? '#6366f1' : m.role === 'viewer' ? '#94a3b8' : '#22c55e';
            const roleSelect = isAdmin && m.role !== 'owner'
                ? `<select onchange="updateMemberRole(${m.user_id}, this.value)" style="background:#0f172a;color:#fff;border:1px solid #334155;border-radius:4px;padding:2px 6px;font-size:0.8rem;">
                     <option value="admin" ${m.role==='admin'?'selected':''}>Admin</option>
                     <option value="member" ${m.role==='member'?'selected':''}>Member</option>
                     <option value="viewer" ${m.role==='viewer'?'selected':''}>Viewer</option>
                   </select>`
                : `<span style="color:${roleColor};font-weight:600;text-transform:uppercase;font-size:0.8rem;">${m.role}</span>`;

            const removeBtn = isAdmin && m.role !== 'owner'
                ? `<button onclick="removeOrgMember(${m.user_id})" style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);color:#f87171;border-radius:4px;padding:3px 8px;font-size:0.75rem;cursor:pointer;">Remove</button>`
                : '';

            return `<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:0.5rem;">${m.username}</td>
                <td style="padding:0.5rem;color:#888;">${m.email || '—'}</td>
                <td style="padding:0.5rem;">${roleSelect}</td>
                <td style="padding:0.5rem;text-align:right;">${removeBtn}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Failed to fetch org members', e);
        showToast('Failed to load team members.', 'error');
    }
}

async function submitAddMember() {
    if (!activeOrgId) return;
    const username = document.getElementById('invite-username').value.trim();
    const role = document.getElementById('invite-role').value;
    if (!username) return showToast('Enter a username to invite.', 'error');
    try {
        const res = await apiFetch(`/api/orgs/${activeOrgId}/members`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, role })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to add member');
        }
        showToast(`Added ${username} as ${role}`, 'success');
        document.getElementById('invite-username').value = '';
        fetchOrgMembers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function updateMemberRole(targetUserId, newRole) {
    if (!activeOrgId) return;
    try {
        const res = await apiFetch(`/api/orgs/${activeOrgId}/members/${targetUserId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: newRole })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to update role');
        }
        showToast('Role updated successfully.', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function removeOrgMember(targetUserId) {
    if (!activeOrgId) return;
    if (!confirm('Are you sure you want to remove this member from the organization?')) return;
    try {
        const res = await apiFetch(`/api/orgs/${activeOrgId}/members/${targetUserId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to remove member');
        }
        showToast('Member removed.', 'success');
        fetchOrgMembers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ─── GitOps & Approval Handlers ─────────────────────────────────
async function loadGitOpsDetails(slug) {
    try {
        const res = await apiFetch(`/api/projects/${slug}/gitops`);
        const data = await res.json();
        
        const badge = document.getElementById('gitops-approval-badge');
        const branchEl = document.getElementById('gitops-branch-name');
        const prLinkEl = document.getElementById('gitops-pr-link');
        const approverEl = document.getElementById('gitops-approved-by');
        const approveBtn = document.getElementById('btn-approve-pr');
        const mergeBtn = document.getElementById('btn-merge-deploy');

        branchEl.innerText = data.git_branch || 'Not configured';
        approverEl.innerText = data.approved_by || 'None (Pending Review)';

        if (data.pr_url) {
            prLinkEl.innerHTML = `<a href="${data.pr_url}" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 600;">PR #${data.pr_number || 'View'} ↗</a>`;
        } else {
            prLinkEl.innerText = 'No Pull Request';
        }

        const appStatus = data.approval_status || 'none';
        const prStatus = data.pr_status || 'none';

        if (appStatus === 'approved') {
            badge.innerText = '✅ Approved';
            badge.className = 'status-badge status-deployed';
            if (approveBtn) approveBtn.disabled = true;
            if (mergeBtn) mergeBtn.disabled = (prStatus === 'merged');
        } else if (appStatus === 'pending') {
            badge.innerText = '⏳ Pending Approval';
            badge.className = 'status-badge status-generating';
            if (approveBtn) approveBtn.disabled = false;
            if (mergeBtn) mergeBtn.disabled = true;
        } else {
            badge.innerText = prStatus === 'merged' ? '🚀 Merged' : 'None';
            badge.className = 'status-badge';
            if (approveBtn) approveBtn.disabled = true;
            if (mergeBtn) mergeBtn.disabled = true;
        }
    } catch (e) {
        console.error("Failed to load GitOps details", e);
    }
}

async function approveProjectPR() {
    if (!currentProject) return;
    try {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/approve`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Approval failed');
        showToast(data.message || 'Pull Request approved!', 'success');
        await loadGitOpsDetails(currentProject.slug);
        await fetchProjects();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function mergeAndDeployProject() {
    if (!currentProject) return;
    if (!confirm(`Merge PR and trigger live cloud deployment for "${currentProject.slug}"?`)) return;
    try {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/merge-deploy`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Merge failed');
        showToast(data.message || 'Merged & Deployed!', 'success');
        await loadGitOpsDetails(currentProject.slug);
        await fetchProjects();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadAuditLogs() {
    try {
        const url = activeOrgId ? `/api/audit-logs?org_id=${activeOrgId}` : '/api/audit-logs';
        const res = await apiFetch(url);
        const logs = await res.json();
        const tbody = document.getElementById('audit-logs-tbody');
        if (!tbody) return;
        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 2rem; color: #888;">No audit trail events recorded yet.</td></tr>`;
            return;
        }
        tbody.innerHTML = logs.map(l => {
            const actionColors = {
                'gitops_pr_created': '#60a5fa',
                'gitops_pr_approved': '#4ade80',
                'gitops_pr_merged_and_deployed': '#a78bfa',
                'org_created': '#f59e0b',
                'member_added': '#38bdf8'
            };
            const col = actionColors[l.action] || '#ccc';
            return `<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 0.6rem; color: #888; font-family: monospace; font-size: 0.8rem;">${l.created_at}</td>
                <td style="padding: 0.6rem; font-weight: 600; color: #fff;">${l.username}</td>
                <td style="padding: 0.6rem;"><span style="color: ${col}; font-weight: 600; text-transform: uppercase; font-size: 0.75rem;">${l.action}</span></td>
                <td style="padding: 0.6rem; font-family: monospace; color: #94a3b8;">${l.resource_slug || '—'}</td>
                <td style="padding: 0.6rem; color: #cbd5e1; font-size: 0.85rem;">${l.details || '—'}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error("Failed to load audit logs", e);
        showToast("Failed to load audit logs", "error");
    }
}

// ─── Boot ───────────────────────────────────────────────────────
init();

