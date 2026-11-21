let currentProject = null;
let logInterval = null;
let currentUser = null;
let allProjects = [];
let currentCodeFiles = {};
let userOrgs = [];
let activeOrgId = null;
let dbPricingCatalog = [];

// ─── Cloud Pricing Catalog Loader (Database-Backed) ─────────────
async function loadPricingCatalog() {
    try {
        const cached = sessionStorage.getItem('omniinfra_pricing_catalog');
        if (cached) {
            dbPricingCatalog = JSON.parse(cached);
        } else {
            const res = await fetch('/api/pricing/catalog');
            if (res.ok) {
                const data = await res.json();
                dbPricingCatalog = data.items || [];
                sessionStorage.setItem('omniinfra_pricing_catalog', JSON.stringify(dbPricingCatalog));
            }
        }
    } catch (e) {
        console.warn('Failed to load pricing catalog:', e);
    }
    // Re-evaluate estimator if prompt already has content
    if (document.getElementById('infra-prompt')?.value?.trim()) {
        updateCostEstimator();
    }
}

// ─── AI Model Engine Catalog Loader (Dynamic) ────────────────────
async function loadAIModels() {
    const select = document.getElementById('infra-model');
    if (!select) return;

    try {
        const res = await fetch('/api/ai-models');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const models = data.models || [];
        if (models.length > 0) {
            select.innerHTML = '';
            models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.model_id;
                const badge = m.badge ? `${m.badge} ` : '';
                const desc = m.description ? ` (${m.description})` : '';
                opt.textContent = `${badge}${m.display_name}${desc}`;
                if (m.is_default) {
                    opt.selected = true;
                }
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Failed to dynamically load AI models:', e);
    }
}

// ─── Init ───────────────────────────────────────────────────────
async function init() {
    if (!await checkAuth()) return;
    if (typeof onCloudProviderChange === 'function') onCloudProviderChange();

    // Attach real-time cost estimator listeners
    const promptEl = document.getElementById('infra-prompt');
    if (promptEl && !promptEl.dataset.hasEstimator) {
        promptEl.dataset.hasEstimator = "true";
        let debounceTimer;
        promptEl.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(updateCostEstimator, 120);
        });
    }
    ['infra-budget', 'infra-env', 'infra-cloud'].forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.dataset.hasEstimator) {
            el.dataset.hasEstimator = "true";
            el.addEventListener('change', updateCostEstimator);
            el.addEventListener('input', updateCostEstimator);
        }
    });

    await fetchUserOrgs();
    await fetchStats();
    await fetchProjects();
    loadPricingCatalog();
    loadAIModels();
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
    const adminBadge = (currentUser && currentUser.is_superuser) ? `
        <a href="/admin" class="btn-sm" style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(139, 92, 246, 0.2)); border: 1px solid rgba(239, 68, 68, 0.5); color: #fca5a5; padding: 0.25rem 0.6rem; border-radius: 4px; text-decoration: none; font-size: 0.75rem; font-weight: 700; display: inline-flex; align-items: center; gap: 0.3rem;">
            <i class="fas fa-shield-alt"></i> Admin Console
        </a>
    ` : '';
    statusContainer.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            ${adminBadge}
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
    } else if (tabId === 'analytics') {
        loadExecutiveAnalytics();
    } else if (tabId === 'billing') {
        loadBillingInfo();
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
            <div class="stat-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="stat-label">Total Projects</span>
                    <i class="fas fa-cubes" style="color: #818cf8; font-size: 0.85rem; opacity: 0.8;"></i>
                </div>
                <span class="stat-value">${stats.total_projects}</span>
            </div>
            <div class="stat-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="stat-label">Live Deployments</span>
                    <i class="fas fa-cloud" style="color: #34d399; font-size: 0.85rem; opacity: 0.8;"></i>
                </div>
                <span class="stat-value">${stats.active_deployments}</span>
            </div>
            <div class="stat-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="stat-label">Monthly Cloud Spend</span>
                    <i class="fas fa-wallet" style="color: #38bdf8; font-size: 0.85rem; opacity: 0.8;"></i>
                </div>
                <span class="stat-value">$${stats.total_monthly_cost}</span>
            </div>
            <div class="stat-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="stat-label">Security Risks</span>
                    <i class="fas fa-shield-virus" style="color: #f87171; font-size: 0.85rem; opacity: 0.8;"></i>
                </div>
                <span class="stat-value">${stats.total_security_issues}</span>
            </div>
            <div class="stat-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="stat-label">Self-Healed Runs</span>
                    <i class="fas fa-wand-magic-sparkles" style="color: #fbbf24; font-size: 0.85rem; opacity: 0.8;"></i>
                </div>
                <span class="stat-value" style="color: var(--accent-orange);">${stats.total_healed_runs || 0}</span>
            </div>
            <div class="stat-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="stat-label">Avg Runtime</span>
                    <i class="fas fa-stopwatch" style="color: #a78bfa; font-size: 0.85rem; opacity: 0.8;"></i>
                </div>
                <span class="stat-value" style="color: var(--accent-blue);">${stats.avg_generation_time || 0}s</span>
            </div>
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

// ─── Search, Filter & Sort ──────────────────────────────────────
function filterProjects() {
    const query = (document.getElementById('search-input')?.value || '').toLowerCase();
    const status = document.getElementById('status-filter')?.value || 'all';
    const engine = document.getElementById('engine-filter')?.value || 'all';
    const sortBy = document.getElementById('sort-filter')?.value || 'latest';

    let filtered = allProjects.filter(p => {
        const matchesSearch = !query || p.slug.toLowerCase().includes(query) || (p.prompt || '').toLowerCase().includes(query);
        const matchesStatus = status === 'all' || p.status === status;
        const pEngine = p.engine || 'terraform';
        const matchesEngine = engine === 'all' || pEngine === engine;
        return matchesSearch && matchesStatus && matchesEngine;
    });

    if (sortBy === 'cost-desc') {
        filtered.sort((a, b) => (parseFloat(b.estimated_cost) || 0) - (parseFloat(a.estimated_cost) || 0));
    } else if (sortBy === 'cost-asc') {
        filtered.sort((a, b) => (parseFloat(a.estimated_cost) || 0) - (parseFloat(b.estimated_cost) || 0));
    } else if (sortBy === 'name') {
        filtered.sort((a, b) => a.slug.localeCompare(b.slug));
    }

    renderProjects(filtered);
}

// ─── Project Detail Modal ───────────────────────────────────────
async function openProject(slug) {
    try {
        isCodeEditMode = false;
        const toggleBtn = document.getElementById('btn-toggle-edit');
        const label = document.getElementById('btn-toggle-edit-label');
        const saveBtn = document.getElementById('btn-save-replan');
        const discardBtn = document.getElementById('btn-discard-edit');
        const statusCard = document.getElementById('code-replan-status-card');
        if (label) label.innerText = "Edit Code";
        if (toggleBtn) {
            toggleBtn.style.background = "rgba(99, 102, 241, 0.15)";
            toggleBtn.style.borderColor = "rgba(99, 102, 241, 0.45)";
            toggleBtn.style.color = "#a5b4fc";
        }
        if (saveBtn) saveBtn.style.display = "none";
        if (discardBtn) discardBtn.style.display = "none";
        if (statusCard) statusCard.style.display = "none";

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
        const onclickAttr = btn.getAttribute('onclick') || '';
        btn.classList.toggle('active', onclickAttr.includes(`'${tabId}'`) || btn.innerText.toLowerCase().includes(tabId));
    });

    if (tabId === 'code' && currentProject) {
        const res = await apiFetch(`/api/projects/${currentProject.slug}/code`);
        currentCodeFiles = await res.json();
        renderFileTabs(currentCodeFiles);
    } else if (tabId === 'adr' && currentProject) {
        renderAdrTimeline(currentProject);
    } else if (tabId === 'gitops') {
        const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
        if (slug) loadGitOpsDetails(slug);
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
        loadSnapshots(currentProject.slug, true);
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
    } else if (tabId === 'logs') {
        const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
        if (slug) {
            loadDeploymentTab(slug);
            loadStatePosture(slug);
        }
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
            let traceHtml = '<div class="decision-trace-flow" style="display: flex; flex-direction: column; gap: 0.75rem;">';
            trace.forEach((step, idx) => {
                if (typeof step === 'object' && step !== null) {
                    const agent = step.agent || 'System';
                    const stage = step.stage || 'Pipeline';
                    const action = step.action || step.decision || 'Action';
                    const reason = step.reason || '';
                    const time = step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : '';

                    const agentColors = {
                        'ArchitectAgent': '#818cf8',
                        'DeveloperAgent': '#38bdf8',
                        'SecurityReviewer': '#f87171',
                        'FinOpsSpecialist': '#34d399',
                        'TestingAgent': '#fbbf24',
                        'GitOpsCoordinator': '#c084fc',
                        'SelfHealingOrchestrator': '#f472b6',
                        'System': '#94a3b8'
                    };
                    const color = agentColors[agent] || '#a5b4fc';

                    traceHtml += `
                        <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-left: 4px solid ${color}; border-radius: var(--radius-sm); padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                            <div style="flex: 1;">
                                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                                    <span style="background: rgba(255,255,255,0.08); color: ${color}; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">${agent}</span>
                                    <span style="font-size: 0.75rem; color: #888;">[${stage}]</span>
                                    <strong style="color: #fff; font-size: 0.9rem;">${action}</strong>
                                </div>
                                ${reason ? `<p style="margin: 0; font-size: 0.8rem; color: #cbd5e1;">${reason}</p>` : ''}
                            </div>
                            ${time ? `<span style="font-size: 0.75rem; color: #64748b; font-family: monospace; white-space: nowrap;">${time}</span>` : ''}
                        </div>
                    `;
                } else {
                    let badgeClass = 'badge-default';
                    let stepLabel = String(step).replace(/_/g, ' ').toUpperCase();
                    let icon = '⚙️';
                    if (String(step).includes('started')) { badgeClass = 'badge-started'; icon = '🚀'; }
                    else if (String(step).includes('failed')) { badgeClass = 'badge-failed'; icon = '❌'; }
                    else if (String(step).includes('succeeded') || String(step).includes('success')) { badgeClass = 'badge-success'; icon = '✅'; }
                    else if (String(step).includes('reflection')) { badgeClass = 'badge-reflection'; icon = '🧠'; }
                    else if (String(step).includes('search')) { badgeClass = 'badge-search'; icon = '🔍'; }
                    else if (String(step).includes('pattern')) { badgeClass = 'badge-pattern'; icon = '📚'; }
                    else if (String(step).includes('apply') || String(step).includes('applied')) { badgeClass = 'badge-apply'; icon = '🔧'; }

                    traceHtml += `
                        <div class="trace-step-badge ${badgeClass}" style="display: inline-flex; margin-right: 0.5rem;">
                            <span>${icon}</span>
                            <span>${stepLabel}</span>
                        </div>
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

        // Render Architectural Decision Records (ADRs)
        renderAdrTimeline(currentProject);
    }
}

// ─── Architectural Decision Records (ADR) Timeline ─────────────
function renderAdrTimeline(project) {
    const container = document.getElementById('modal-adr-timeline');
    const badge = document.getElementById('adr-count-badge');
    if (!container) return;

    const trace = project?.decision_trace || [];
    const adrs = trace.filter(d => typeof d === 'object' && d !== null && (d.is_adr || d.rationale || d.reason || d.action));

    if (badge) badge.innerText = `${adrs.length} Decision${adrs.length === 1 ? '' : 's'}`;

    if (adrs.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 2.5rem 1rem; color: #94a3b8; background: rgba(255,255,255,0.02); border-radius: var(--radius-sm); border: 1px dashed var(--border-color);">
                <div style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.6;">🧠</div>
                <h4 style="margin: 0 0 0.25rem 0; color: #cbd5e1;">No Architectural Decision Records Recorded</h4>
                <p style="margin: 0; font-size: 0.85rem;">Workload was executed under default fast-track generation without branching decision overrides.</p>
            </div>
        `;
        return;
    }

    const agentColors = {
        'TerraformArchitect': '#818cf8',
        'ArchitectAgent': '#818cf8',
        'DeveloperAgent': '#38bdf8',
        'SecurityReviewer': '#f87171',
        'FinOpsSpecialist': '#34d399',
        'ConsensusReviewer': '#a855f7',
        'TestingAgent': '#fbbf24',
        'GitOpsCoordinator': '#c084fc',
        'System': '#94a3b8'
    };

    let html = '';
    adrs.forEach((adr, idx) => {
        const agent = adr.agent || 'PlatformAgent';
        const color = agentColors[agent] || '#818cf8';
        const stage = adr.stage || 'Architecture';
        const title = adr.title || adr.action || adr.decision || `Architectural Decision #${idx + 1}`;
        const rationale = adr.rationale || adr.reason || 'Standard operational best practice.';
        const decisionText = adr.decision || adr.action || '';
        const alternatives = adr.alternatives_considered || '';
        const tradeoffs = adr.tradeoffs || '';
        const timestamp = adr.timestamp ? new Date(adr.timestamp).toLocaleTimeString() : '';

        html += `
            <div style="background: rgba(255,255,255,0.025); border: 1px solid var(--border-color); border-left: 4px solid ${color}; border-radius: var(--radius-sm); padding: 1.1rem 1.25rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="background: rgba(255,255,255,0.08); color: ${color}; font-size: 0.72rem; font-weight: 700; padding: 3px 8px; border-radius: 4px; text-transform: uppercase;">${agent}</span>
                        <span style="font-size: 0.75rem; color: #94a3b8;">[${stage}]</span>
                    </div>
                    ${timestamp ? `<span style="font-size: 0.75rem; color: #64748b; font-family: monospace;">${timestamp}</span>` : ''}
                </div>
                <h4 style="margin: 0 0 0.5rem 0; color: #fff; font-size: 0.98rem; font-weight: 600;">${title}</h4>
                ${decisionText && decisionText !== title ? `<p style="margin: 0 0 0.5rem 0; font-size: 0.86rem; color: #cbd5e1;"><strong>Decision:</strong> ${decisionText}</p>` : ''}
                <div style="background: rgba(99, 102, 241, 0.05); border-left: 3px solid #6366f1; padding: 0.5rem 0.75rem; border-radius: 0 4px 4px 0; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.84rem; color: #e2e8f0; line-height: 1.4;">
                        <strong style="color: #a5b4fc;">💡 Why Decided:</strong> ${rationale}
                    </div>
                </div>
                ${alternatives && alternatives !== 'Standard default configuration' ? `
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.35rem;">
                        <strong style="color: #cbd5e1;">🔄 Alternatives Considered:</strong> ${alternatives}
                    </div>
                ` : ''}
                ${tradeoffs ? `
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem;">
                        <strong style="color: #cbd5e1;">⚖️ Trade-offs:</strong> ${tradeoffs}
                    </div>
                ` : ''}
            </div>
        `;
    });

    container.innerHTML = html;
}

// ─── File Tabs (Code Viewer) ────────────────────────────────────
let currentActiveFileName = '';

function renderFileTabs(files) {
    const tabsContainer = document.getElementById('file-tabs');
    const codeContainer = document.getElementById('modal-tab-code-content');
    const fileNames = Object.keys(files);

    if (fileNames.length === 0) {
        tabsContainer.innerHTML = '';
        currentActiveFileName = '';
        codeContainer.innerHTML = '<p class="empty-state">No Terraform files found.</p>';
        return;
    }

    tabsContainer.innerHTML = fileNames.map((f, i) =>
        `<button class="file-tab ${i === 0 ? 'active' : ''}" onclick="showFile('${f.replace(/'/g, "\\'")}', this)">${f}</button>`
    ).join('');

    showFileContent(fileNames[0]);
}

let isCodeEditMode = false;

function showFile(fileName, btnEl) {
    document.querySelectorAll('.file-tab').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');
    showFileContent(fileName);
}

function showFileContent(fileName) {
    currentActiveFileName = fileName;
    renderActiveCodeView();
}

function renderActiveCodeView() {
    const codeContainer = document.getElementById('modal-tab-code-content');
    if (!codeContainer) return;
    const content = currentCodeFiles[currentActiveFileName] || '';

    if (!isCodeEditMode) {
        const escaped = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        codeContainer.innerHTML =
            `<pre style="background:#000; padding:1rem; border-radius:4px; font-size:0.8rem; line-height: 1.55; overflow-x: auto;"><code>${escaped}</code></pre>`;
    } else {
        codeContainer.innerHTML = `
            <div class="code-editor-wrapper" style="display: flex; flex-direction: column; background: #080c14; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 6px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0.85rem; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); font-size: 0.8rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span class="status-badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.3);">
                            <i class="fas fa-pen"></i> IN-BROWSER EDITOR
                        </span>
                        <span style="font-weight: 600; color: #f8fafc;" id="editor-filename-label">${currentActiveFileName}</span>
                    </div>
                    <div style="color: #64748b; font-size: 0.74rem;">
                        <kbd style="background: rgba(255,255,255,0.08); padding: 2px 5px; border-radius: 3px; color: #cbd5e1;">Tab</kbd> inserts 2 spaces · Auto-formats on Save
                    </div>
                </div>
                <textarea id="code-editor-textarea" spellcheck="false" style="width: 100%; min-height: 480px; background: transparent; color: #e2e8f0; font-family: 'Fira Code', 'JetBrains Mono', Consolas, Menlo, Monaco, monospace; font-size: 0.85rem; line-height: 1.6; padding: 1rem; border: none; outline: none; resize: vertical; box-sizing: border-box;"></textarea>
            </div>
        `;
        const textarea = document.getElementById('code-editor-textarea');
        if (textarea) {
            textarea.value = content;
            textarea.addEventListener('keydown', function(e) {
                if (e.key === 'Tab') {
                    e.preventDefault();
                    const start = this.selectionStart;
                    const end = this.selectionEnd;
                    this.value = this.value.substring(0, start) + '  ' + this.value.substring(end);
                    this.selectionStart = this.selectionEnd = start + 2;
                }
            });
        }
    }
}

function toggleCodeEditMode() {
    if (!currentActiveFileName || !currentCodeFiles[currentActiveFileName]) {
        return showToast("No active code file selected to edit", "error");
    }

    isCodeEditMode = !isCodeEditMode;
    const toggleBtn = document.getElementById('btn-toggle-edit');
    const label = document.getElementById('btn-toggle-edit-label');
    const saveBtn = document.getElementById('btn-save-replan');
    const discardBtn = document.getElementById('btn-discard-edit');

    if (isCodeEditMode) {
        if (label) label.innerText = "Exit Edit Mode";
        if (toggleBtn) {
            toggleBtn.style.background = "rgba(245, 158, 11, 0.15)";
            toggleBtn.style.borderColor = "rgba(245, 158, 11, 0.4)";
            toggleBtn.style.color = "#fbbf24";
        }
        if (saveBtn) saveBtn.style.display = "inline-flex";
        if (discardBtn) discardBtn.style.display = "inline-flex";
        showToast(`Editing ${currentActiveFileName} in-browser`, "info");
    } else {
        if (label) label.innerText = "Edit Code";
        if (toggleBtn) {
            toggleBtn.style.background = "rgba(99, 102, 241, 0.15)";
            toggleBtn.style.borderColor = "rgba(99, 102, 241, 0.45)";
            toggleBtn.style.color = "#a5b4fc";
        }
        if (saveBtn) saveBtn.style.display = "none";
        if (discardBtn) discardBtn.style.display = "none";
    }

    renderActiveCodeView();
}

async function saveAndReplanCode() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active workspace selected", "error");
    if (!currentActiveFileName) return showToast("No active file selected", "error");

    const textarea = document.getElementById('code-editor-textarea');
    if (!textarea) return;
    const updatedCode = textarea.value;

    const saveBtn = document.getElementById('btn-save-replan');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> <span>Saving & Planning...</span>`;
    }

    const statusCard = document.getElementById('code-replan-status-card');
    if (statusCard) {
        statusCard.style.display = "block";
        statusCard.innerHTML = `
            <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.35); color: #a5b4fc; border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.85rem; display: flex; align-items: center; gap: 0.6rem;">
                <i class="fas fa-spinner fa-spin"></i> Running terraform fmt, syntax validation, and dry-run plan for <strong>${currentActiveFileName}</strong>...
            </div>
        `;
    }

    try {
        const res = await apiFetch(`/api/projects/${slug}/code`, {
            method: 'POST',
            body: JSON.stringify({
                filename: currentActiveFileName,
                content: updatedCode,
                replan: true
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errData.detail || "Failed to save and re-plan code");
        }

        const data = await res.json();
        currentCodeFiles[currentActiveFileName] = data.content;
        textarea.value = data.content;

        const isSuccess = data.validation?.valid && (data.plan?.status === 'success' || data.plan?.status === 'skipped');
        const planSummary = data.plan?.summary || "Plan Complete";
        const escapedPlan = (data.plan?.output || data.validation?.output || "").replace(/</g, '&lt;').replace(/>/g, '&gt;');

        if (statusCard) {
            if (isSuccess) {
                statusCard.innerHTML = `
                    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.35); color: #34d399; border-radius: 8px; padding: 0.85rem 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.4rem;">
                            <strong style="display: flex; align-items: center; gap: 0.4rem;">
                                <i class="fas fa-check-circle"></i> Validation & Plan Dry-Run Succeeded
                            </strong>
                            <span class="status-badge" style="background: rgba(16, 185, 129, 0.2); color: #a7f3d0; font-size: 0.74rem; font-weight: 600; padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.4);">
                                ${planSummary}
                            </span>
                        </div>
                        <p style="margin: 0.25rem 0 0.5rem 0; font-size: 0.82rem; color: #cbd5e1;">${data.message}</p>
                        <details style="margin-top: 0.4rem; font-size: 0.78rem;">
                            <summary style="cursor: pointer; color: #6ee7b7; font-weight: 600;">View Plan Dry-Run Console Output</summary>
                            <pre style="margin-top: 0.4rem; padding: 0.75rem; background: #020617; border-radius: 4px; overflow-x: auto; font-size: 0.75rem; color: #94a3b8; max-height: 220px; line-height: 1.45;"><code>${escapedPlan}</code></pre>
                        </details>
                    </div>
                `;
                showToast(`Saved and re-planned ${currentActiveFileName}!`, "success");
            } else {
                statusCard.innerHTML = `
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.35); color: #f87171; border-radius: 8px; padding: 0.85rem 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.4rem;">
                            <strong style="display: flex; align-items: center; gap: 0.4rem;">
                                <i class="fas fa-exclamation-triangle"></i> Validation or Plan Failed
                            </strong>
                            <span class="status-badge" style="background: rgba(239, 68, 68, 0.2); color: #fca5a5; font-size: 0.74rem; font-weight: 600; padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(239, 68, 68, 0.4);">
                                ${planSummary}
                            </span>
                        </div>
                        <p style="margin: 0.25rem 0 0.5rem 0; font-size: 0.82rem; color: #fca5a5;">Your code changes introduced syntax or plan errors. Review output below:</p>
                        <pre style="margin-top: 0.4rem; padding: 0.75rem; background: #020617; border-radius: 4px; overflow-x: auto; font-size: 0.75rem; color: #fca5a5; max-height: 220px; line-height: 1.45;"><code>${escapedPlan}</code></pre>
                    </div>
                `;
                showToast("Code saved, but syntax validation/plan failed.", "error");
            }
        }
    } catch (err) {
        showToast(err.message, "error");
        if (statusCard) {
            statusCard.innerHTML = `
                <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.35); color: #f87171; border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.85rem;">
                    <strong>Error:</strong> ${err.message}
                </div>
            `;
        }
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = `<i class="fas fa-play"></i> <span>Save & Re-Plan (Dry-Run)</span>`;
        }
    }
}

function discardCodeEdits() {
    if (isCodeEditMode) {
        toggleCodeEditMode();
    }
    const statusCard = document.getElementById('code-replan-status-card');
    if (statusCard) statusCard.style.display = "none";
    showToast("Edits discarded", "info");
}

function copyCurrentCodeFile() {
    if (!currentActiveFileName || !currentCodeFiles || !currentCodeFiles[currentActiveFileName]) {
        return showToast("No active code file selected", "error");
    }
    const content = currentCodeFiles[currentActiveFileName];
    navigator.clipboard.writeText(content).then(() => {
        showToast(`Copied ${currentActiveFileName} to clipboard!`, "success");
    }).catch(err => {
        showToast("Failed to copy code: " + err, "error");
    });
}

function downloadCurrentCodeFile() {
    if (!currentActiveFileName || !currentCodeFiles || !currentCodeFiles[currentActiveFileName]) {
        return showToast("No active code file selected", "error");
    }
    const content = currentCodeFiles[currentActiveFileName];
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const safeName = currentActiveFileName.replace(/\//g, '_');
    a.download = safeName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    showToast(`Downloaded ${safeName}`, "success");
}

function downloadWorkspaceZip() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active workspace selected", "error");
    showToast(`Exporting .zip archive for ${slug}...`, "info");
    const downloadUrl = `/api/projects/${slug}/export/zip`;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `${slug}-infrastructure.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
}

// ─── Snapshots / Evolution ──────────────────────────────────────
async function loadSnapshots(slug, autoSelectLatest = true) {
    const res = await apiFetch(`/api/projects/${slug}/snapshots`);
    const snapshots = await res.json();
    const container = document.getElementById('snapshot-items');
    if (!snapshots || snapshots.length === 0) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.85rem; padding: 0.5rem;">No snapshots yet. Click <strong>⚡ Evolve Workspace</strong> to modify this project and capture version history.</p>';
        return;
    }

    container.innerHTML = snapshots.map((s, idx) => `
        <div class="snapshot-item ${idx === 0 ? 'active' : ''}" id="snap-${s.id}" onclick="viewDiff('${slug}', '${s.id}')">
            <i class="fas fa-history" style="margin-right: 0.35rem; color: #818cf8;"></i> ${s.timestamp}
            ${s.is_latest || idx === 0 ? '<span style="font-size:0.65rem; background:rgba(99,102,241,0.25); color:#a5b4fc; padding:1px 5px; border-radius:4px; margin-left:4px;">Latest Baseline</span>' : ''}
        </div>
    `).join('');

    if (autoSelectLatest && snapshots.length > 0) {
        const target = snapshots[0];
        viewDiff(slug, target.id);
    }
}

async function viewDiff(slug, snapshotId) {
    document.querySelectorAll('.snapshot-item').forEach(el => el.classList.remove('active'));
    const activeEl = document.getElementById(`snap-${snapshotId}`);
    if (activeEl) activeEl.classList.add('active');

    const res = await apiFetch(`/api/projects/${slug}/diff/${snapshotId}`);
    const data = await res.json();
    const viewer = document.getElementById('diff-viewer');
    const rawDiff = data.diff || '';
    if (!rawDiff.trim() || rawDiff.includes('No differences detected.')) {
        viewer.innerHTML = `
            <div style="text-align: center; padding: 2.5rem; color: #94a3b8;">
                <i class="fas fa-check-circle" style="font-size: 2rem; color: #10b981; margin-bottom: 0.5rem; display: block;"></i>
                <div style="font-weight: 600; color: #fff;">In Sync with Baseline</div>
                <p style="font-size: 0.85rem; margin-top: 0.25rem;">No modifications detected between current code and this snapshot.</p>
            </div>
        `;
        return;
    }

    const coloredDiff = rawDiff.split('\n').map(line => {
        const safe = line.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff --git')) {
            return `<div style="background: rgba(255, 255, 255, 0.05); color: #e2e8f0; font-weight: 700; padding: 3px 8px; font-family: monospace;">${safe}</div>`;
        }
        if (line.startsWith('+')) {
            return `<div style="background: rgba(34, 197, 94, 0.12); color: #4ade80; border-left: 3px solid #22c55e; padding: 1px 8px; font-weight: 500;">${safe}</div>`;
        }
        if (line.startsWith('-')) {
            return `<div style="background: rgba(239, 68, 68, 0.12); color: #f87171; border-left: 3px solid #ef4444; padding: 1px 8px; font-weight: 500;">${safe}</div>`;
        }
        if (line.startsWith('@@')) {
            return `<div style="background: rgba(99, 102, 241, 0.15); color: #818cf8; font-weight: 600; padding: 3px 8px; margin: 4px 0; border-radius: 4px;">${safe}</div>`;
        }
        return `<div style="color: #94a3b8; padding: 1px 8px;">${safe}</div>`;
    }).join('');

    viewer.innerHTML = `<pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.82rem; line-height: 1.55; margin: 0; background: #0b1120; border-radius: 6px; padding: 0.75rem; border: 1px solid rgba(255,255,255,0.06);"><code>${coloredDiff}</code></pre>`;
}

async function submitEvolveWorkspace() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active workspace selected.", "error");

    const promptInput = document.getElementById('evolve-prompt-input');
    const prompt = promptInput?.value?.trim();
    if (!prompt) return showToast("Please enter follow-up evolution requirements.", "error");

    const apply = document.getElementById('evolve-live-apply')?.checked || false;
    const engine = document.getElementById('evolve-engine-select')?.value || 'terraform';
    const btn = document.getElementById('btn-submit-evolve');
    const pill = document.getElementById('evolve-status-pill');

    const credentials = {
        AWS_ACCESS_KEY_ID: document.getElementById('aws-key')?.value || '',
        AWS_SECRET_ACCESS_KEY: document.getElementById('aws-secret')?.value || '',
        AWS_DEFAULT_REGION: document.getElementById('aws-region')?.value || '',
        ARM_CLIENT_ID: document.getElementById('az-client-id')?.value || '',
        ARM_CLIENT_SECRET: document.getElementById('az-client-secret')?.value || '',
        ARM_SUBSCRIPTION_ID: document.getElementById('az-subscription-id')?.value || '',
        ARM_TENANT_ID: document.getElementById('az-tenant-id')?.value || '',
        GOOGLE_CREDENTIALS: document.getElementById('gcp-json')?.value || ''
    };

    const selectedModel = document.getElementById('infra-model')?.value || 'gemini/gemini-2.0-flash';
    let provider = 'gemini';
    if (selectedModel.includes('/')) {
        provider = selectedModel.split('/')[0];
    }
    const ai_config = {
        provider: provider,
        model: selectedModel,
        key: ''
    };

    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Evolving...`;
    if (pill) pill.style.display = 'inline-flex';

    showToast(`🚀 Evolution started for workspace: ${slug}`, "info");

    const cloud_provider = document.getElementById('infra-cloud')?.value || 'aws';
    const env_tier = document.getElementById('infra-env')?.value || 'production';
    const region = document.getElementById('infra-region')?.value || 'us-east-1';

    try {
        const res = await apiFetch(`/api/projects/${slug}/evolve`, {
            method: 'POST',
            body: JSON.stringify({ prompt, apply, engine, credentials, ai_config, cloud_provider, env_tier, region })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to start evolution");
        }

        const data = await res.json();
        showToast(`⚡ Evolution running. Baseline snapshot: ${data.pre_snapshot || 'saved'}`, "success");

        if (promptInput) promptInput.value = '';

        if (document.getElementById('live-console-modal')) {
            document.getElementById('live-console-modal').style.display = 'flex';
            const consoleElem = document.getElementById('live-console');
            if (consoleElem) consoleElem.innerText = `🚀 Evolving workspace '${slug}'...\nBaseline snapshot archived: ${data.pre_snapshot || 'N/A'}\n`;
        }

        let pollCount = 0;
        const interval = setInterval(async () => {
            pollCount++;
            try {
                const statusRes = await apiFetch(`/api/runs/status`);
                if (statusRes.ok) {
                    const statusData = await statusRes.json();

                    // Stream active evolution logs to the live console
                    const consoleElem = document.getElementById('live-console');
                    if (consoleElem && statusData.logs) {
                        consoleElem.innerText = statusData.logs;
                        consoleElem.scrollTop = consoleElem.scrollHeight;
                    }

                    if (!statusData.running || pollCount > 80) {
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.innerHTML = `<i class="fas fa-bolt"></i> ⚡ Evolve Workspace`;
                        if (pill) pill.style.display = 'none';

                        showToast(`✅ Workspace '${slug}' evolution completed!`, "success");
                        await loadSnapshots(slug, true);
                        const codeRes = await apiFetch(`/api/projects/${slug}/code`);
                        if (codeRes.ok) {
                            currentCodeFiles = await codeRes.json();
                            renderFileTabs(currentCodeFiles);
                        }
                        await fetchProjects();
                    }
                }
            } catch (pollErr) {
                console.error("Polling error:", pollErr);
            }
        }, 1500);

    } catch (e) {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-bolt"></i> ⚡ Evolve Workspace`;
        if (pill) pill.style.display = 'none';
        showToast(e.message, "error");
    }
}

// ─── Cloud Provider & Region Presets ────────────────────────────
function onCloudProviderChange() {
    const cloud = document.getElementById('infra-cloud')?.value || 'aws';
    const regionSelect = document.getElementById('infra-region');
    if (!regionSelect) return;

    const regionPresets = {
        aws: [
            { val: 'us-east-1', label: 'us-east-1 (N. Virginia)' },
            { val: 'us-west-2', label: 'us-west-2 (Oregon)' },
            { val: 'eu-west-1', label: 'eu-west-1 (Ireland)' },
            { val: 'ap-south-1', label: 'ap-south-1 (Mumbai)' }
        ],
        azure: [
            { val: 'eastus', label: 'eastus (East US)' },
            { val: 'westeurope', label: 'westeurope (West Europe)' },
            { val: 'centralus', label: 'centralus (Central US)' },
            { val: 'southeastasia', label: 'southeastasia (Singapore)' }
        ],
        gcp: [
            { val: 'us-central1', label: 'us-central1 (Iowa)' },
            { val: 'europe-west1', label: 'europe-west1 (Belgium)' },
            { val: 'asia-east1', label: 'asia-east1 (Taiwan)' }
        ],
        kubernetes: [
            { val: 'cluster.local', label: 'cluster.local (Default NS)' },
            { val: 'kube-system', label: 'kube-system' }
        ],
        multicloud: [
            { val: 'global', label: 'global (Multi-Region / Any)' },
            { val: 'us-east-1', label: 'AWS us-east-1 + Azure eastus' }
        ]
    };

    const currentVal = regionSelect.value;
    regionSelect.innerHTML = '';
    const list = regionPresets[cloud] || regionPresets.aws;
    list.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.val;
        opt.textContent = r.label;
        if (r.val === currentVal) opt.selected = true;
        regionSelect.appendChild(opt);
    });
}

// ─── Quick Prompt Starters ──────────────────────────────────────
function insertPromptTemplate(type) {
    const promptInput = document.getElementById('infra-prompt');
    const engineSelect = document.getElementById('infra-engine');
    const cloudSelect = document.getElementById('infra-cloud');
    const envSelect = document.getElementById('infra-env');
    const regionSelect = document.getElementById('infra-region');
    if (!promptInput) return;

    const templates = {
        's3_vault': {
            text: 'Deploy an AWS S3 Glacier Vault with strict server-side encryption (AES-256), bucket versioning enabled, automatic lifecycle transition to Glacier Flexible Retrieval after 30 days, and complete public access block complying with CIS AWS Foundations Benchmark.',
            cloud: 'aws',
            env: 'production',
            region: 'us-east-1',
            engine: 'terraform'
        },
        'vpc_ha': {
            text: 'Create a high-availability AWS Virtual Private Cloud (VPC) spanning 2 Availability Zones with public and private subnets, redundant NAT Gateways, Internet Gateway, and fine-grained Network ACLs and Route Tables.',
            cloud: 'aws',
            env: 'production',
            region: 'us-east-1',
            engine: 'terraform'
        },
        'eks_cluster': {
            text: 'Provision a production-ready AWS EKS Kubernetes Cluster with an IAM OIDC provider, managed node group with auto-scaling (t3.medium instances), and dedicated security groups enforcing least-privilege egress/ingress.',
            cloud: 'aws',
            env: 'production',
            region: 'us-east-1',
            engine: 'terraform'
        },
        'azure_aks': {
            text: 'Deploy a production Azure Kubernetes Service (AKS) cluster with Azure CNI networking, managed system identity, Azure Key Vault CSI secret store provider, and Azure Monitor container insights.',
            cloud: 'azure',
            env: 'production',
            region: 'eastus',
            engine: 'terraform'
        },
        'gcp_cloudrun': {
            text: 'Provision a scalable Google Cloud Run container microservice with Cloud SQL PostgreSQL instance in a private VPC, Serverless VPC Access connector, and Cloud Armor security policies.',
            cloud: 'gcp',
            env: 'production',
            region: 'us-central1',
            engine: 'terraform'
        },
        'opentofu_web': {
            text: 'Deploy a multi-tier secure web application architecture using OpenTofu: an Application Load Balancer (ALB), Auto Scaling Group of web servers across 2 subnets, and an isolated PostgreSQL RDS database instance in private subnets.',
            cloud: 'aws',
            env: 'production',
            region: 'us-east-1',
            engine: 'opentofu'
        },
        'serverless_api': {
            text: 'Build a serverless REST API backend using AWS API Gateway (HTTP API v2), an AWS Lambda Python runtime microservice with IAM execution role, and an Amazon DynamoDB table with on-demand capacity and point-in-time recovery.',
            cloud: 'aws',
            env: 'production',
            region: 'us-east-1',
            engine: 'terraform'
        }
    };

    const chosen = templates[type];
    if (chosen) {
        promptInput.value = chosen.text;
        if (cloudSelect && chosen.cloud) {
            cloudSelect.value = chosen.cloud;
            onCloudProviderChange();
        }
        if (envSelect && chosen.env) {
            envSelect.value = chosen.env;
        }
        if (regionSelect && chosen.region) {
            regionSelect.value = chosen.region;
        }
        if (engineSelect && chosen.engine) {
            engineSelect.value = chosen.engine;
        }
        promptInput.focus();
        updateCostEstimator();
        showToast("Architecture template and governance presets loaded!", "info");
    }
}

// ─── Pre-Run Interactive Cost & Resource Estimator ───────────────
function extractQuantityForTerm(term, text) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    // 1. Direct multipliers: "3x t3.large", "3* t3.large", "t3.large x 3"
    const directPrefixRegex = new RegExp(`\\b(\\d+)\\s*(?:x|\\*)\\s*(?:of\\s+)?` + escaped, 'i');
    const directSuffixRegex = new RegExp(escaped + `\\s*(?:x|\\*)\\s*(\\d+)\\b`, 'i');

    // 2. Preceding quantity with optional intermediate service words:
    // Matches "aws 3 ec2 t3.large", "3 ec2 t3.large", "3 instances of t3.large", "3 vms t3.large"
    const intermediateWords = `(?:(?:ec2|vm|vms|instances?|nodes?|servers?|virtual machines?)\\s+)*`;
    const flexiblePrefixRegex = new RegExp(`\\b(\\d+)\\s+` + intermediateWords + `(?:of\\s+)?` + escaped, 'i');

    // 3. Suffix words: "t3.large count = 3", "t3.large with 3 instances"
    const flexibleSuffixRegex = new RegExp(escaped + `\\s+(?:(?:instances?|nodes?|vms?|servers?)\\s+)?(?:count|quantity)?\\s*[:=]?\\s*(\\d+)\\b`, 'i');

    // 4. Quantity preceding generic compute keyword: e.g. "aws 3 ec2"
    const globalCountRegex = new RegExp(`\\b(\\d+)\\s+(?:ec2|vms?|instances?|nodes?|servers?)\\b`, 'i');

    for (const regex of [directPrefixRegex, flexiblePrefixRegex, directSuffixRegex, flexibleSuffixRegex, globalCountRegex]) {
        const match = text.match(regex);
        if (match && match[1]) {
            const q = parseInt(match[1], 10);
            if (q > 0 && q <= 500) return q;
        }
    }
    return 1;
}

function updateCostEstimator() {
    const promptInput = document.getElementById('infra-prompt');
    const estimatorCard = document.getElementById('cost-estimator-card');
    if (!promptInput || !estimatorCard) return;

    const rawText = (promptInput.value || '').trim();
    if (rawText.length < 4) {
        estimatorCard.style.display = 'none';
        return;
    }

    const text = rawText.toLowerCase();
    const budgetInput = document.getElementById('infra-budget');
    const budget = parseFloat(budgetInput?.value || 100);
    const envTier = document.getElementById('infra-env')?.value || 'production';
    const cloud = (document.getElementById('infra-cloud')?.value || 'aws').toLowerCase();

    const detected = [];
    let rawTotal = 0;
    const matchedServices = new Set();
    let workingText = text;

    // 1. Database-backed SKU Matching (Sort by length descending)
    if (Array.isArray(dbPricingCatalog) && dbPricingCatalog.length > 0) {
        const sortedCatalog = [...dbPricingCatalog].sort((a, b) => b.sku.length - a.sku.length);

        for (const item of sortedCatalog) {
            const skuLower = item.sku.toLowerCase();
            const escapedSku = skuLower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            // Word boundary match supporting dots and underscores
            const skuRegex = new RegExp(`(?:^|[^a-z0-9_])${escapedSku}(?:$|[^a-z0-9_])`, 'i');

            if (skuRegex.test(workingText)) {
                const qty = extractQuantityForTerm(skuLower, text);
                const itemMonthly = (item.monthly_usd || 0) * qty;

                let icon = "fas fa-microchip";
                if (item.service === 'rds') icon = "fas fa-database";
                else if (item.service === 'managed') icon = "fas fa-network-wired";
                else if (item.service === 'storage') icon = "fas fa-hard-drive";
                else if (item.provider === 'aws') icon = "fab fa-aws";
                else if (item.provider === 'azure') icon = "fab fa-microsoft";
                else if (item.provider === 'gcp') icon = "fab fa-google";

                const displayName = qty > 1 ? `${qty}x ${item.sku}` : item.sku;

                detected.push({
                    name: displayName,
                    cost: itemMonthly,
                    icon: icon,
                    sku: item.sku,
                    service: item.service
                });
                rawTotal += itemMonthly;
                matchedServices.add(item.service);

                // Mask out matched SKU so smaller substrings don't match again
                workingText = workingText.replace(new RegExp(escapedSku, 'gi'), ' '.repeat(skuLower.length));
            }
        }
    }

    // 2. High-Level Architecture & Managed Service Keyword Matchers
    const architecturalRules = [
        {
            serviceKey: "managed_k8s",
            pattern: /\b(eks|kubernetes|k8s|aks|gke)\b/i,
            name: "Kubernetes Control Plane",
            icon: "fas fa-dharmachakra",
            cost: 73.00
        },
        {
            serviceKey: "alb",
            pattern: /\b(load balancer|alb|application load balancer)\b/i,
            name: "Application Load Balancer",
            icon: "fas fa-shield",
            cost: 21.90
        },
        {
            serviceKey: "nlb",
            pattern: /\b(nlb|network load balancer)\b/i,
            name: "Network Load Balancer",
            icon: "fas fa-network-wired",
            cost: 18.25
        },
        {
            serviceKey: "nat_gateway",
            pattern: /\b(nat gateway|nat|redundant nat)\b/i,
            name: "VPC NAT Gateway",
            icon: "fas fa-network-wired",
            cost: 32.85
        },
        {
            serviceKey: "rds",
            pattern: /\b(rds|postgres|postgresql|mysql|aurora|database|relational db)\b/i,
            name: "Managed Relational DB",
            icon: "fas fa-database",
            cost: 49.64 // db.t3.medium baseline
        },
        {
            serviceKey: "dynamodb",
            pattern: /\b(dynamodb|nosql)\b/i,
            name: "DynamoDB On-Demand",
            icon: "fas fa-table",
            cost: 5.00
        },
        {
            serviceKey: "storage_object",
            pattern: /\b(s3|bucket|blob storage|blob)\b/i,
            name: "Object Storage & Vault",
            icon: "fas fa-box-archive",
            cost: 2.30
        },
        {
            serviceKey: "storage_glacier",
            pattern: /\b(glacier|cold vault|deep archive)\b/i,
            name: "Glacier Vault",
            icon: "fas fa-archive",
            cost: 1.00
        },
        {
            serviceKey: "lambda",
            pattern: /\b(lambda|serverless|api gateway)\b/i,
            name: "Serverless Lambda API",
            icon: "fas fa-bolt",
            cost: 5.00
        },
        {
            serviceKey: "cloudrun",
            pattern: /\b(cloud run|cloudrun)\b/i,
            name: "GCP Cloud Run Service",
            icon: "fas fa-cloud",
            cost: 8.00
        }
    ];

    for (const rule of architecturalRules) {
        if (!matchedServices.has(rule.serviceKey) && !matchedServices.has(rule.name.toLowerCase()) && rule.pattern.test(workingText)) {
            // Ensure we don't duplicate managed DB if an RDS SKU was already selected
            if (rule.serviceKey === 'rds' && matchedServices.has('rds')) continue;
            detected.push({ name: rule.name, cost: rule.cost, icon: rule.icon });
            rawTotal += rule.cost;
            matchedServices.add(rule.serviceKey);
        }
    }

    // 3. Generic VM Compute fallback if no compute SKU matched
    const hasComputeSku = matchedServices.has('ec2') || matchedServices.has('vm') || matchedServices.has('compute');
    if (!hasComputeSku && /\b(ec2|virtual machine|vm|nodes?|compute|servers?)\b/i.test(workingText)) {
        detected.push({ name: "EC2 VM Compute", cost: 30.40, icon: "fas fa-microchip" });
        rawTotal += 30.40;
    }

    // 4. Storage volume allocation detector (e.g. "100 GB", "500gb", "1 TB")
    const storageMatch = text.match(/(\d+)\s*(gb|tb)\b/i);
    if (storageMatch) {
        let sizeGb = parseInt(storageMatch[1], 10);
        if (storageMatch[2].toLowerCase() === 'tb') sizeGb *= 1024;
        if (sizeGb > 0 && sizeGb <= 64000) {
            const storageCost = sizeGb * 0.08; // $0.08/GB-mo EBS gp3
            const label = sizeGb >= 1024 ? `${(sizeGb / 1024).toFixed(0)}TB EBS SSD` : `${sizeGb}GB EBS SSD`;
            detected.push({ name: label, cost: storageCost, icon: "fas fa-hard-drive" });
            rawTotal += storageCost;
        }
    }

    // 5. Fallback baseline if nothing identified
    if (detected.length === 0) {
        detected.push({ name: "Core Platform IaC", cost: 15.00, icon: "fas fa-cubes" });
        rawTotal = 15.00;
    }

    // 6. Apply Environment Multipliers & Formulate Customer Explanations
    let multiplier = 1.0;
    let multiplierLabel = "(Standard Sizing · 1.0x Base)";
    let tierExplanation = `<i class="fas fa-circle-info" style="color: #818cf8;"></i> Staging Tier: 100% 24/7 continuous On-Demand standard baseline.`;
    if (envTier === 'production') {
        multiplier = 1.25;
        multiplierLabel = "(Production HA Sizing · 1.25x Buffer)";
        tierExplanation = `<i class="fas fa-shield" style="color: #38bdf8;"></i> Production Tier (+25%): 24/7 uptime + Multi-AZ standby capacity buffer, snapshot backup retention & enhanced telemetry.`;
    } else if (envTier === 'development') {
        multiplier = 0.45;
        multiplierLabel = "(Dev Cost-Optimized · 0.45x Schedule)";
        tierExplanation = `<i class="fas fa-clock" style="color: #34d399;"></i> Dev Tier (-55%): Assumes scheduled business-hour uptime (10h/day x 5d) & single-AZ non-HA dev architecture.`;
    }

    const finalEstimated = rawTotal * multiplier;

    // 7. Render Estimator Card
    estimatorCard.style.display = 'block';
    const costValEl = document.getElementById('estimator-cost-value');
    const badgeEl = document.getElementById('estimator-budget-badge');
    const multEl = document.getElementById('estimator-env-multiplier');
    const baseOnDemandEl = document.getElementById('estimator-base-on-demand');
    const tierExplEl = document.getElementById('estimator-tier-explanation');
    const pillsContainer = document.getElementById('estimator-resource-pills');
    const warningBanner = document.getElementById('estimator-warning-banner');
    const warningText = document.getElementById('estimator-warning-text');

    if (costValEl) costValEl.innerText = `~$${finalEstimated.toFixed(2)}/mo`;
    if (multEl) multEl.innerText = multiplierLabel;
    if (baseOnDemandEl) {
        baseOnDemandEl.style.display = 'inline-block';
        baseOnDemandEl.innerText = `Base 24/7: ~$${rawTotal.toFixed(2)}/mo`;
    }
    if (tierExplEl) {
        tierExplEl.innerHTML = tierExplanation;
    }

    if (pillsContainer) {
        pillsContainer.innerHTML = detected.slice(0, 4).map(d => `
            <span class="badge" style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.12); color: #cbd5e1; font-size: 0.72rem; padding: 2px 7px; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.3rem;">
                <i class="${d.icon}" style="color: #818cf8; font-size: 0.7rem;"></i> ${d.name}: ~$${(d.cost * multiplier).toFixed(0)}/mo
            </span>
        `).join('') + (detected.length > 4 ? `<span style="font-size: 0.7rem; color: #64748b;">+${detected.length - 4} more</span>` : '');
    }

    // 8. Budget Alerting
    if (finalEstimated > budget) {
        const diff = (finalEstimated - budget).toFixed(0);
        if (badgeEl) {
            badgeEl.innerText = `⚠️ Exceeds Budget by $${diff}`;
            badgeEl.style.background = 'rgba(239, 68, 68, 0.15)';
            badgeEl.style.color = '#f87171';
            badgeEl.style.borderColor = 'rgba(239, 68, 68, 0.35)';
        }
        if (costValEl) costValEl.style.color = '#f87171';
        if (warningBanner) warningBanner.style.display = 'block';
        if (warningText) {
            warningText.innerText = `Projected baseline (~$${finalEstimated.toFixed(0)}/mo) exceeds your allocated budget ($${budget.toFixed(0)} USD). Consider raising your budget or selecting the Development tier.`;
        }
    } else {
        if (badgeEl) {
            badgeEl.innerText = `✅ Within Budget`;
            badgeEl.style.background = 'rgba(16, 185, 129, 0.15)';
            badgeEl.style.color = '#34d399';
            badgeEl.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        }
        if (costValEl) costValEl.style.color = '#34d399';
        if (warningBanner) warningBanner.style.display = 'none';
    }
}

// ─── Credential Tabs ────────────────────────────────────────────
function switchCredTab(provider) {
    document.querySelectorAll('[id^="cred-panel-"]').forEach(p => p.style.display = 'none');
    const panel = document.getElementById(`cred-panel-${provider}`);
    if (panel) panel.style.display = (provider === 'gcp') ? 'block' : 'grid';
    if (event?.target?.parentElement) {
        event.target.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');
    }
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
    const isGitOps = document.getElementById('infra-gitops')?.checked || false;
    const details = document.getElementById('gitops-section');
    if (details) {
        details.open = isGitOps;
    }
}

// ─── Generate Infrastructure ────────────────────────────────────
async function generateInfra() {
    const promptInput = document.getElementById('infra-prompt');
    const prompt = promptInput ? promptInput.value.trim() : '';
    const budget = document.getElementById('infra-budget')?.value || 100;
    const engine = document.getElementById('infra-engine')?.value || 'terraform';
    const cloud_provider = document.getElementById('infra-cloud')?.value || 'aws';
    const env_tier = document.getElementById('infra-env')?.value || 'production';
    const region = document.getElementById('infra-region')?.value || 'us-east-1';
    const selectedModel = document.getElementById('infra-model')?.value || 'gemini/gemini-2.0-flash';
    const genBtn = document.getElementById('btn-generate');

    if (!prompt) return showToast("Please enter an infrastructure requirement.", "error");

    const apply = document.getElementById('infra-apply')?.checked || false;
    const new_project = document.getElementById('infra-new-project')?.checked ?? true;
    const gitops = document.getElementById('infra-gitops')?.checked || false;
    const git_repo = document.getElementById('gitops-repo')?.value?.trim() || '';
    const target_branch = document.getElementById('gitops-branch')?.value?.trim() || 'main';
    const git_token = document.getElementById('gitops-token')?.value?.trim() || '';

    let provider = 'gemini';
    if (selectedModel.includes('/')) {
        provider = selectedModel.split('/')[0];
    }

    const ai_config = {
        provider: provider,
        model: selectedModel,
        key: ''
    };

    const credentials = {
        AWS_ACCESS_KEY_ID: document.getElementById('aws-key')?.value || '',
        AWS_SECRET_ACCESS_KEY: document.getElementById('aws-secret')?.value || '',
        AWS_DEFAULT_REGION: document.getElementById('aws-region')?.value || region,
        ARM_CLIENT_ID: document.getElementById('az-client-id')?.value || '',
        ARM_CLIENT_SECRET: document.getElementById('az-client-secret')?.value || '',
        ARM_SUBSCRIPTION_ID: document.getElementById('az-subscription-id')?.value || '',
        ARM_TENANT_ID: document.getElementById('az-tenant-id')?.value || '',
        GOOGLE_CREDENTIALS: document.getElementById('gcp-json')?.value || ''
    };

    if (genBtn) {
        genBtn.disabled = true;
        genBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> <span>Synthesizing...</span>`;
    }
    const genStatus = document.getElementById('gen-status');
    if (genStatus) genStatus.style.display = 'inline-block';

    const liveModal = document.getElementById('live-console-modal');
    if (liveModal) liveModal.style.display = 'flex';
    const consoleElem = document.getElementById('live-console');
    if (consoleElem) consoleElem.innerText = `🚀 Connecting to Multi-Agent Orchestrator...\nTarget Cloud: ${cloud_provider.toUpperCase()} | Env: ${env_tier.toUpperCase()} | Region: ${region}\nTarget Model: ${selectedModel}\nEngine: ${engine.toUpperCase()}\n\n`;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
        
        const payload = { prompt, budget, apply, new_project, credentials, ai_config, gitops, git_repo, target_branch, git_token, engine, cloud_provider, env_tier, region };
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
            const msg = errData.detail || `Server error: ${response.status}`;
            if (response.status === 402 || msg.toLowerCase().includes("quota")) {
                if (typeof openUpgradeModal === 'function') {
                    openUpgradeModal();
                }
            }
            throw new Error(msg);
        }
        showToast("Multi-Agent synthesis started! Streaming live orchestration...", "info");
        startPollingLogs();
    } catch (e) {
        let errorMsg = e.message;
        if (e.name === 'AbortError') {
            errorMsg = "Request timed out. Is the server running?";
        } else if (errorMsg === 'Failed to fetch') {
            errorMsg = "Could not connect to server. Check if the dashboard is running on port 5000.";
        }
        if (consoleElem) consoleElem.innerText += "\n❌ Error: " + errorMsg;
        if (genBtn) {
            genBtn.disabled = false;
            genBtn.innerHTML = `<i class="fas fa-wand-magic-sparkles"></i> <span>Synthesize Infrastructure</span>`;
        }
        if (genStatus) genStatus.style.display = 'none';
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
                    if (genBtn) {
                        genBtn.disabled = false;
                        genBtn.innerHTML = `<i class="fas fa-wand-magic-sparkles"></i> <span>Synthesize Infrastructure</span>`;
                    }
                    const genStat = document.getElementById('gen-status');
                    if (genStat) genStat.style.display = 'none';

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
        const currentUserRole = currentOrg ? currentOrg.role : null;
        const isOwner = currentUserRole === 'owner';
        const isAdmin = currentUserRole === 'admin';
        const currentUserId = currentUser ? currentUser.id : null;

        // Configure invite-role options based on caller role
        const inviteRoleSelect = document.getElementById('invite-role');
        if (inviteRoleSelect) {
            if (isOwner) {
                inviteRoleSelect.innerHTML = `
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                    <option value="viewer">Viewer</option>
                `;
            } else {
                inviteRoleSelect.innerHTML = `
                    <option value="member">Member</option>
                    <option value="viewer">Viewer</option>
                `;
            }
        }

        if (!members.length) {
            tbody.innerHTML = '<tr><td colspan="4" style="padding:1rem;color:#888;text-align:center;">No members yet.</td></tr>';
            return;
        }
        tbody.innerHTML = members.map(m => {
            const isTargetOwner = m.role === 'owner' || (currentOrg && m.user_id === currentOrg.owner_id);
            const isTargetAdmin = m.role === 'admin';
            const isSelf = currentUserId && m.user_id === currentUserId;
            const roleColor = isTargetOwner ? '#f59e0b' : isTargetAdmin ? '#6366f1' : m.role === 'viewer' ? '#94a3b8' : '#22c55e';

            // Role editing permissions:
            // - Owner can edit Admins, Members, Viewers
            // - Admin can ONLY edit Members and Viewers (cannot edit Owner or peer Admins)
            // - Self and Owner cannot be edited via dropdown
            const canEdit = !isTargetOwner && !isSelf && (isOwner || (isAdmin && !isTargetAdmin));

            let roleSelect;
            if (canEdit) {
                if (isOwner) {
                    roleSelect = `<select onchange="updateMemberRole(${m.user_id}, this.value)" style="background:#0f172a;color:#fff;border:1px solid #334155;border-radius:4px;padding:2px 6px;font-size:0.8rem;">
                         <option value="admin" ${m.role==='admin'?'selected':''}>Admin</option>
                         <option value="member" ${m.role==='member'?'selected':''}>Member</option>
                         <option value="viewer" ${m.role==='viewer'?'selected':''}>Viewer</option>
                       </select>`;
                } else {
                    roleSelect = `<select onchange="updateMemberRole(${m.user_id}, this.value)" style="background:#0f172a;color:#fff;border:1px solid #334155;border-radius:4px;padding:2px 6px;font-size:0.8rem;">
                         <option value="member" ${m.role==='member'?'selected':''}>Member</option>
                         <option value="viewer" ${m.role==='viewer'?'selected':''}>Viewer</option>
                       </select>`;
                }
            } else {
                roleSelect = `<span style="color:${roleColor};font-weight:600;text-transform:uppercase;font-size:0.8rem;">${m.role}${isTargetOwner ? ' 👑' : ''}</span>`;
            }

            // Member removal permissions:
            // - Owner cannot be removed
            // - Admin cannot remove peer Admins or Owner
            // - Cannot remove self via member list
            const canRemove = !isTargetOwner && !isSelf && (isOwner || (isAdmin && !isTargetAdmin));
            const removeBtn = canRemove
                ? `<button onclick="removeOrgMember(${m.user_id})" style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);color:#f87171;border-radius:4px;padding:3px 8px;font-size:0.75rem;cursor:pointer;">Remove</button>`
                : '';

            return `<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:0.5rem;">${m.username} ${isSelf ? '<span style="color:#64748b;font-size:0.75rem;">(You)</span>' : ''}</td>
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
let activeGitOpsData = null;

async function loadGitOpsDetails(slug) {
    const connectView = document.getElementById('gitops-connect-view');
    const statusView = document.getElementById('gitops-status-view');
    const cancelBtn = document.getElementById('btn-cancel-gitops-connect');

    try {
        const res = await apiFetch(`/api/projects/${slug}/gitops`);
        const data = res.ok ? await res.json() : {};
        activeGitOpsData = data;

        // Check if GitOps / PR is active
        if (data && data.pr_url) {
            // Show Status View, Hide Connect View
            if (connectView) connectView.style.display = 'none';
            if (statusView) statusView.style.display = 'flex';

            const badge = document.getElementById('gitops-approval-badge');
            const branchEl = document.getElementById('gitops-branch-name');
            const prLinkEl = document.getElementById('gitops-pr-link');
            const approverEl = document.getElementById('gitops-approved-by');
            const approveBtn = document.getElementById('btn-approve-pr');
            const mergeBtn = document.getElementById('btn-merge-deploy');

            branchEl.innerText = data.git_branch || 'Not configured';
            approverEl.innerText = data.approved_by || 'None (Pending Review)';
            prLinkEl.innerHTML = `<a href="${data.pr_url}" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 600;">PR #${data.pr_number || 'View'} ↗</a>`;

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
        } else {
            // Show Connect View, Hide Status View
            if (statusView) statusView.style.display = 'none';
            if (connectView) connectView.style.display = 'block';
            if (cancelBtn) cancelBtn.style.display = 'none';

            // Prepopulate form if some repo info is known
            const repoInput = document.getElementById('modal-gitops-repo');
            const branchInput = document.getElementById('modal-gitops-target-branch');
            const featBranchInput = document.getElementById('modal-gitops-branch-name');
            if (repoInput && !repoInput.value) repoInput.value = (data && data.git_repo) || '';
            if (branchInput && !branchInput.value) branchInput.value = (data && data.git_branch) || 'main';
            if (featBranchInput && !featBranchInput.value) featBranchInput.value = `ai/${slug}`;
        }
    } catch (e) {
        console.error("Failed to load GitOps details", e);
        if (statusView) statusView.style.display = 'none';
        if (connectView) connectView.style.display = 'block';
    }
}

function showGitOpsConnectForm() {
    const connectView = document.getElementById('gitops-connect-view');
    const statusView = document.getElementById('gitops-status-view');
    const cancelBtn = document.getElementById('btn-cancel-gitops-connect');
    if (connectView) connectView.style.display = 'block';
    if (statusView) statusView.style.display = 'none';
    if (cancelBtn) cancelBtn.style.display = activeGitOpsData && activeGitOpsData.pr_url ? 'inline-block' : 'none';

    if (activeGitOpsData && currentProject) {
        const repoInput = document.getElementById('modal-gitops-repo');
        if (repoInput && !repoInput.value) repoInput.value = activeGitOpsData.git_repo || '';
    }
}

function cancelGitOpsConnect() {
    if (activeGitOpsData && activeGitOpsData.pr_url) {
        const connectView = document.getElementById('gitops-connect-view');
        const statusView = document.getElementById('gitops-status-view');
        if (connectView) connectView.style.display = 'none';
        if (statusView) statusView.style.display = 'flex';
    }
}

async function submitGitOpsPush() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return;
    const repoUrl = document.getElementById('modal-gitops-repo').value.trim();
    const targetBranch = document.getElementById('modal-gitops-target-branch').value.trim() || 'main';
    const gitToken = document.getElementById('modal-gitops-token').value.trim();
    const branchName = document.getElementById('modal-gitops-branch-name').value.trim();
    const pushBtn = document.getElementById('btn-modal-gitops-push');
    const statusEl = document.getElementById('gitops-push-status');

    if (!repoUrl) {
        showToast('Please provide a Git repository URL', 'error');
        document.getElementById('modal-gitops-repo').focus();
        return;
    }

    const origHtml = pushBtn.innerHTML;
    pushBtn.disabled = true;
    pushBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pushing...';
    if (statusEl) statusEl.innerText = 'Creating branch, staging IaC, and pushing...';

    try {
        const res = await apiFetch(`/api/projects/${slug}/gitops/push`, {
            method: 'POST',
            body: JSON.stringify({
                repo_url: repoUrl,
                target_branch: targetBranch,
                git_token: gitToken,
                branch_name: branchName
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to push to Git');
        showToast(data.message || 'Successfully created Pull Request!', 'success');
        if (statusEl) statusEl.innerText = '';
        await loadGitOpsDetails(slug);
        await fetchProjects();
    } catch (e) {
        showToast(e.message, 'error');
        if (statusEl) statusEl.innerText = `Error: ${e.message}`;
    } finally {
        pushBtn.disabled = false;
        pushBtn.innerHTML = origHtml;
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

// ─── Post-Provisioning Live Deploy Handlers ───────────────────────
let activeDeployData = null;
let activeDeployProvider = 'aws';
let activeDeployLogType = 'apply';

function getDeployCredentials() {
    const credentials = {};
    if (activeDeployProvider === 'aws') {
        const key = document.getElementById('deploy-aws-key')?.value.trim();
        const secret = document.getElementById('deploy-aws-secret')?.value.trim();
        const region = document.getElementById('deploy-aws-region')?.value.trim() || 'us-east-1';
        const token = document.getElementById('deploy-aws-token')?.value.trim();
        if (key) credentials.AWS_ACCESS_KEY_ID = key;
        if (secret) credentials.AWS_SECRET_ACCESS_KEY = secret;
        if (region) credentials.AWS_DEFAULT_REGION = region;
        if (token) credentials.AWS_SESSION_TOKEN = token;
    } else if (activeDeployProvider === 'azure') {
        const clientId = document.getElementById('deploy-az-client-id')?.value.trim();
        const clientSec = document.getElementById('deploy-az-client-secret')?.value.trim();
        const tenantId = document.getElementById('deploy-az-tenant-id')?.value.trim();
        const subId = document.getElementById('deploy-az-subscription-id')?.value.trim();
        if (clientId) credentials.ARM_CLIENT_ID = clientId;
        if (clientSec) credentials.ARM_CLIENT_SECRET = clientSec;
        if (tenantId) credentials.ARM_TENANT_ID = tenantId;
        if (subId) credentials.ARM_SUBSCRIPTION_ID = subId;
    } else if (activeDeployProvider === 'gcp') {
        const gcpJson = document.getElementById('deploy-gcp-json')?.value.trim();
        if (gcpJson) credentials.GOOGLE_CREDENTIALS = gcpJson;
    }
    return credentials;
}

function saveDeployCredentialsToSession() {
    try {
        const creds = {
            provider: activeDeployProvider,
            aws_key: document.getElementById('deploy-aws-key')?.value || '',
            aws_secret: document.getElementById('deploy-aws-secret')?.value || '',
            aws_region: document.getElementById('deploy-aws-region')?.value || 'us-east-1',
            aws_token: document.getElementById('deploy-aws-token')?.value || '',
            az_client_id: document.getElementById('deploy-az-client-id')?.value || '',
            az_client_secret: document.getElementById('deploy-az-client-secret')?.value || '',
            az_tenant_id: document.getElementById('deploy-az-tenant-id')?.value || '',
            az_sub_id: document.getElementById('deploy-az-subscription-id')?.value || '',
            gcp_json: document.getElementById('deploy-gcp-json')?.value || ''
        };
        sessionStorage.setItem('active_deploy_creds', JSON.stringify(creds));
    } catch (e) {}
}

function restoreDeployCredentialsFromSession() {
    try {
        const saved = sessionStorage.getItem('active_deploy_creds');
        if (!saved) return;
        const creds = JSON.parse(saved);
        if (creds.provider) switchDeployCredTab(creds.provider);
        if (creds.aws_key && document.getElementById('deploy-aws-key')) document.getElementById('deploy-aws-key').value = creds.aws_key;
        if (creds.aws_secret && document.getElementById('deploy-aws-secret')) document.getElementById('deploy-aws-secret').value = creds.aws_secret;
        if (creds.aws_region && document.getElementById('deploy-aws-region')) document.getElementById('deploy-aws-region').value = creds.aws_region;
        if (creds.aws_token && document.getElementById('deploy-aws-token')) document.getElementById('deploy-aws-token').value = creds.aws_token;
        if (creds.az_client_id && document.getElementById('deploy-az-client-id')) document.getElementById('deploy-az-client-id').value = creds.az_client_id;
        if (creds.az_client_secret && document.getElementById('deploy-az-client-secret')) document.getElementById('deploy-az-client-secret').value = creds.az_client_secret;
        if (creds.az_tenant_id && document.getElementById('deploy-az-tenant-id')) document.getElementById('deploy-az-tenant-id').value = creds.az_tenant_id;
        if (creds.az_sub_id && document.getElementById('deploy-az-subscription-id')) document.getElementById('deploy-az-subscription-id').value = creds.az_sub_id;
        if (creds.gcp_json && document.getElementById('deploy-gcp-json')) document.getElementById('deploy-gcp-json').value = creds.gcp_json;
    } catch (e) {}
}

async function testDeployCredentials() {
    const testBtn = document.getElementById('btn-test-credentials');
    const resultEl = document.getElementById('deploy-cred-test-result');
    if (!resultEl) return;

    saveDeployCredentialsToSession();
    const creds = getDeployCredentials();

    if (activeDeployProvider === 'aws' && (!creds.AWS_ACCESS_KEY_ID || !creds.AWS_SECRET_ACCESS_KEY)) {
        showToast("Please enter both AWS Access Key ID and Secret Access Key to test.", "warning");
        resultEl.style.display = 'block';
        resultEl.style.background = 'rgba(239, 68, 68, 0.15)';
        resultEl.style.border = '1px solid #ef4444';
        resultEl.style.color = '#fca5a5';
        resultEl.innerHTML = `<i class="fas fa-exclamation-circle"></i> <strong>Missing Credentials:</strong> Please enter your Access Key ID and Secret Key above before testing.`;
        return;
    }

    if (testBtn) {
        testBtn.disabled = true;
        testBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Testing...`;
    }

    resultEl.style.display = 'block';
    resultEl.style.background = 'rgba(56, 189, 248, 0.1)';
    resultEl.style.border = '1px solid #38bdf8';
    resultEl.style.color = '#7dd3fc';
    resultEl.innerHTML = `<i class="fas fa-circle-notch fa-spin"></i> Contacting ${activeDeployProvider.toUpperCase()} STS / Auth endpoint to verify caller identity...`;

    try {
        const res = await apiFetch('/api/credentials/test', {
            method: 'POST',
            body: JSON.stringify({
                provider: activeDeployProvider,
                credentials: creds
            })
        });
        const data = await res.json();
        const msg = (data.message || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        if (res.ok && data.success) {
            resultEl.style.background = 'rgba(16, 185, 129, 0.15)';
            resultEl.style.border = '1px solid #10b981';
            resultEl.style.color = '#6ee7b7';
            resultEl.innerHTML = `<i class="fas fa-check-circle" style="color: #10b981;"></i> <strong>Connection Verified:</strong> ${msg}`;
            showToast("Cloud credentials verified successfully!", "success");
        } else {
            resultEl.style.background = 'rgba(239, 68, 68, 0.15)';
            resultEl.style.border = '1px solid #ef4444';
            resultEl.style.color = '#fca5a5';
            const errCode = data.error_code ? `[${data.error_code}] ` : '';
            resultEl.innerHTML = `<i class="fas fa-times-circle" style="color: #ef4444;"></i> <strong>Authentication Failed:</strong> ${errCode}${msg || 'Credential validation failed'}`;
            showToast(data.message || "Credential validation failed", "error");
        }
    } catch (e) {
        resultEl.style.background = 'rgba(239, 68, 68, 0.15)';
        resultEl.style.border = '1px solid #ef4444';
        resultEl.style.color = '#fca5a5';
        const errMsg = (e.message || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        resultEl.innerHTML = `<i class="fas fa-exclamation-triangle" style="color: #ef4444;"></i> <strong>Error:</strong> Failed to reach server validator: ${errMsg}`;
    } finally {
        if (testBtn) {
            testBtn.disabled = false;
            testBtn.innerHTML = `<i class="fas fa-plug"></i> Test Connection`;
        }
    }
}

async function saveWorkspaceCredentials() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active project slug found", "error");

    saveDeployCredentialsToSession();
    const creds = getDeployCredentials();

    if (!Object.keys(creds).length) {
        return showToast("Please enter credentials into the fields first before saving to workspace", "warning");
    }

    try {
        const res = await apiFetch(`/api/projects/${slug}/credentials`, {
            method: 'POST',
            body: JSON.stringify({
                provider: activeDeployProvider,
                credentials: creds
            })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Credentials saved specifically for workspace '${slug}'!`, "success");
            await refreshWorkspaceCredentialBadge(slug);
        } else {
            showToast(data.detail || "Failed to save workspace credentials", "error");
        }
    } catch (e) {
        showToast("Error saving workspace credentials: " + e.message, "error");
    }
}

async function clearWorkspaceCredentials() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return;
    if (!confirm(`Are you sure you want to remove the saved credentials for workspace '${slug}'?`)) return;

    try {
        const res = await apiFetch(`/api/projects/${slug}/credentials`, { method: 'DELETE' });
        if (res.ok) {
            showToast("Saved credentials removed for workspace", "success");
            await refreshWorkspaceCredentialBadge(slug);
        }
    } catch (e) {
        showToast("Failed to delete credentials: " + e.message, "error");
    }
}

async function refreshWorkspaceCredentialBadge(slug) {
    const badgeEl = document.getElementById('deploy-vault-badge');
    const clearBtn = document.getElementById('btn-clear-credentials');
    if (!badgeEl) return;

    try {
        const res = await apiFetch(`/api/projects/${slug}/credentials`);
        const data = res.ok ? await res.json() : null;
        if (data && data.configured) {
            badgeEl.style.background = 'rgba(16, 185, 129, 0.15)';
            badgeEl.style.borderColor = '#10b981';
            badgeEl.style.color = '#6ee7b7';
            let detail = data.provider.toUpperCase();
            if (data.masked && data.masked.access_key) detail += ` (${data.masked.access_key})`;
            badgeEl.innerHTML = `<i class="fas fa-lock" style="color: #10b981;"></i> Saved for Workspace: <strong>${detail}</strong>`;
            if (clearBtn) clearBtn.style.display = 'inline-flex';
        } else {
            badgeEl.style.background = 'rgba(255,255,255,0.05)';
            badgeEl.style.borderColor = 'rgba(255,255,255,0.1)';
            badgeEl.style.color = '#94a3b8';
            badgeEl.innerHTML = `<i class="fas fa-shield-alt"></i> Not saved to workspace`;
            if (clearBtn) clearBtn.style.display = 'none';
        }
    } catch (e) {
        badgeEl.innerHTML = `<i class="fas fa-shield-alt"></i> Not saved to workspace`;
        if (clearBtn) clearBtn.style.display = 'none';
    }
}

async function loadDeploymentTab(slug) {
    const provisionView = document.getElementById('deploy-provision-view');
    const activeView = document.getElementById('deploy-active-view');
    const provisionActions = document.getElementById('deploy-provision-actions');
    const activeActions = document.getElementById('deploy-active-actions');
    const statusEl = document.getElementById('deploy-action-status');
    const terminalEl = document.getElementById('deploy-terminal-output');

    // Reset preflight result banner when loading tab
    const testResultEl = document.getElementById('deploy-cred-test-result');
    if (testResultEl) testResultEl.style.display = 'none';

    restoreDeployCredentialsFromSession();
    await refreshWorkspaceCredentialBadge(slug);
    await loadStatePosture(slug);

    // Attach real-time input listeners to persist credentials in sessionStorage
    ['deploy-aws-key', 'deploy-aws-secret', 'deploy-aws-region', 'deploy-aws-token', 
     'deploy-az-client-id', 'deploy-az-client-secret', 'deploy-az-tenant-id', 'deploy-az-subscription-id', 'deploy-gcp-json'].forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.dataset.hasSessionListener) {
            el.dataset.hasSessionListener = "true";
            el.addEventListener('input', saveDeployCredentialsToSession);
        }
    });

    if (statusEl) statusEl.innerText = 'Loading deployment status...';

    try {
        const res = await apiFetch(`/api/projects/${slug}/deployment-status`);
        const data = res.ok ? await res.json() : {};
        activeDeployData = data;

        const isDeployed = data.is_deployed || (currentProject && currentProject.status === 'deployed');
        if (isDeployed) {
            if (provisionView) provisionView.style.display = 'none';
            if (activeView) activeView.style.display = 'flex';
            if (provisionActions) provisionActions.style.display = 'none';
            if (activeActions) activeActions.style.display = 'flex';

            const providerEl = document.getElementById('deploy-active-provider');
            const timeEl = document.getElementById('deploy-active-time');
            const byEl = document.getElementById('deploy-active-by');
            const badgeEl = document.getElementById('deploy-status-badge');

            if (providerEl) providerEl.innerText = (data.detected_provider || 'aws').toUpperCase();
            if (timeEl) timeEl.innerText = data.deployed_at ? new Date(data.deployed_at).toLocaleString() : 'Active (Earlier Run)';
            if (byEl) byEl.innerText = data.deployed_by || (currentUser ? currentUser.username : 'Admin');
            if (badgeEl) {
                badgeEl.innerText = 'Live Deployed';
                badgeEl.className = 'status-badge status-deployed';
            }

            activeDeployLogType = 'apply';
            await loadDeployLog(slug, 'apply');
        } else {
            if (activeView) activeView.style.display = 'none';
            if (activeActions) activeActions.style.display = 'none';
            if (provisionView) provisionView.style.display = 'block';
            if (provisionActions) provisionActions.style.display = 'flex';

            // Auto-select tab matching detected provider
            const detected = data.detected_provider || 'aws';
            switchDeployCredTab(detected);

            // Pre-fill engine dropdown
            const engineSelect = document.getElementById('deploy-engine');
            if (engineSelect && currentProject && currentProject.engine) {
                engineSelect.value = currentProject.engine;
            }

            activeDeployLogType = 'plan';
            await loadDeployLog(slug, 'plan');
        }

        if (statusEl) statusEl.innerText = '';
    } catch (e) {
        console.error("Failed to load deployment status:", e);
        if (statusEl) statusEl.innerText = '';
    }
}

function switchDeployCredTab(provider) {
    activeDeployProvider = provider;
    ['aws', 'azure', 'gcp', 'local'].forEach(p => {
        const panel = document.getElementById(`deploy-cred-${p}`);
        const btn = document.getElementById(`btn-deploy-tab-${p}`);
        if (panel) panel.style.display = (p === provider) ? (p === 'gcp' ? 'block' : p === 'local' ? 'block' : 'grid') : 'none';
        if (btn) btn.classList.toggle('active', p === provider);
    });
    saveDeployCredentialsToSession();
}

// ─── Remote State & Security Transparency ───────────────────────
async function loadStatePosture(slug) {
    if (!slug) return;
    try {
        const res = await apiFetch(`/api/projects/${slug}/state-posture`);
        if (!res.ok) return;
        const data = await res.json();

        const storageEl = document.getElementById('posture-storage-type');
        const storageSub = document.getElementById('posture-backend-status-pill');
        const encEl = document.getElementById('posture-encryption');
        const lockEl = document.getElementById('posture-locking');
        const serialEl = document.getElementById('posture-serial');
        const verTag = document.getElementById('posture-version-tag');

        if (storageEl) storageEl.innerText = data.posture?.storage_type || 'Workspace Isolated Enclave';
        if (storageSub) {
            storageSub.innerText = data.posture?.is_remote 
                ? `● Remote Cloud Object Storage (${(data.backend?.type || 's3').toUpperCase()})` 
                : '● Enclave Isolated (.tfstate)';
            storageSub.style.color = data.posture?.is_remote ? '#c084fc' : '#38bdf8';
        }
        if (encEl) encEl.innerText = data.posture?.encryption || 'AES-256 (Server-Side)';
        if (lockEl) lockEl.innerText = data.posture?.locking || 'Active Mutex (.lock.hcl)';

        const serial = data.state_meta?.serial || 0;
        const resCount = data.state_meta?.resource_count || 0;
        if (serialEl) serialEl.innerText = `Serial #${serial} · ${resCount} Live Resources`;

        if (verTag) verTag.innerText = `● Terraform ${data.state_meta?.terraform_version || 'v1.14.8'}`;

        // Pre-fill inputs in configuration drawer
        const bucketInput = document.getElementById('remote-backend-bucket');
        const keyInput = document.getElementById('remote-backend-key');
        const regionInput = document.getElementById('remote-backend-region');
        const dynamoInput = document.getElementById('remote-backend-dynamo');

        if (bucketInput && data.backend?.bucket) bucketInput.value = data.backend.bucket;
        if (keyInput) keyInput.value = data.backend?.key || `workspaces/${slug}/terraform.tfstate`;
        if (regionInput && data.backend?.region) regionInput.value = data.backend.region;
        if (dynamoInput && data.backend?.dynamodb_table) dynamoInput.value = data.backend.dynamodb_table;
    } catch (e) {
        console.warn("Failed to load state posture:", e);
    }
}

function toggleBackendConfigDrawer() {
    const drawer = document.getElementById('backend-config-drawer');
    const label = document.getElementById('btn-toggle-backend-label');
    if (!drawer) return;
    const isHidden = (drawer.style.display === 'none' || !drawer.style.display);
    drawer.style.display = isHidden ? 'block' : 'none';
    if (label) label.innerText = isHidden ? 'Close Drawer' : 'Configure Remote Backend';
}

async function saveRemoteBackendConfig() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active workspace selected", "error");

    const bucket = document.getElementById('remote-backend-bucket')?.value?.trim();
    const key = document.getElementById('remote-backend-key')?.value?.trim() || `workspaces/${slug}/terraform.tfstate`;
    const region = document.getElementById('remote-backend-region')?.value?.trim() || 'us-east-1';
    const dynamodb_table = document.getElementById('remote-backend-dynamo')?.value?.trim();

    if (!bucket) {
        return showToast("Please specify an S3 bucket name.", "error");
    }

    const btn = document.getElementById('btn-save-remote-backend');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> <span>Injecting Backend...</span>`;
    }

    try {
        const res = await apiFetch(`/api/projects/${slug}/backend`, {
            method: 'POST',
            body: JSON.stringify({
                backend_type: 's3',
                bucket,
                key,
                region,
                dynamodb_table
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to configure backend");
        }

        const data = await res.json();
        showToast(data.message || "Remote S3 backend successfully configured!", "success");
        toggleBackendConfigDrawer();
        await loadStatePosture(slug);
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-check"></i> <span>Apply & Inject Backend HCL</span>`;
        }
    }
}

async function switchDeployLogType(type) {
    activeDeployLogType = type;
    ['apply', 'plan', 'destroy'].forEach(t => {
        const btn = document.getElementById(`btn-log-${t}`);
        if (btn) btn.classList.toggle('active', t === type);
    });
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (slug) {
        await loadDeployLog(slug, type);
    }
}

async function loadDeployLog(slug, logType) {
    const terminalEl = document.getElementById('deploy-terminal-output');
    if (!terminalEl) return;
    try {
        const engine = document.getElementById('deploy-engine')?.value || (currentProject && currentProject.engine) || 'terraform';
        const res = await apiFetch(`/api/projects/${slug}/logs/${engine}_${logType}`);
        const data = await res.json();
        if (data && data.content && data.content !== "No logs available.") {
            terminalEl.innerText = data.content;
        } else {
            // Fallback to generic log_type
            const altRes = await apiFetch(`/api/projects/${slug}/logs/terraform_${logType}`);
            const altData = await altRes.json();
            terminalEl.innerText = altData.content || `No ${logType} logs available for this workspace.`;
        }
    } catch (e) {
        terminalEl.innerText = `No ${logType} logs recorded yet.`;
    }
}

function copyDeployLog() {
    const terminalEl = document.getElementById('deploy-terminal-output');
    if (terminalEl && terminalEl.innerText) {
        navigator.clipboard.writeText(terminalEl.innerText).then(() => {
            showToast("Log copied to clipboard!", "success");
        }).catch(() => {
            showToast("Failed to copy log", "error");
        });
    }
}

async function submitLiveDeploy(action) {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active project slug found", "error");

    const planBtn = document.getElementById('btn-deploy-plan');
    const applyBtn = document.getElementById('btn-deploy-apply');
    const statusEl = document.getElementById('deploy-action-status');
    const terminalEl = document.getElementById('deploy-terminal-output');
    const engine = document.getElementById('deploy-engine')?.value || (currentProject && currentProject.engine) || 'terraform';

    // Collect credentials dynamically from active inputs and save to session
    saveDeployCredentialsToSession();
    const credentials = getDeployCredentials();

    const actionTitle = action === 'apply' ? 'Deployment (terraform apply)' : 'Plan (terraform plan)';
    if (planBtn) planBtn.disabled = true;
    if (applyBtn) applyBtn.disabled = true;
    if (statusEl) statusEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Executing ${actionTitle}...`;
    if (terminalEl) terminalEl.innerText = `⏳ Initializing ${engine} and running ${action} on workspace '${slug}'...\nPlease wait, this may take a few moments.\n`;

    try {
        const res = await apiFetch(`/api/projects/${slug}/deploy`, {
            method: 'POST',
            body: JSON.stringify({
                action: action,
                engine: engine,
                credentials: credentials
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Execution failed with status ${res.status}`);

        const stdout = data.stdout || '';
        const stderr = data.stderr || '';
        const combined = `=== Execution Result (${engine} ${action}) ===\nExit Code: ${data.exit_code}\n\nSTDOUT:\n${stdout}\n\nSTDERR:\n${stderr}`;
        if (terminalEl) terminalEl.innerText = combined;

        if (data.success) {
            showToast(`${action === 'apply' ? '🚀 Infrastructure successfully deployed!' : '✅ Plan generated successfully!'}`, 'success');
            if (statusEl) statusEl.innerText = `Completed successfully (Exit Code: 0)`;
            if (action === 'apply') {
                await loadDeploymentTab(slug);
                await fetchProjects();
            }
        } else {
            showToast(`${actionTitle} failed. Inspect terminal output.`, 'error');
            if (statusEl) statusEl.innerText = `Failed (Exit Code: ${data.exit_code})`;
        }
    } catch (err) {
        showToast(err.message, 'error');
        if (statusEl) statusEl.innerText = `Error: ${err.message}`;
        if (terminalEl) terminalEl.innerText += `\n❌ Error: ${err.message}`;
    } finally {
        if (planBtn) planBtn.disabled = false;
        if (applyBtn) applyBtn.disabled = false;
    }
}

async function submitLiveDestroy() {
    const slug = (currentProject && currentProject.slug) || document.getElementById('modal-project-slug')?.innerText?.trim();
    if (!slug) return showToast("No active project slug found", "error");

    // Collect credentials dynamically from active inputs
    saveDeployCredentialsToSession();
    const credentials = getDeployCredentials();
    const engine = document.getElementById('deploy-engine')?.value || (currentProject && currentProject.engine) || 'terraform';

    let credNotice = "";
    if (credentials.AWS_ACCESS_KEY_ID || credentials.ARM_CLIENT_ID || credentials.GOOGLE_CREDENTIALS) {
        credNotice = `\n\n🔑 Using active credentials supplied in the Cloud Provider Credentials panel.`;
    } else {
        credNotice = `\n\n⚠️ NOTE: The Access Key & Secret Key fields above are currently blank.\nIf this workspace requires your IAM credentials, please fill in your Access Key and Secret Key in the Cloud Provider Credentials section above before proceeding.`;
    }

    if (!confirm(`⚠️ ARE YOU SURE?\n\nThis will permanently destroy and remove all cloud resources managed by workspace "${slug}".\n\nThis action CANNOT be undone.${credNotice}`)) {
        return;
    }

    const statusEl = document.getElementById('deploy-action-status');
    const terminalEl = document.getElementById('deploy-terminal-output');

    if (statusEl) statusEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Destroying infrastructure...`;
    if (terminalEl) terminalEl.innerText = `🧹 Executing ${engine} destroy on workspace '${slug}'...\n`;

    try {
        const res = await apiFetch(`/api/projects/${slug}/destroy`, {
            method: 'POST',
            body: JSON.stringify({
                engine: engine,
                credentials: credentials
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Destroy failed with status ${res.status}`);

        const stdout = data.stdout || '';
        const stderr = data.stderr || '';
        if (terminalEl) terminalEl.innerText = `=== Destroy Result (${engine}) ===\nExit Code: ${data.exit_code}\n\nSTDOUT:\n${stdout}\n\nSTDERR:\n${stderr}`;

        if (data.success) {
            showToast("Infrastructure successfully destroyed.", "success");
            if (statusEl) statusEl.innerText = "Destroyed";
            await loadDeploymentTab(slug);
            await fetchProjects();
        } else {
            showToast("Destroy command returned errors. Check output.", "error");
            if (statusEl) statusEl.innerText = `Destroy failed (Exit Code: ${data.exit_code})`;
        }
    } catch (err) {
        showToast(err.message, 'error');
        if (statusEl) statusEl.innerText = `Error: ${err.message}`;
        if (terminalEl) terminalEl.innerText += `\n❌ Error: ${err.message}`;
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

// ════════════════════════════════════════════════════════════════════════
// ── Phase 12: Executive Analytics & Observability Handlers ─────────────
// ════════════════════════════════════════════════════════════════════════

async function loadExecutiveAnalytics() {
    try {
        const url = activeOrgId ? `/api/analytics/executive?org_id=${activeOrgId}` : '/api/analytics/executive';
        const res = await apiFetch(url);
        const data = await res.json();
        const kpis = data.kpis || {};

        document.getElementById('analytics-kpi-success-rate').innerText = `${kpis.success_rate_percent || 0}%`;
        document.getElementById('analytics-kpi-savings').innerText = `$${kpis.estimated_financial_savings_usd || 0}`;
        document.getElementById('analytics-kpi-monthly-spend').innerText = `$${kpis.total_monthly_spend || 0}`;
        document.getElementById('analytics-kpi-healing-rounds').innerText = `${kpis.total_self_healing_rounds || 0} (${kpis.estimated_engineering_hours_saved || 0} hrs saved)`;

        if (kpis.savings_breakdown) {
            const savingsNote = document.getElementById('analytics-kpi-savings-note');
            if (savingsNote && kpis.savings_breakdown.formula) {
                savingsNote.innerText = `${kpis.savings_breakdown.formula}`;
            }
            const healingNote = document.getElementById('analytics-kpi-healing-note');
            if (healingNote && kpis.savings_breakdown.baseline_generation_hours !== undefined) {
                healingNote.innerText = `${kpis.savings_breakdown.baseline_generation_hours}h gen + ${kpis.savings_breakdown.self_healing_hours}h healing`;
            }
        }

        // Render Failure Taxonomy
        const taxContainer = document.getElementById('analytics-failure-taxonomy');
        const tax = data.failure_taxonomy || {};
        const entries = Object.entries(tax);
        if (entries.length === 0 || (entries.length === 1 && entries[0][0] === 'None')) {
            taxContainer.innerHTML = `<p class="text-muted" style="padding: 1rem 0;">🎉 Zero runtime failures recorded across workspaces!</p>`;
        } else {
            const maxVal = Math.max(...entries.map(e => e[1]));
            taxContainer.innerHTML = entries.map(([category, count]) => {
                const pct = Math.max(8, Math.round((count / maxVal) * 100));
                return `
                <div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                        <span style="color: #cbd5e1; font-weight: 500;">${category}</span>
                        <span style="color: #f87171; font-weight: 600;">${count} events</span>
                    </div>
                    <div style="background: rgba(255,255,255,0.05); height: 8px; border-radius: 4px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #f87171, #ef4444); width: ${pct}%; height: 100%;"></div>
                    </div>
                </div>
                `;
            }).join('');
        }

        // Render Pattern Memory Leaderboard
        const leadContainer = document.getElementById('analytics-pattern-leaderboard');
        const patterns = data.pattern_leaderboard || [];
        if (patterns.length === 0) {
            leadContainer.innerHTML = `<p class="text-muted" style="padding: 1rem 0;">No pattern memory records found.</p>`;
        } else {
            leadContainer.innerHTML = `
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--border-color); color: #888;">
                        <th style="padding: 0.4rem;">Error Signature</th>
                        <th style="padding: 0.4rem;">Confidence</th>
                        <th style="padding: 0.4rem;">Successes</th>
                        <th style="padding: 0.4rem;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${patterns.map(p => `
                        <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
                            <td style="padding: 0.5rem 0.4rem; font-family: monospace; color: #a5b4fc;">${p.signature}</td>
                            <td style="padding: 0.5rem 0.4rem;">
                                <div style="display: flex; align-items: center; gap: 0.4rem;">
                                    <div style="background: rgba(255,255,255,0.08); width: 50px; height: 6px; border-radius: 3px; overflow: hidden;">
                                        <div style="background: #10b981; width: ${p.confidence_percent}%; height: 100%;"></div>
                                    </div>
                                    <span style="font-weight: 600; color: #fff;">${p.confidence_percent}%</span>
                                </div>
                            </td>
                            <td style="padding: 0.5rem 0.4rem; color: #cbd5e1;">${p.success_count}</td>
                            <td style="padding: 0.5rem 0.4rem;"><span class="status-badge" style="background: ${p.status === 'trusted' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)'}; color: ${p.status === 'trusted' ? '#34d399' : '#fbbf24'}; font-size: 0.7rem;">${p.status}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            `;
        }
    } catch (e) {
        console.error("Failed to load executive analytics", e);
    }
}

// ════════════════════════════════════════════════════════════════════════
// ── Phase 12: Billing & Usage Metering Handlers ────────────────────────
// ════════════════════════════════════════════════════════════════════════

let currentSubscription = null;

async function loadBillingInfo() {
    try {
        const url = activeOrgId ? `/api/billing/subscription?org_id=${activeOrgId}` : '/api/billing/subscription';
        const res = await apiFetch(url);
        const data = await res.json();
        const sub = data.subscription || {};
        const plans = data.plans || {};
        const statement = data.current_statement || {};
        const consumption = statement.consumption || {};

        currentSubscription = sub;

        const planMeta = plans[sub.plan] || { name: sub.plan, price_monthly: 0, monthly_runs: 5, features: [] };

        document.getElementById('billing-current-plan-name').innerText = planMeta.name;
        document.getElementById('billing-monthly-price').innerHTML = `$${planMeta.price_monthly}<span style="font-size: 1rem; color: #aaa;">/mo</span>`;
        document.getElementById('billing-plan-description').innerText = planMeta.features[0] || "Active subscription tier.";
        
        const badge = document.getElementById('billing-status-badge');
        if (sub.cancel_at_period_end) {
            badge.innerText = "CANCELS AT PERIOD END";
            badge.style.background = "rgba(245, 158, 11, 0.2)";
            badge.style.color = "#fbbf24";
            badge.style.border = "1px solid #f59e0b";
        } else {
            badge.innerText = (sub.status || "ACTIVE").toUpperCase();
            badge.style.background = "";
            badge.style.color = "";
            badge.style.border = "";
        }

        // Quota Bar & Remaining Runs
        const used = sub.runs_this_month || 0;
        const limit = sub.monthly_limit;
        const runsRemaining = limit === -1 ? 'Unlimited' : Math.max(0, limit - used);

        if (limit === -1) {
            document.getElementById('billing-quota-text').innerText = `${used} Runs (Unlimited Capacity)`;
            document.getElementById('billing-quota-bar').style.width = "100%";
        } else {
            const pct = Math.min(100, Math.round((used / limit) * 100));
            document.getElementById('billing-quota-text').innerText = `${used} / ${limit} Runs Used`;
            document.getElementById('billing-quota-bar').style.width = `${pct}%`;
        }

        // Customer Value Metrics
        const runsRemEl = document.getElementById('billing-runs-remaining');
        if (runsRemEl) runsRemEl.innerText = limit === -1 ? 'Unlimited' : `${runsRemaining} Runs`;

        const hoursSavedEl = document.getElementById('billing-hours-saved');
        if (hoursSavedEl) {
            const saved = (used * 4.5).toFixed(1);
            hoursSavedEl.innerText = `${saved} hrs`;
        }

        const infraSpendEl = document.getElementById('billing-infra-spend');
        if (infraSpendEl) infraSpendEl.innerText = `$${consumption.infra_projected_spend_usd || '0.00'}`;

        // Recent Workspace Runs (Clean, customer-facing table without backend tokens or platform cost)
        const projMap = {};
        if (Array.isArray(allProjects)) {
            allProjects.forEach(p => { if (p && p.slug) projMap[p.slug] = p; });
        }

        const tbody = document.getElementById('billing-runs-tbody');
        const runs = statement.recent_runs || [];
        if (runs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 1.5rem; color: #888;">No workspace execution records logged yet for this period.</td></tr>`;
        } else {
            tbody.innerHTML = runs.map(r => {
                const proj = projMap[r.project_slug] || {};
                const isTofu = (proj.engine === 'opentofu');
                const engineBadge = isTofu 
                    ? `<span style="font-size: 0.78rem; background: rgba(245, 158, 11, 0.15); color: #fbbf24; padding: 2px 7px; border-radius: 4px; font-weight: 600;">🧅 OpenTofu</span>`
                    : `<span style="font-size: 0.78rem; background: rgba(168, 85, 247, 0.15); color: #c084fc; padding: 2px 7px; border-radius: 4px; font-weight: 600;">🟣 Terraform</span>`;
                const statusName = proj.status ? proj.status.toUpperCase() : 'COMPLETED';
                const statusClass = (proj.status === 'deployed') ? 'status-deployed' : (proj.status === 'failed' ? 'status-failed' : 'status-generating');
                const estCost = proj.estimated_cost !== undefined ? `$${proj.estimated_cost}/mo` : '$0.00/mo';

                return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
                    <td style="padding: 0.5rem; color: #888; font-family: monospace;">${r.created_at ? r.created_at.substring(0, 16).replace('T', ' ') : '-'}</td>
                    <td style="padding: 0.5rem; font-family: monospace; color: #a5b4fc; font-weight: 500;">${r.project_slug}</td>
                    <td style="padding: 0.5rem; color: #cbd5e1;">${engineBadge}</td>
                    <td style="padding: 0.5rem;"><span class="status-badge ${statusClass}" style="font-size: 0.72rem; padding: 2px 7px;">${statusName}</span></td>
                    <td style="padding: 0.5rem; color: #38bdf8; font-weight: 500;">${estCost}</td>
                </tr>
                `;
            }).join('');
        }

        // Admin-Only: Internal Cost & Token Economics (COGS)
        const adminPanel = document.getElementById('billing-admin-cogs-panel');
        if (adminPanel) {
            const isSuper = !!(currentUser && currentUser.is_superuser);
            adminPanel.style.display = isSuper ? 'block' : 'none';
            if (isSuper) {
                const tokensEl = document.getElementById('billing-total-tokens');
                if (tokensEl) tokensEl.innerText = (consumption.total_tokens || 0).toLocaleString();
                const aiCostEl = document.getElementById('billing-ai-cost');
                if (aiCostEl) aiCostEl.innerText = `Est. Raw AI Cost: $${consumption.ai_cost_incurred_usd || 0}`;
                const compSecEl = document.getElementById('billing-compute-seconds');
                if (compSecEl) compSecEl.innerText = `${consumption.compute_seconds || 0}s`;
                const compCostEl = document.getElementById('billing-compute-cost');
                if (compCostEl) compCostEl.innerText = `Internal Compute Fee: $${consumption.compute_cost_incurred_usd || 0}`;
            }
        }
    } catch (e) {
        console.error("Failed to load billing info", e);
    }
}

let currentPaymentGateway = 'razorpay';

function selectPaymentGateway(gw) {
    currentPaymentGateway = gw;
    const rzpBtn = document.getElementById('gateway-btn-razorpay');
    const strBtn = document.getElementById('gateway-btn-stripe');
    if (gw === 'razorpay') {
        if (rzpBtn) {
            rzpBtn.style.background = 'rgba(59, 130, 246, 0.2)';
            rzpBtn.style.borderColor = '#3b82f6';
            rzpBtn.style.color = '#93c5fd';
        }
        if (strBtn) {
            strBtn.style.background = 'rgba(255, 255, 255, 0.05)';
            strBtn.style.borderColor = 'var(--border-color)';
            strBtn.style.color = '#ccc';
        }
    } else {
        if (strBtn) {
            strBtn.style.background = 'rgba(99, 102, 241, 0.2)';
            strBtn.style.borderColor = '#6366f1';
            strBtn.style.color = '#a5b4fc';
        }
        if (rzpBtn) {
            rzpBtn.style.background = 'rgba(255, 255, 255, 0.05)';
            rzpBtn.style.borderColor = 'var(--border-color)';
            rzpBtn.style.color = '#ccc';
        }
    }
}

function openUpgradeModal() {
    const modal = document.getElementById('modal-upgrade-plan');
    if (modal) modal.style.display = 'flex';
}

async function confirmDowngrade(cancelAtPeriodEnd) {
    try {
        const payload = { cancel_at_period_end: cancelAtPeriodEnd };
        if (activeOrgId) payload.org_id = activeOrgId;
        const res = await apiFetch('/api/billing/downgrade', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update subscription");

        showToast(data.message || "Subscription updated successfully", "success");
        closeModal('modal-downgrade-confirm');
        closeModal('modal-upgrade-plan');
        await loadBillingInfo();
    } catch (err) {
        showToast(err.message || "Downgrade failed", "error");
    }
}

async function upgradeSubscription(planId) {
    if (planId === 'free') {
        // If user already on paid plan, warn before downgrading
        if (currentSubscription && currentSubscription.plan && currentSubscription.plan !== 'free') {
            const currentPlanName = (currentSubscription.plan || 'PRO').toUpperCase();
            const remaining = currentSubscription.remaining_runs !== undefined ? currentSubscription.remaining_runs : '0';
            const limit = currentSubscription.monthly_limit || 100;
            const paidUntil = currentSubscription.paid_until ? new Date(currentSubscription.paid_until).toLocaleDateString() : 'End of period';

            const summaryElem = document.getElementById('downgrade-summary-text');
            if (summaryElem) {
                summaryElem.innerText = `You are currently subscribed to the ${currentPlanName} plan with ${remaining} remaining runs out of ${limit}.`;
            }
            const planElem = document.getElementById('downgrade-current-plan');
            if (planElem) planElem.innerText = currentPlanName;
            const remElem = document.getElementById('downgrade-remaining-runs');
            if (remElem) remElem.innerText = `${remaining} runs remaining`;
            const untilElem = document.getElementById('downgrade-paid-until');
            if (untilElem) untilElem.innerText = paidUntil;

            const modal = document.getElementById('modal-downgrade-confirm');
            if (modal) modal.style.display = 'flex';
            return;
        }

        if (currentSubscription && currentSubscription.plan === 'free') {
            showToast("You are already on the Free tier.", "info");
            return;
        }

        try {
            const payload = { plan: 'free', gateway: currentPaymentGateway };
            if (activeOrgId) payload.org_id = activeOrgId;
            const res = await apiFetch('/api/billing/upgrade', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            showToast("Subscribed to Free Tier", "success");
            closeModal('modal-upgrade-plan');
            await loadBillingInfo();
        } catch (e) {
            showToast(e.message, "error");
        }
        return;
    }

    if (currentPaymentGateway === 'razorpay') {
        // Razorpay Checkout flow
        try {
            const payload = { plan: planId, currency: 'INR' };
            if (activeOrgId) payload.org_id = activeOrgId;
            const res = await apiFetch('/api/billing/razorpay/create-order', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            const orderData = await res.json();
            if (!res.ok) throw new Error(orderData.detail || "Failed to create Razorpay order");

            // Anti-Double-Charging Check: If user already paid for this plan and entitlement is valid, restore immediately
            if (orderData.already_paid || orderData.restored) {
                showToast(orderData.message || `Restored your ${planId.toUpperCase()} plan without charge!`, "success");
                closeModal('modal-upgrade-plan');
                await loadBillingInfo();
                return;
            }

            if (typeof Razorpay === 'undefined') {
                throw new Error("Razorpay Checkout SDK is not loaded. Please disable ad-blockers or check your connection.");
            }

            if (orderData.simulated) {
                const confirmed = confirm(`Razorpay Simulation Mode: No active API keys configured. Confirm simulated test payment to upgrade to ${planId.toUpperCase()}?`);
                if (!confirmed) return;

                // Verification in simulation / local testing mode
                const verifyRes = await apiFetch('/api/billing/razorpay/verify', {
                    method: 'POST',
                    body: JSON.stringify({
                        razorpay_order_id: orderData.order_id,
                        razorpay_payment_id: `pay_sim_${Date.now()}`,
                        razorpay_signature: "simulated_valid_sig",
                        plan: planId,
                        org_id: activeOrgId
                    })
                });
                const verifyData = await verifyRes.json();
                showToast(verifyData.message || `Upgraded to ${planId.toUpperCase()}!`, "success");
                closeModal('modal-upgrade-plan');
                await loadBillingInfo();
                return;
            }

            // Live Razorpay standard modal
            const options = {
                key: orderData.key_id,
                amount: orderData.amount,
                currency: orderData.currency,
                name: "Terraform AI Agent",
                description: `Upgrade to ${orderData.plan_name}`,
                order_id: orderData.order_id,
                handler: async function (response) {
                    try {
                        const verifyRes = await apiFetch('/api/billing/razorpay/verify', {
                            method: 'POST',
                            body: JSON.stringify({
                                razorpay_order_id: response.razorpay_order_id,
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_signature: response.razorpay_signature,
                                plan: planId,
                                org_id: activeOrgId
                            })
                        });
                        const verifyData = await verifyRes.json();
                        showToast(verifyData.message || "Payment Successful & Verified!", "success");
                        closeModal('modal-upgrade-plan');
                        await loadBillingInfo();
                    } catch (err) {
                        showToast(err.message || "Payment verification failed", "error");
                    }
                },
                prefill: {
                    name: currentUser ? currentUser.username : "Developer",
                    email: currentUser ? currentUser.email : "user@example.com"
                },
                theme: {
                    color: "#6366f1"
                }
            };
            const rzp = new Razorpay(options);
            rzp.open();
        } catch (e) {
            showToast(e.message, "error");
        }
    } else {
        // Stripe flow
        try {
            const payload = { plan: planId, gateway: 'stripe' };
            if (activeOrgId) payload.org_id = activeOrgId;
            const res = await apiFetch('/api/billing/upgrade', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Upgrade request failed");

            // Anti-Double-Charging Check: If restored
            if (data.already_paid || data.restored) {
                showToast(data.message || `Restored your ${planId.toUpperCase()} plan without charge!`, "success");
                closeModal('modal-upgrade-plan');
                await loadBillingInfo();
                return;
            }

            if (data.checkout_url && !data.simulated) {
                window.location.href = data.checkout_url;
            } else {
                showToast(data.message || `Successfully upgraded to ${planId.toUpperCase()} tier!`, "success");
                closeModal('modal-upgrade-plan');
                await loadBillingInfo();
            }
        } catch (e) {
            showToast(e.message, "error");
        }
    }
}

// ════════════════════════════════════════════════════════════════════════
// ── Phase 12: Compliance & Audit Package Export ────────────────────────
// ════════════════════════════════════════════════════════════════════════

async function exportCompliancePackage(format = 'json') {
    try {
        const url = activeOrgId ? `/api/compliance/export?org_id=${activeOrgId}&format=${format}` : `/api/compliance/export?format=${format}`;
        const res = await apiFetch(url);
        if (!res.ok) throw new Error("Failed to export compliance package");

        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = format === 'csv' ? 'soc2_compliance_audit_trail.csv' : 'soc2_compliance_package.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast(`Compliance package exported as ${format.toUpperCase()}`, "success");
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ─── Boot ───────────────────────────────────────────────────────
init();

