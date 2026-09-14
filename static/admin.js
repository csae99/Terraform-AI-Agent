// ════════════════════════════════════════════════════════════════════════
// ── Super-Admin Platform Operations Console Logic ──────────────────────
// ════════════════════════════════════════════════════════════════════════

let allUsers = [];
let allOrgs = [];
let allAuditLogs = [];

document.addEventListener('DOMContentLoaded', async () => {
    await checkAdminAuth();
    await loadOverview();
});

// ─── Authentication & Identity ──────────────────────────────────────────
async function checkAdminAuth() {
    try {
        const res = await fetch('/api/auth/me');
        if (!res.ok) {
            window.location.href = '/login?next=/admin';
            return;
        }
        const user = await res.json();
        if (!user.is_superuser) {
            alert("Access Denied: Super-Admin privileges required.");
            window.location.href = '/';
            return;
        }
        document.getElementById('admin-user-pill').innerHTML = `<i class="fas fa-shield-alt"></i> ${user.username} (Super-Admin)`;
    } catch (e) {
        console.error("Auth check failed:", e);
    }
}

// ─── Tab Switching ──────────────────────────────────────────────────────
function switchAdminTab(tab) {
    document.querySelectorAll('.admin-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.admin-view').forEach(v => v.classList.remove('active'));

    const btn = document.getElementById(`tab-${tab}`);
    const view = document.getElementById(`view-${tab}`);
    if (btn) btn.classList.add('active');
    if (view) view.classList.add('active');

    if (tab === 'overview') loadOverview();
    else if (tab === 'users') loadUsers();
    else if (tab === 'orgs') loadOrgs();
    else if (tab === 'llm') loadLLMMetrics();
    else if (tab === 'k8s') loadK8sFleet();
    else if (tab === 'audit') loadAuditLogs();
}

function refreshAdminData() {
    const activeTab = document.querySelector('.admin-tab-btn.active');
    const tabName = activeTab ? activeTab.id.replace('tab-', '') : 'overview';
    switchAdminTab(tabName);
    showToast("Dashboard refreshed", "info");
}

// ─── Toast Notifications ────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle';
    toast.innerHTML = `<i class="fas fa-${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ─── Modal Helpers ──────────────────────────────────────────────────────
function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = 'none';
}

// ─── 1. Overview & Vitals ───────────────────────────────────────────────
async function loadOverview() {
    try {
        const res = await fetch('/api/admin/overview');
        if (!res.ok) throw new Error("Failed to load overview");
        const data = await res.json();

        // Populate Vitals
        document.getElementById('vital-total-users').innerText = data.tenants.total_users;
        document.getElementById('vital-active-users').innerText = `${data.tenants.active_users} Active`;
        document.getElementById('vital-total-orgs').innerText = data.tenants.total_orgs;
        document.getElementById('vital-total-projects').innerText = data.workspaces.total_projects;
        document.getElementById('vital-deployed-projects').innerText = `${data.workspaces.deployed_projects} Deployed`;
        document.getElementById('vital-total-mrr').innerText = `$${data.economics.estimated_mrr}`;
        document.getElementById('vital-plan-breakdown').innerText = `${data.economics.plan_distribution.pro || 0} Pro / ${data.economics.plan_distribution.enterprise || 0} Ent`;
        document.getElementById('vital-total-tokens').innerText = (data.economics.total_tokens || 0).toLocaleString();
        document.getElementById('vital-total-ai-cost').innerText = `Est. Spend: $${data.economics.total_infra_cost || 0}`;
        document.getElementById('vital-k8s-status').innerText = data.vitals.k8s_operator.toUpperCase();
        document.getElementById('vital-redis-status').innerText = `Redis: ${data.vitals.redis.toUpperCase()}`;

        // Plan distribution breakdown
        const planList = document.getElementById('plan-distribution-list');
        if (planList) {
            const dist = data.economics.plan_distribution;
            planList.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #cbd5e1;"><i class="fas fa-circle" style="color: #64748b; font-size: 0.6rem; margin-right: 0.5rem;"></i> Free Tier</span>
                    <strong style="color: #fff;">${dist.free || 0} accounts</strong>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #cbd5e1;"><i class="fas fa-circle" style="color: #3b82f6; font-size: 0.6rem; margin-right: 0.5rem;"></i> Pro Developer ($29/mo)</span>
                    <strong style="color: #38bdf8;">${dist.pro || 0} accounts</strong>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #cbd5e1;"><i class="fas fa-circle" style="color: #a855f7; font-size: 0.6rem; margin-right: 0.5rem;"></i> Enterprise Team ($199/mo)</span>
                    <strong style="color: #c084fc;">${dist.enterprise || 0} accounts</strong>
                </div>
            `;
        }
    } catch (e) {
        console.error("Overview error:", e);
    }
}

// ─── 2. Users & Tenants ─────────────────────────────────────────────────
async function loadUsers() {
    try {
        const res = await fetch('/api/admin/tenants/users');
        if (!res.ok) throw new Error("Failed to load users");
        allUsers = await res.json();
        renderUsersTable(allUsers);
    } catch (e) {
        showToast(e.message, "error");
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('users-tbody');
    if (!tbody) return;
    if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #888; padding: 2rem;">No users found.</td></tr>`;
        return;
    }
    tbody.innerHTML = users.map(u => {
        const isSuper = u.is_superuser;
        const isSuspended = u.status === 'suspended';
        return `
            <tr>
                <td>#${u.id}</td>
                <td><strong>${escapeHtml(u.username)}</strong><br><small style="color: #64748b;">${escapeHtml(u.email || 'No email')}</small></td>
                <td>
                    <span class="status-badge" style="background: ${isSuper ? 'rgba(239,68,68,0.2)' : 'rgba(100,116,139,0.2)'}; color: ${isSuper ? '#f87171' : '#cbd5e1'};">
                        ${isSuper ? 'Super-Admin' : 'Standard'}
                    </span>
                </td>
                <td>
                    <span class="status-badge" style="background: ${isSuspended ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}; color: ${isSuspended ? '#f87171' : '#34d399'};">
                        ${u.status.toUpperCase()}
                    </span>
                </td>
                <td><span style="text-transform: capitalize; font-weight: 600;">${u.plan}</span></td>
                <td>${u.runs_this_month} / ${u.monthly_limit === -1 ? '∞' : u.monthly_limit}</td>
                <td style="color: #64748b; font-size: 0.8rem;">${u.created_at ? u.created_at.substring(0, 10) : '-'}</td>
                <td>
                    <div style="display: flex; gap: 0.4rem;">
                        <button class="action-btn-sm ${isSuspended ? 'btn-activate' : 'btn-suspend'}" onclick="toggleUserStatus(${u.id}, '${u.status}')">
                            <i class="fas fa-${isSuspended ? 'check' : 'ban'}"></i> ${isSuspended ? 'Activate' : 'Suspend'}
                        </button>
                        <button class="action-btn-sm btn-plan" onclick="toggleUserAdmin(${u.id}, ${isSuper})">
                            <i class="fas fa-shield-alt"></i> ${isSuper ? 'Demote' : 'Make Admin'}
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function filterUsersTable() {
    const q = document.getElementById('search-users').value.toLowerCase();
    const filtered = allUsers.filter(u => 
        u.username.toLowerCase().includes(q) || (u.email && u.email.toLowerCase().includes(q))
    );
    renderUsersTable(filtered);
}

async function toggleUserStatus(userId, currentStatus) {
    const newStatus = currentStatus === 'suspended' ? 'active' : 'suspended';
    if (!confirm(`Are you sure you want to change user #${userId} to ${newStatus}?`)) return;
    try {
        const res = await fetch(`/api/admin/tenants/users/${userId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update user status");
        showToast(data.message, "success");
        await loadUsers();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function toggleUserAdmin(userId, currentIsSuper) {
    const newSuper = !currentIsSuper;
    const actionName = newSuper ? "promote to Super-Admin" : "demote to Standard User";
    if (!confirm(`Are you sure you want to ${actionName} for user #${userId}?`)) return;
    try {
        const res = await fetch(`/api/admin/tenants/users/${userId}/role`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_superuser: newSuper })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update admin role");
        showToast(data.message, "success");
        await loadUsers();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ─── 3. Organizations & Plans ───────────────────────────────────────────
async function loadOrgs() {
    try {
        const res = await fetch('/api/admin/tenants/orgs');
        if (!res.ok) throw new Error("Failed to load organizations");
        allOrgs = await res.json();
        renderOrgsTable(allOrgs);
    } catch (e) {
        showToast(e.message, "error");
    }
}

function renderOrgsTable(orgs) {
    const tbody = document.getElementById('orgs-tbody');
    if (!tbody) return;
    if (orgs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #888; padding: 2rem;">No organizations recorded.</td></tr>`;
        return;
    }
    tbody.innerHTML = orgs.map(o => `
        <tr>
            <td>#${o.id}</td>
            <td><strong>${escapeHtml(o.name)}</strong></td>
            <td><code style="color: #a5b4fc; background: rgba(99,102,241,0.1); padding: 0.2rem 0.4rem; border-radius: 4px;">${escapeHtml(o.slug)}</code></td>
            <td>${escapeHtml(o.owner_name || 'ID ' + o.owner_id)}</td>
            <td><span class="nav-badge" style="background: rgba(255,255,255,0.08);">${o.member_count}</span></td>
            <td>
                <span class="status-badge" style="background: ${o.plan === 'enterprise' ? 'rgba(168,85,247,0.2)' : o.plan === 'pro' ? 'rgba(59,130,246,0.2)' : 'rgba(100,116,139,0.2)'}; color: ${o.plan === 'enterprise' ? '#c084fc' : o.plan === 'pro' ? '#60a5fa' : '#cbd5e1'};">
                    ${o.plan.toUpperCase()}
                </span>
            </td>
            <td>${o.runs_this_month} / ${o.monthly_limit === -1 ? 'Unlimited' : o.monthly_limit}</td>
            <td>
                <button class="action-btn-sm btn-plan" onclick="openOrgPlanModal(${o.id}, '${escapeHtml(o.name)}', '${o.plan}')">
                    <i class="fas fa-tag"></i> Set Plan
                </button>
            </td>
        </tr>
    `).join('');
}

function filterOrgsTable() {
    const q = document.getElementById('search-orgs').value.toLowerCase();
    const filtered = allOrgs.filter(o => 
        o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q)
    );
    renderOrgsTable(filtered);
}

function openOrgPlanModal(orgId, orgName, currentPlan) {
    document.getElementById('override-org-id').value = orgId;
    document.getElementById('override-org-name').innerText = `Organization: ${orgName} (#${orgId})`;
    document.getElementById('override-plan-select').value = currentPlan;
    document.getElementById('modal-override-plan').style.display = 'flex';
}

async function submitOrgPlanOverride() {
    const orgId = document.getElementById('override-org-id').value;
    const plan = document.getElementById('override-plan-select').value;
    try {
        const res = await fetch(`/api/admin/tenants/orgs/${orgId}/plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to override plan");
        showToast(data.message, "success");
        closeModal('modal-override-plan');
        await loadOrgs();
        await loadOverview();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ─── 4. LLM Economics ───────────────────────────────────────────────────
async function loadLLMMetrics() {
    try {
        const res = await fetch('/api/admin/llm/metrics');
        if (!res.ok) throw new Error("Failed to load LLM metrics");
        const data = await res.json();
        const tbody = document.getElementById('llm-records-tbody');
        if (!tbody) return;
        if (!data.recent_records || data.recent_records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #888; padding: 2rem;">No token consumption records logged yet.</td></tr>`;
            return;
        }
        tbody.innerHTML = data.recent_records.map(r => `
            <tr>
                <td>#${r.id}</td>
                <td>${r.org_id ? 'Org #' + r.org_id : 'Personal'}</td>
                <td><strong>${(r.tokens_used || 0).toLocaleString()}</strong></td>
                <td>$${(r.infra_cost || 0).toFixed(2)}</td>
                <td>${(r.run_time_seconds || 0).toFixed(1)}s</td>
            </tr>
        `).join('');
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ─── 5. K8s & Worker Fleet ──────────────────────────────────────────────
async function loadK8sFleet() {
    try {
        const res = await fetch('/api/admin/k8s/fleet');
        if (!res.ok) throw new Error("Failed to load K8s fleet");
        const data = await res.json();

        // CRD list
        const crdsContainer = document.getElementById('k8s-crds-list');
        if (crdsContainer) {
            crdsContainer.innerHTML = (data.crds || []).map(c => `
                <div style="background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.3); padding: 0.5rem 0.75rem; border-radius: 6px; font-size: 0.85rem; color: #93c5fd;">
                    <i class="fas fa-file-code"></i> ${c}
                </div>
            `).join('');
        }

        // Reconcile events
        const eventsTbody = document.getElementById('k8s-events-tbody');
        if (eventsTbody) {
            const events = data.recent_reconcile_events || [];
            if (events.length === 0) {
                eventsTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #888; padding: 2rem;">No reconciliation events recorded yet.</td></tr>`;
                return;
            }
            eventsTbody.innerHTML = events.map(ev => `
                <tr>
                    <td><span class="status-badge" style="background: ${ev.type === 'Warning' ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}; color: ${ev.type === 'Warning' ? '#f87171' : '#34d399'};">${ev.type}</span></td>
                    <td><strong>${escapeHtml(ev.reason)}</strong></td>
                    <td>${escapeHtml(ev.resource)}</td>
                    <td>${escapeHtml(ev.message)}</td>
                    <td style="color: #64748b; font-size: 0.8rem;">${escapeHtml(ev.timestamp)}</td>
                </tr>
            `).join('');
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ─── 6. Global Audit Vault ──────────────────────────────────────────────
async function loadAuditLogs() {
    try {
        const res = await fetch('/api/admin/audit/global?limit=100');
        if (!res.ok) throw new Error("Failed to load global audit logs");
        allAuditLogs = await res.json();
        renderAuditTable(allAuditLogs);
    } catch (e) {
        showToast(e.message, "error");
    }
}

function renderAuditTable(logs) {
    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;
    if (logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #888; padding: 2rem;">No audit logs recorded.</td></tr>`;
        return;
    }
    tbody.innerHTML = logs.map(l => `
        <tr>
            <td style="color: #64748b; font-size: 0.8rem;">${l.created_at ? l.created_at.substring(0, 19).replace('T', ' ') : '-'}</td>
            <td><strong style="color: #f59e0b;">${escapeHtml(l.action)}</strong></td>
            <td>${escapeHtml(l.username || 'User ' + (l.user_id || 'System'))}</td>
            <td>${l.org_id ? '#' + l.org_id : 'Global / Personal'}</td>
            <td>${l.resource_slug ? '<code>' + escapeHtml(l.resource_slug) + '</code>' : '-'}</td>
            <td style="color: #94a3b8; font-size: 0.85rem;">${escapeHtml(l.details || '')}</td>
        </tr>
    `).join('');
}

function filterAuditTable() {
    const q = document.getElementById('search-audit').value.toLowerCase();
    const filtered = allAuditLogs.filter(l => 
        (l.action && l.action.toLowerCase().includes(q)) ||
        (l.details && l.details.toLowerCase().includes(q)) ||
        (l.username && l.username.toLowerCase().includes(q))
    );
    renderAuditTable(filtered);
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
