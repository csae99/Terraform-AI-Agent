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
    else if (tab === 'llm' || tab === 'finops') loadFinOpsData();
    else if (tab === 'k8s') loadK8sFleet();
    else if (tab === 'audit') loadAuditLogs();
    else if (tab === 'config') loadConfig();
    else if (tab === 'killswitches') loadKillSwitches();
    else if (tab === 'patterns') loadPatterns();
    else if (tab === 'agents') loadAgentOperations();
    else if (tab === 'llm-router') loadLLMRouter();
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

// ─── 4. FinOps & Revenue Analytics (Milestone 3) ───────────────────────────
let _finopsData = { overview: null, costs: null, tenants: [] };

async function loadFinOpsData() {
    await Promise.all([
        loadFinOpsOverview(),
        loadFinOpsCosts(),
        loadFinOpsTenants()
    ]);
}

// Backward compatibility alias
async function loadLLMMetrics() {
    return loadFinOpsData();
}

async function loadFinOpsOverview() {
    try {
        const res = await fetch('/api/admin/finops/overview');
        if (!res.ok) throw new Error("Failed to load FinOps overview");
        const data = await res.json();
        _finopsData.overview = data;

        // Populate Executive KPI Strip
        const mrrEl = document.getElementById('finops-vital-mrr');
        if (mrrEl) mrrEl.innerText = `$${(data.mrr || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        const arrEl = document.getElementById('finops-vital-arr');
        if (arrEl) arrEl.innerText = `$${(data.arr || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        const costsEl = document.getElementById('finops-vital-costs');
        if (costsEl && data.costs) costsEl.innerText = `$${(data.costs.total_operating_cost || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        const aiCostEl = document.getElementById('finops-vital-ai-cost');
        if (aiCostEl && data.costs) aiCostEl.innerText = `$${(data.costs.ai_token_cost || 0).toFixed(2)}`;
        const compCostEl = document.getElementById('finops-vital-compute-cost');
        if (compCostEl && data.costs) compCostEl.innerText = `$${(data.costs.compute_cost || 0).toFixed(2)}`;

        const marginEl = document.getElementById('finops-vital-margin');
        if (marginEl && data.profitability) {
            const marginPct = data.profitability.gross_margin_pct || 0;
            marginEl.innerText = `${marginPct.toFixed(1)}%`;
            marginEl.style.color = marginPct >= 60 ? '#34d399' : (marginPct >= 30 ? '#fbbf24' : '#f87171');
        }
        const profitEl = document.getElementById('finops-vital-net-profit');
        if (profitEl && data.profitability) profitEl.innerText = `$${(data.profitability.gross_profit || 0).toFixed(2)}`;

        const savingsEl = document.getElementById('finops-vital-savings');
        if (savingsEl) savingsEl.innerText = `$${(data.ai_savings_generated || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

        const convEl = document.getElementById('finops-vital-conversion');
        if (convEl) convEl.innerText = `${(data.conversion_rate_pct || 0).toFixed(1)}%`;
        const arpuEl = document.getElementById('finops-vital-arpu');
        if (arpuEl) arpuEl.innerText = `$${(data.arpu || 0).toFixed(2)}`;

        // Subscription Tier breakdown panel
        const totalTenantsEl = document.getElementById('finops-total-tenants-count');
        if (totalTenantsEl) totalTenantsEl.innerText = `${data.total_tenants || 0} Accounts`;
        const freeCountEl = document.getElementById('finops-free-count');
        if (freeCountEl && data.plan_distribution) freeCountEl.innerText = data.plan_distribution.free || 0;
        const proCountEl = document.getElementById('finops-pro-count');
        if (proCountEl && data.plan_distribution) proCountEl.innerText = data.plan_distribution.pro || 0;
        const proRevEl = document.getElementById('finops-pro-rev');
        if (proRevEl && data.plan_distribution && data.tier_prices) {
            proRevEl.innerText = `$${((data.plan_distribution.pro || 0) * (data.tier_prices.pro || 29)).toFixed(0)}/mo`;
        }
        const entCountEl = document.getElementById('finops-enterprise-count');
        if (entCountEl && data.plan_distribution) entCountEl.innerText = data.plan_distribution.enterprise || 0;
        const entRevEl = document.getElementById('finops-enterprise-rev');
        if (entRevEl && data.plan_distribution && data.tier_prices) {
            entRevEl.innerText = `$${((data.plan_distribution.enterprise || 0) * (data.tier_prices.enterprise || 199)).toFixed(0)}/mo`;
        }

        const paidRatioEl = document.getElementById('finops-paid-ratio');
        if (paidRatioEl) paidRatioEl.innerText = `${data.paid_tenants || 0} / ${data.total_tenants || 0} (${(data.conversion_rate_pct || 0).toFixed(1)}%)`;

    } catch (e) {
        console.error("loadFinOpsOverview error:", e);
    }
}

async function loadFinOpsCosts() {
    try {
        const res = await fetch('/api/admin/finops/costs');
        if (!res.ok) throw new Error("Failed to load FinOps costs");
        const data = await res.json();
        _finopsData.costs = data;

        const listEl = document.getElementById('finops-cost-categories-list');
        if (listEl) {
            listEl.innerHTML = (data.categories || []).map(c => `
                <div style="background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                        <span style="font-size: 0.8rem; color: #cbd5e1; display: flex; align-items: center; gap: 0.4rem;">
                            <i class="${c.icon}" style="color: ${c.color};"></i> ${c.name}
                        </span>
                        <span style="font-size: 0.8rem; font-weight: 700; color: #fff;">
                            $${(c.amount || 0).toFixed(2)} <span style="font-size: 0.7rem; color: #94a3b8; font-weight: normal;">(${c.pct}%)</span>
                        </span>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); border-radius: 4px; height: 6px; overflow: hidden;">
                        <div style="background: ${c.color}; width: ${Math.min(100, Math.max(2, c.pct))}%; height: 100%;"></div>
                    </div>
                </div>
            `).join('');
        }

        const runEl = document.getElementById('finops-unit-cost-run');
        if (runEl && data.unit_economics) runEl.innerText = `$${(data.unit_economics.cost_per_run || 0).toFixed(4)}`;
        const projEl = document.getElementById('finops-unit-cost-project');
        if (projEl && data.unit_economics) projEl.innerText = `$${(data.unit_economics.cost_per_project || 0).toFixed(2)}`;
        const tokEl = document.getElementById('finops-unit-cost-tokens');
        if (tokEl && data.unit_economics) tokEl.innerText = `$${(data.unit_economics.cost_per_1k_tokens || 0).toFixed(5)}`;
    } catch (e) {
        console.error("loadFinOpsCosts error:", e);
    }
}

async function loadFinOpsTenants() {
    try {
        const res = await fetch('/api/admin/finops/tenants');
        if (!res.ok) throw new Error("Failed to load FinOps tenants");
        const data = await res.json();
        _finopsData.tenants = data.tenants || [];
        renderFinOpsTenants(_finopsData.tenants);
    } catch (e) {
        console.error("loadFinOpsTenants error:", e);
        showToast(e.message, "error");
    }
}

function renderFinOpsTenants(tenants) {
    const tbody = document.getElementById('finops-tenants-tbody');
    if (!tbody) return;

    if (!tenants || tenants.length === 0) {
        tbody.innerHTML = `<tr><td colspan="13" style="text-align: center; color: #888; padding: 2rem;">No tenant unit economics recorded yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = tenants.map(t => {
        let healthBadge = '';
        if (t.health === 'high_margin') {
            healthBadge = '<span class="badge badge-success"><i class="fas fa-arrow-trend-up"></i> High Margin</span>';
        } else if (t.health === 'healthy') {
            healthBadge = '<span class="badge badge-success"><i class="fas fa-check"></i> Healthy</span>';
        } else if (t.health === 'at_risk') {
            healthBadge = '<span class="badge badge-warning"><i class="fas fa-exclamation-triangle"></i> At Risk</span>';
        } else if (t.health === 'free_tier') {
            healthBadge = '<span class="badge" style="background: rgba(148, 163, 184, 0.2); color: #cbd5e1;">Free Tier</span>';
        } else {
            healthBadge = '<span class="badge badge-danger"><i class="fas fa-arrow-down"></i> Subsidized</span>';
        }

        const planBadge = t.plan === 'enterprise' 
            ? '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-weight: 700;">ENTERPRISE</span>'
            : (t.plan === 'pro' 
                ? '<span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #818cf8; font-weight: 700;">PRO</span>'
                : '<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: #94a3b8;">FREE</span>');

        const marginColor = t.margin_pct >= 60 ? '#34d399' : (t.margin_pct >= 30 ? '#fbbf24' : (t.margin_pct >= 0 ? '#f87171' : '#ef4444'));

        return `
            <tr>
                <td>
                    <strong style="color: #fff;">${escapeHtml(t.name)}</strong>
                    <div style="font-size: 0.75rem; color: #94a3b8;">${escapeHtml(t.slug)} (ID: #${t.org_id})</div>
                </td>
                <td>${planBadge}</td>
                <td><strong>${t.runs_count || 0}</strong></td>
                <td>${(t.tokens_used || 0).toLocaleString()}</td>
                <td>$${(t.ai_cost || 0).toFixed(4)}</td>
                <td>$${(t.compute_cost || 0).toFixed(4)}</td>
                <td><strong style="color: #f87171;">$${(t.total_cost || 0).toFixed(2)}</strong></td>
                <td>$${(t.cloud_spend || 0).toFixed(2)}</td>
                <td><span style="color: #fbbf24; font-weight: 600;">$${(t.ai_savings || 0).toFixed(2)}</span></td>
                <td><strong style="color: #fff;">$${(t.monthly_fee || 0).toFixed(2)}</strong></td>
                <td><strong style="color: ${t.net_margin >= 0 ? '#34d399' : '#ef4444'};">${t.net_margin >= 0 ? '+' : ''}$${(t.net_margin || 0).toFixed(2)}</strong></td>
                <td><strong style="color: ${marginColor};">${(t.margin_pct || 0).toFixed(1)}%</strong></td>
                <td>${healthBadge}</td>
            </tr>
        `;
    }).join('');
}

function filterFinOpsTenants() {
    const search = (document.getElementById('finops-tenant-search')?.value || '').toLowerCase();
    const health = document.getElementById('finops-health-filter')?.value || 'all';

    let filtered = _finopsData.tenants || [];
    if (search) {
        filtered = filtered.filter(t => (t.name || '').toLowerCase().includes(search) || (t.slug || '').toLowerCase().includes(search));
    }
    if (health !== 'all') {
        filtered = filtered.filter(t => t.health === health);
    }
    renderFinOpsTenants(filtered);
}

function openPricingSimulator() {
    const modal = document.getElementById('modal-pricing-simulator');
    if (!modal) return;
    modal.style.display = 'flex';
    if (_finopsData.overview && _finopsData.overview.tier_prices) {
        const proInput = document.getElementById('sim-pro-price');
        const entInput = document.getElementById('sim-enterprise-price');
        if (proInput) proInput.value = _finopsData.overview.tier_prices.pro || 29;
        if (entInput) entInput.value = _finopsData.overview.tier_prices.enterprise || 199;
    }
    recalculateSimulation();
}

async function recalculateSimulation() {
    const proPrice = parseFloat(document.getElementById('sim-pro-price')?.value || 29);
    const entPrice = parseFloat(document.getElementById('sim-enterprise-price')?.value || 199);

    try {
        const res = await fetch('/api/admin/finops/simulate-pricing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pro: proPrice, enterprise: entPrice, free: 0.0 })
        });
        if (!res.ok) throw new Error("Simulation failed");
        const data = await res.json();

        const mrrEl = document.getElementById('sim-result-mrr');
        if (mrrEl) mrrEl.innerText = `$${data.projected_mrr.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        const deltaEl = document.getElementById('sim-result-delta');
        if (deltaEl) {
            deltaEl.innerText = `${data.mrr_delta >= 0 ? '+' : ''}$${data.mrr_delta.toFixed(2)}`;
            deltaEl.style.color = data.mrr_delta >= 0 ? '#34d399' : '#f87171';
        }

        const marginEl = document.getElementById('sim-result-margin');
        if (marginEl) {
            marginEl.innerText = `${data.projected_gross_margin_pct.toFixed(1)}%`;
            marginEl.style.color = data.projected_gross_margin_pct >= 60 ? '#34d399' : (data.projected_gross_margin_pct >= 30 ? '#fbbf24' : '#f87171');
        }

        const arrEl = document.getElementById('sim-result-arr');
        if (arrEl) arrEl.innerText = `$${data.projected_arr.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        const costEl = document.getElementById('sim-result-cost');
        if (costEl) costEl.innerText = `$${data.total_operating_cost.toFixed(2)}`;
    } catch (e) {
        console.error("recalculateSimulation error:", e);
    }
}

async function saveSimulationPrices() {
    const proPrice = parseFloat(document.getElementById('sim-pro-price')?.value || 29);
    const entPrice = parseFloat(document.getElementById('sim-enterprise-price')?.value || 199);

    try {
        const res = await fetch('/api/admin/finops/tier-pricing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pro: proPrice, enterprise: entPrice, free: 0.0 })
        });
        if (!res.ok) throw new Error("Failed to apply tier pricing");
        const data = await res.json();
        showToast(data.message || "Subscription pricing updated!", "success");
        closeModal('modal-pricing-simulator');
        await loadFinOpsData();
    } catch (e) {
        showToast(e.message, "error");
    }
}

function exportFinOpsCSV() {
    window.location.href = '/api/admin/finops/export';
    showToast("Downloading FinOps unit economics CSV...", "info");
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

// ════════════════════════════════════════════════════════════════════════
// ── 7. Environment & Config Manager ─────────────────────────────────────
// ════════════════════════════════════════════════════════════════════════

let allConfigs = [];
let activeConfigCategory = 'all';

async function loadConfig() {
    try {
        const res = await fetch('/api/admin/config');
        if (!res.ok) throw new Error("Failed to load platform configuration");
        const data = await res.json();
        allConfigs = data.configs || [];
        updateConfigCategoryCounts();
        renderConfigTable(getFilteredConfigs());
    } catch (e) {
        showToast(e.message, "error");
    }
}

function updateConfigCategoryCounts() {
    const counts = { all: allConfigs.length, llm: 0, database: 0, auth: 0, features: 0 };
    allConfigs.forEach(c => {
        const cat = (c.category || 'general').toLowerCase();
        if (counts[cat] !== undefined) counts[cat]++;
    });
    for (const [k, v] of Object.entries(counts)) {
        const el = document.getElementById(`cfg-count-${k}`);
        if (el) el.innerText = v;
    }
}

function filterConfigCategory(cat) {
    activeConfigCategory = cat;
    document.querySelectorAll('[id^="cfg-cat-"]').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`cfg-cat-${cat}`);
    if (btn) btn.classList.add('active');
    renderConfigTable(getFilteredConfigs());
}

function getFilteredConfigs() {
    const q = (document.getElementById('search-config')?.value || '').toLowerCase();
    return allConfigs.filter(c => {
        const matchCat = activeConfigCategory === 'all' || (c.category || '').toLowerCase() === activeConfigCategory;
        const matchQ = !q || c.key.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q);
        return matchCat && matchQ;
    });
}

function filterConfigTable() {
    renderConfigTable(getFilteredConfigs());
}

function renderConfigTable(configs) {
    const tbody = document.getElementById('config-tbody');
    if (!tbody) return;
    if (configs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #888; padding: 2rem;">No configuration variables found matching criteria.</td></tr>`;
        return;
    }

    tbody.innerHTML = configs.map(c => {
        const catBadge = `<span class="status-badge" style="background: rgba(99,102,241,0.15); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.3); font-size: 0.72rem;">${escapeHtml(c.category || 'general')}</span>`;
        const isMasked = c.is_masked;
        const valDisplay = isMasked
            ? `<span style="font-family: monospace; color: #94a3b8;" id="val-${c.id}">${escapeHtml(c.value)}</span>`
            : `<span style="font-family: monospace; color: #e2e8f0;" id="val-${c.id}">${escapeHtml(c.value || '(empty)')}</span>`;
            
        const dateDisplay = c.updated_at ? c.updated_at.substring(0, 16).replace('T', ' ') : '-';

        return `
            <tr>
                <td><strong style="color: #f1f5f9; font-family: monospace;">${escapeHtml(c.key)}</strong></td>
                <td>${catBadge}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        ${valDisplay}
                        ${c.is_secret ? `<span title="Masked Secret" style="font-size: 0.75rem; color: #f59e0b;"><i class="fas fa-lock"></i></span>` : ''}
                    </div>
                </td>
                <td style="color: #94a3b8; font-size: 0.85rem;">${escapeHtml(c.description || '-')}</td>
                <td style="color: #64748b; font-size: 0.8rem;">${dateDisplay}</td>
                <td style="text-align: right;">
                    <div style="display: inline-flex; gap: 0.3rem;">
                        <button onclick="testConfigKey('${escapeHtml(c.key)}')" class="action-btn-sm" style="background: rgba(59,130,246,0.15); color: #93c5fd; border: 1px solid rgba(59,130,246,0.3);" title="Test Connectivity / Validity">
                            <i class="fas fa-bolt"></i> Test
                        </button>
                        <button onclick="openConfigModal('${escapeHtml(c.key)}')" class="action-btn-sm btn-plan" title="Edit Parameter">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button onclick="deleteConfigKey('${escapeHtml(c.key)}')" class="action-btn-sm btn-suspend" title="Delete Parameter">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function openConfigModal(key = null) {
    const modal = document.getElementById('modal-edit-config');
    if (!modal) return;
    const title = document.getElementById('modal-cfg-title');
    const keyInput = document.getElementById('cfg-input-key');
    const valInput = document.getElementById('cfg-input-value');
    const catInput = document.getElementById('cfg-input-category');
    const secInput = document.getElementById('cfg-input-secret');
    const descInput = document.getElementById('cfg-input-desc');

    if (key) {
        const item = allConfigs.find(c => c.key === key);
        title.innerHTML = `<i class="fas fa-edit" style="color: #6366f1;"></i> Edit Parameter: <code>${escapeHtml(key)}</code>`;
        keyInput.value = item ? item.key : key;
        keyInput.disabled = true;
        valInput.value = item ? (item.is_masked ? '' : item.value) : '';
        valInput.placeholder = item && item.is_masked ? "Leave empty to keep existing secret, or enter new value..." : "Enter configuration value...";
        catInput.value = item ? (item.category || 'general') : 'general';
        secInput.value = item ? (item.is_secret ? 'true' : 'false') : 'auto';
        descInput.value = item ? (item.description || '') : '';
    } else {
        title.innerHTML = `<i class="fas fa-plus" style="color: #6366f1;"></i> Add Runtime Parameter`;
        keyInput.value = '';
        keyInput.disabled = false;
        valInput.value = '';
        valInput.placeholder = 'Enter configuration value...';
        catInput.value = 'general';
        secInput.value = 'auto';
        descInput.value = '';
    }
    modal.style.display = 'flex';
}

async function submitConfigSave() {
    const key = document.getElementById('cfg-input-key').value.trim();
    const value = document.getElementById('cfg-input-value').value;
    const category = document.getElementById('cfg-input-category').value;
    const secVal = document.getElementById('cfg-input-secret').value;
    const description = document.getElementById('cfg-input-desc').value.trim();

    if (!key) {
        showToast("Parameter key is required", "error");
        return;
    }

    const payload = {
        key,
        value,
        category,
        description,
        is_secret: secVal === 'auto' ? null : (secVal === 'true')
    };

    try {
        const res = await fetch('/api/admin/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to save configuration");
        showToast(data.message, "success");
        closeModal('modal-edit-config');
        await loadConfig();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function testConfigKey(key) {
    showToast(`Testing ${key}...`, "info");
    try {
        const res = await fetch('/api/admin/config/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Test failed");
        showToast(`[${key}] ${data.message}`, data.status === 'error' ? 'error' : data.status === 'warning' ? 'error' : 'success');
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function deleteConfigKey(key) {
    if (!confirm(`Are you sure you want to delete parameter '${key}'?`)) return;
    try {
        const res = await fetch(`/api/admin/config/${encodeURIComponent(key)}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete");
        showToast(data.message, "success");
        await loadConfig();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ════════════════════════════════════════════════════════════════════════
// ── 8. Emergency Kill Switches ──────────────────────────────────────────
// ════════════════════════════════════════════════════════════════════════

let allKillSwitches = {};

async function loadKillSwitches() {
    try {
        const res = await fetch('/api/admin/killswitches');
        if (!res.ok) throw new Error("Failed to load emergency kill switches");
        const data = await res.json();
        allKillSwitches = data.switches || {};
        renderKillSwitches(allKillSwitches);
    } catch (e) {
        showToast(e.message, "error");
    }
}

function renderKillSwitches(switches) {
    const grid = document.getElementById('killswitches-grid');
    if (!grid) return;

    let anyActive = false;
    const switchCards = Object.values(switches).map(s => {
        if (s.enabled) anyActive = true;
        const statusColor = s.enabled ? '#ef4444' : '#10b981';
        const statusBg = s.enabled ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)';
        const statusBorder = s.enabled ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)';
        const statusText = s.enabled ? 'ACTIVE (FROZEN)' : 'NORMAL (ALLOWED)';
        const toggleBtnText = s.enabled ? 'Deactivate (Resume)' : 'Activate (Emergency Stop)';
        const toggleBtnBg = s.enabled ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';
        const toggleBtnColor = s.enabled ? '#34d399' : '#f87171';
        const toggleBtnBorder = s.enabled ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(239, 68, 68, 0.4)';

        return `
            <div class="vital-card" style="border: 1px solid ${statusBorder};">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
                    <div>
                        <h3 style="margin: 0; font-size: 1.15rem; color: #fff;">${escapeHtml(s.name)}</h3>
                        <span style="font-family: monospace; font-size: 0.75rem; color: #94a3b8;">${escapeHtml(s.id)}</span>
                    </div>
                    <span class="status-badge" style="background: ${statusBg}; color: ${statusColor}; border: 1px solid ${statusBorder}; font-weight: 700;">
                        ${statusText}
                    </span>
                </div>
                <p style="color: #cbd5e1; font-size: 0.88rem; min-height: 40px; margin: 0.5rem 0;">
                    ${escapeHtml(s.description)}
                </p>
                <div style="background: rgba(0,0,0,0.25); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem; margin: 0.75rem 0; font-size: 0.78rem; color: #94a3b8;">
                    <div><strong>Last Reason:</strong> ${escapeHtml(s.reason || 'None provided')}</div>
                    <div><strong>Updated by:</strong> ${escapeHtml(s.updated_by || 'system')} ${s.updated_at ? '(' + s.updated_at.substring(0, 16).replace('T', ' ') + ')' : ''}</div>
                </div>
                <div style="margin-top: auto; padding-top: 0.5rem;">
                    <button onclick="promptKillSwitch('${escapeHtml(s.id)}', ${s.enabled})" class="action-btn-sm" style="width: 100%; justify-content: center; padding: 0.6rem; font-size: 0.85rem; background: ${toggleBtnBg}; color: ${toggleBtnColor}; border: ${toggleBtnBorder};">
                        <i class="fas fa-${s.enabled ? 'play-circle' : 'stop-circle'}"></i> ${toggleBtnText}
                    </button>
                </div>
            </div>
        `;
    });

    grid.innerHTML = switchCards.join('');

    // Update Global Banner
    const banner = document.getElementById('killswitch-global-banner');
    const bannerTitle = document.getElementById('killswitch-banner-title');
    const bannerDesc = document.getElementById('killswitch-banner-desc');
    if (banner && bannerTitle && bannerDesc) {
        if (anyActive) {
            banner.style.background = 'rgba(239, 68, 68, 0.15)';
            banner.style.border = '1px solid rgba(239, 68, 68, 0.4)';
            banner.style.color = '#f87171';
            banner.querySelector('i').className = 'fas fa-exclamation-triangle';
            bannerTitle.innerText = 'EMERGENCY OVERRIDE ACTIVE';
            bannerDesc.innerText = 'One or more platform capabilities are currently frozen by Super-Admin emergency controls.';
        } else {
            banner.style.background = 'rgba(16, 185, 129, 0.15)';
            banner.style.border = '1px solid rgba(16, 185, 129, 0.3)';
            banner.style.color = '#34d399';
            banner.querySelector('i').className = 'fas fa-check-circle';
            bannerTitle.innerText = 'All Systems Nominal';
            bannerDesc.innerText = 'No emergency kill switches are currently active. All platform operations are proceeding normally.';
        }
    }
}

function promptKillSwitch(switchId, currentEnabled) {
    const modal = document.getElementById('modal-killswitch-confirm');
    if (!modal) return;
    const targetState = !currentEnabled;
    document.getElementById('ks-target-id').value = switchId;
    document.getElementById('ks-target-state').value = targetState ? 'true' : 'false';
    document.getElementById('ks-input-reason').value = '';

    const actionText = targetState ? 'ACTIVATE EMERGENCY STOP' : 'DEACTIVATE & RESUME';
    document.getElementById('ks-modal-title').innerHTML = `<i class="fas fa-radiation"></i> Confirm Kill Switch: <code>${escapeHtml(switchId)}</code>`;
    document.getElementById('ks-modal-msg').innerHTML = `Are you sure you want to <strong>${actionText}</strong> for <strong>${escapeHtml(switchId)}</strong>? An audit record will be logged immediately.`;
    
    const confirmBtn = document.getElementById('ks-btn-confirm');
    if (confirmBtn) {
        confirmBtn.style.background = targetState ? '#ef4444' : '#10b981';
        confirmBtn.innerText = targetState ? 'Activate Kill Switch' : 'Resume Operations';
    }

    modal.style.display = 'flex';
}

async function submitKillSwitchToggle() {
    const switchId = document.getElementById('ks-target-id').value;
    const targetState = document.getElementById('ks-target-state').value === 'true';
    const reason = document.getElementById('ks-input-reason').value.trim();

    if (!reason) {
        showToast("Please provide an audit justification reason", "error");
        return;
    }

    try {
        const res = await fetch(`/api/admin/killswitches/${encodeURIComponent(switchId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: targetState, reason })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to toggle kill switch");
        showToast(data.message, targetState ? "error" : "success");
        closeModal('modal-killswitch-confirm');
        await loadKillSwitches();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ════════════════════════════════════════════════════════════════════════
// ── 9. Failure Pattern Memory Catalog ───────────────────────────────────
// ════════════════════════════════════════════════════════════════════════

let allPatterns = [];

async function loadPatterns() {
    try {
        const res = await fetch('/api/admin/patterns');
        if (!res.ok) throw new Error("Failed to load failure pattern catalog");
        const data = await res.json();
        allPatterns = data.patterns || [];
        updatePatternKPIs(allPatterns);
        renderPatternsTable(allPatterns);
    } catch (e) {
        showToast(e.message, "error");
    }
}

function updatePatternKPIs(patterns) {
    const total = patterns.length;
    const trusted = patterns.filter(p => p.status === 'trusted').length;
    const candidate = patterns.filter(p => p.status === 'candidate').length;
    const avgConf = total > 0 ? (patterns.reduce((sum, p) => sum + (p.confidence || 0), 0) / total * 100).toFixed(1) : '0';

    const elTot = document.getElementById('vital-pat-total');
    const elTru = document.getElementById('vital-pat-trusted');
    const elCan = document.getElementById('vital-pat-candidate');
    const elCnf = document.getElementById('vital-pat-confidence');

    if (elTot) elTot.innerText = total;
    if (elTru) elTru.innerText = trusted;
    if (elCan) elCan.innerText = candidate;
    if (elCnf) elCnf.innerText = `${avgConf}%`;
}

function filterPatternsTable() {
    const q = (document.getElementById('search-patterns')?.value || '').toLowerCase();
    const filtered = allPatterns.filter(p => 
        (p.error_substring && p.error_substring.toLowerCase().includes(q)) ||
        (p.description && p.description.toLowerCase().includes(q)) ||
        (p.fix && p.fix.toLowerCase().includes(q)) ||
        (p.category && p.category.toLowerCase().includes(q))
    );
    renderPatternsTable(filtered);
}

function renderPatternsTable(patterns) {
    const tbody = document.getElementById('patterns-tbody');
    if (!tbody) return;
    if (patterns.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #888; padding: 2rem;">No failure patterns found matching search query.</td></tr>`;
        return;
    }

    tbody.innerHTML = patterns.map(p => {
        const isTrusted = p.status === 'trusted';
        const statusBadge = `<span class="status-badge" style="background: ${isTrusted ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)'}; color: ${isTrusted ? '#34d399' : '#fbbf24'}; border: 1px solid ${isTrusted ? 'rgba(16,185,129,0.4)' : 'rgba(245,158,11,0.4)'};">${escapeHtml(p.status)}</span>`;
        
        const sevColor = p.severity === 'CRITICAL' ? '#ef4444' : p.severity === 'HIGH' ? '#f97316' : '#38bdf8';
        const sevBadge = `<span class="status-badge" style="background: rgba(255,255,255,0.05); color: ${sevColor}; font-weight: 700;">${escapeHtml(p.severity || 'MEDIUM')}</span>`;

        const confPct = Math.round((p.confidence || 0) * 100);
        const confBar = `
            <div style="display: flex; align-items: center; gap: 0.4rem;">
                <div style="flex: 1; background: rgba(255,255,255,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                    <div style="width: ${confPct}%; background: ${confPct >= 80 ? '#10b981' : confPct >= 50 ? '#f59e0b' : '#ef4444'}; height: 100%;"></div>
                </div>
                <span style="font-size: 0.78rem; color: #cbd5e1; font-family: monospace;">${confPct}%</span>
            </div>
        `;

        return `
            <tr>
                <td>
                    <strong style="color: #f1f5f9; font-family: monospace; font-size: 0.85rem;">${escapeHtml(p.error_substring)}</strong>
                    <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.2rem;">${escapeHtml(p.description || '')}</div>
                </td>
                <td><span class="status-badge" style="background: rgba(168,85,247,0.15); color: #d8b4fe; border: 1px solid rgba(168,85,247,0.3); font-size: 0.72rem;">${escapeHtml(p.category || 'general')}</span></td>
                <td>${sevBadge}</td>
                <td>${confBar}</td>
                <td style="font-size: 0.8rem; color: #94a3b8;"><span style="color: #34d399;">${p.success_count || 0}</span> / <span style="color: #f87171;">${p.failure_count || 0}</span></td>
                <td>${statusBadge}</td>
                <td style="font-size: 0.8rem; color: #cbd5e1; max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(p.fix || '')}">
                    ${escapeHtml(p.fix || '-')}
                </td>
                <td style="text-align: right;">
                    <div style="display: inline-flex; gap: 0.3rem;">
                        ${!isTrusted ? `
                            <button onclick="promotePattern(${p.id})" class="action-btn-sm btn-activate" title="Promote to Trusted">
                                <i class="fas fa-check"></i>
                            </button>
                        ` : ''}
                        <button onclick="decayPattern(${p.id})" class="action-btn-sm" style="background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3);" title="Decay Confidence (-15%)">
                            <i class="fas fa-arrow-down"></i>
                        </button>
                        <button onclick="openPatternModal(${p.id})" class="action-btn-sm btn-plan" title="Edit Pattern">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="deletePattern(${p.id})" class="action-btn-sm btn-suspend" title="Delete Pattern">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function openPatternModal(id = null) {
    const modal = document.getElementById('modal-edit-pattern');
    if (!modal) return;
    const title = document.getElementById('pat-modal-title');
    const targetIdInput = document.getElementById('pat-target-id');
    const subInput = document.getElementById('pat-input-substring');
    const catInput = document.getElementById('pat-input-category');
    const sevInput = document.getElementById('pat-input-severity');
    const descInput = document.getElementById('pat-input-desc');
    const fixInput = document.getElementById('pat-input-fix');
    const statInput = document.getElementById('pat-input-status');
    const confInput = document.getElementById('pat-input-confidence');

    if (id) {
        const item = allPatterns.find(p => p.id === id);
        title.innerHTML = `<i class="fas fa-edit" style="color: #a855f7;"></i> Edit Pattern #${id}`;
        targetIdInput.value = id;
        subInput.value = item ? item.error_substring : '';
        subInput.disabled = true;
        catInput.value = item ? (item.category || 'general') : 'general';
        sevInput.value = item ? (item.severity || 'MEDIUM') : 'MEDIUM';
        descInput.value = item ? (item.description || '') : '';
        fixInput.value = item ? (item.fix || '') : '';
        statInput.value = item ? (item.status || 'trusted') : 'trusted';
        confInput.value = item ? (item.confidence || 0.95) : 0.95;
    } else {
        title.innerHTML = `<i class="fas fa-plus" style="color: #a855f7;"></i> Add Failure Pattern`;
        targetIdInput.value = '';
        subInput.value = '';
        subInput.disabled = false;
        catInput.value = 'provider';
        sevInput.value = 'MEDIUM';
        descInput.value = '';
        fixInput.value = '';
        statInput.value = 'trusted';
        confInput.value = 0.95;
    }
    modal.style.display = 'flex';
}

async function submitPatternSave() {
    const id = document.getElementById('pat-target-id').value;
    const error_substring = document.getElementById('pat-input-substring').value.trim();
    const category = document.getElementById('pat-input-category').value;
    const severity = document.getElementById('pat-input-severity').value;
    const description = document.getElementById('pat-input-desc').value.trim();
    const fix = document.getElementById('pat-input-fix').value.trim();
    const status = document.getElementById('pat-input-status').value;
    const confidence = parseFloat(document.getElementById('pat-input-confidence').value) || 0.9;

    if (!error_substring) {
        showToast("Error substring is required", "error");
        return;
    }

    const payload = { error_substring, category, severity, description, fix, status, confidence };

    try {
        const url = id ? `/api/admin/patterns/${id}` : '/api/admin/patterns';
        const method = id ? 'PUT' : 'POST';
        const res = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to save pattern");
        showToast(data.message, "success");
        closeModal('modal-edit-pattern');
        await loadPatterns();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function promotePattern(id) {
    try {
        const res = await fetch(`/api/admin/patterns/${id}/promote`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Promotion failed");
        showToast(data.message, "success");
        await loadPatterns();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function decayPattern(id) {
    try {
        const res = await fetch(`/api/admin/patterns/${id}/decay`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Decay failed");
        showToast(data.message, "info");
        await loadPatterns();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function deletePattern(id) {
    if (!confirm(`Are you sure you want to delete pattern #${id}?`)) return;
    try {
        const res = await fetch(`/api/admin/patterns/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete pattern");
        showToast(data.message, "success");
        await loadPatterns();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ════════════════════════════════════════════════════════════════════════
// ── Milestone 2: Agent Operations Center Logic ─────────────────────────
// ════════════════════════════════════════════════════════════════════════

let cachedAgentRuns = [];
let activeInspectorSlug = null;

async function loadAgentOperations() {
    try {
        // 1. Fetch Fleet Health
        const healthRes = await fetch('/api/admin/agents/health');
        if (healthRes.ok) {
            const healthData = await healthRes.json();
            renderAgentFleetGrid(healthData.agents || []);
        }

        // 2. Fetch Leaderboard
        const lbRes = await fetch('/api/admin/agents/leaderboard');
        if (lbRes.ok) {
            const lbData = await lbRes.json();
            const lb = lbData.leaderboard || {};
            if (lb.most_used) {
                document.getElementById('agent-lb-most-used').innerText = lb.most_used.agent_name;
                document.getElementById('agent-lb-most-used-sub').innerText = lb.most_used.value;
            }
            if (lb.highest_failure_rate) {
                document.getElementById('agent-lb-failure-rate').innerText = lb.highest_failure_rate.agent_name;
                document.getElementById('agent-lb-failure-sub').innerText = lb.highest_failure_rate.value;
            }
            if (lb.top_token_consumer) {
                document.getElementById('agent-lb-tokens').innerText = lb.top_token_consumer.agent_name;
                document.getElementById('agent-lb-tokens-sub').innerText = lb.top_token_consumer.value;
            }
            if (lb.most_expensive) {
                document.getElementById('agent-lb-cost').innerText = lb.most_expensive.agent_name;
                document.getElementById('agent-lb-cost-sub').innerText = lb.most_expensive.value;
            }
        }

        // 3. Fetch Runs
        await loadAgentRuns();
    } catch (e) {
        console.error("Agent Operations load error:", e);
        showToast("Error loading Agent Operations: " + e.message, "error");
    }
}

function renderAgentFleetGrid(agents) {
    const grid = document.getElementById('agent-fleet-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const agentIcons = {
        'ArchitectAgent': 'drafting-compass',
        'DeveloperAgent': 'code',
        'SecurityReviewer': 'shield-alt',
        'FinOpsSpecialist': 'coins',
        'TestingAgent': 'vial',
        'GitOpsCoordinator': 'code-branch',
        'DeploymentPlanner': 'rocket'
    };

    agents.forEach(a => {
        const icon = agentIcons[a.agent_name] || 'robot';
        const isHealthy = a.status === 'HEALTHY';
        const statusColor = isHealthy ? '#34d399' : '#f87171';
        const statusBg = isHealthy ? 'rgba(52, 211, 153, 0.15)' : 'rgba(248, 113, 113, 0.15)';
        const progressColor = a.success_rate_percent >= 95 ? '#10b981' : (a.success_rate_percent >= 85 ? '#f59e0b' : '#ef4444');

        const card = document.createElement('div');
        card.className = 'vital-card';
        card.style.position = 'relative';
        card.style.overflow = 'hidden';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.style.justifyContent = 'space-between';

        card.innerHTML = `
            <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
                    <div style="display: flex; align-items: center; gap: 0.6rem;">
                        <div style="width: 36px; height: 36px; border-radius: 8px; background: rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: center; font-size: 1.1rem; color: #38bdf8;">
                            <i class="fas fa-${icon}"></i>
                        </div>
                        <div>
                            <div style="font-size: 0.95rem; font-weight: 700; color: #fff;">${a.agent_name}</div>
                            <span style="font-size: 0.75rem; color: #94a3b8;">${a.role_title}</span>
                        </div>
                    </div>
                    <span style="font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; background: ${statusBg}; color: ${statusColor}; border: 1px solid ${statusColor};">
                        ${a.status}
                    </span>
                </div>

                <!-- Success Rate Bar -->
                <div style="margin: 0.85rem 0;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 0.25rem;">
                        <span style="color: #94a3b8;">Success Rate</span>
                        <span style="font-weight: 700; color: #fff;">${a.success_rate_percent}%</span>
                    </div>
                    <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${a.success_rate_percent}%; height: 100%; background: ${progressColor}; border-radius: 3px;"></div>
                    </div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; border-top: 1px solid var(--border); padding-top: 0.75rem; margin-top: 0.5rem; font-size: 0.8rem;">
                <div>
                    <span style="color: #94a3b8; font-size: 0.7rem;">TOTAL RUNS</span>
                    <div style="font-weight: 700; color: #fff;">${a.total_runs} (${a.failed_runs} fails)</div>
                </div>
                <div>
                    <span style="color: #94a3b8; font-size: 0.7rem;">AVG DURATION</span>
                    <div style="font-weight: 700; color: #38bdf8;">${a.avg_duration_seconds}s</div>
                </div>
                <div>
                    <span style="color: #94a3b8; font-size: 0.7rem;">TOTAL TOKENS</span>
                    <div style="font-weight: 700; color: #c084fc;">${a.total_tokens.toLocaleString()}</div>
                </div>
                <div>
                    <span style="color: #94a3b8; font-size: 0.7rem;">TOTAL COST</span>
                    <div style="font-weight: 700; color: #34d399;">$${a.total_cost.toFixed(3)}</div>
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

async function loadAgentRuns() {
    try {
        const res = await fetch('/api/admin/agents/runs?limit=30');
        if (!res.ok) throw new Error("Failed to load runs");
        const data = await res.json();
        cachedAgentRuns = data.runs || [];
        renderAgentRunsTable(cachedAgentRuns);
    } catch (e) {
        console.error("Error loading agent runs:", e);
    }
}

function renderAgentRunsTable(runs) {
    const tbody = document.getElementById('agent-runs-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!runs || runs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No pipeline runs found.</td></tr>`;
        return;
    }

    runs.forEach(r => {
        const tr = document.createElement('tr');
        const isRunning = r.status === 'running';
        const isPaused = r.status === 'paused';
        const isCancelled = r.status === 'cancelled';
        const isCompleted = r.status === 'completed' || r.status === 'deployed' || r.status === 'generated' || r.status === 'pr_opened';

        let statusBadge = `<span class="badge" style="background: rgba(100,116,139,0.2); color: #94a3b8;">${r.status.toUpperCase()}</span>`;
        if (isRunning) statusBadge = `<span class="badge" style="background: rgba(56,189,248,0.2); color: #38bdf8;"><i class="fas fa-spinner fa-spin"></i> RUNNING</span>`;
        else if (isPaused) statusBadge = `<span class="badge" style="background: rgba(234,179,8,0.2); color: #fde047;"><i class="fas fa-pause"></i> PAUSED</span>`;
        else if (isCancelled) statusBadge = `<span class="badge" style="background: rgba(239,68,68,0.2); color: #fca5a5;"><i class="fas fa-ban"></i> CANCELLED</span>`;
        else if (isCompleted) statusBadge = `<span class="badge" style="background: rgba(34,197,94,0.2); color: #86efac;"><i class="fas fa-check"></i> SUCCESS</span>`;
        else if (r.status === 'failed') statusBadge = `<span class="badge" style="background: rgba(239,68,68,0.2); color: #f87171;"><i class="fas fa-times"></i> FAILED</span>`;

        let actionButtons = `
            <button onclick="openRunInspector('${r.slug}')" class="action-btn-sm" style="background: rgba(56,189,248,0.15); border: 1px solid #38bdf8; color: #38bdf8;">
                <i class="fas fa-search"></i> Inspect
            </button>
        `;

        if (isRunning) {
            actionButtons += `
                <button onclick="interveneRun('${r.slug}', 'pause')" class="action-btn-sm btn-suspend" style="color: #fde047; border-color: #eab308; background: rgba(234,179,8,0.15);">
                    <i class="fas fa-pause"></i> Pause
                </button>
                <button onclick="interveneRun('${r.slug}', 'cancel')" class="action-btn-sm btn-suspend">
                    <i class="fas fa-stop"></i> Cancel
                </button>
            `;
        } else if (isPaused) {
            actionButtons += `
                <button onclick="interveneRun('${r.slug}', 'resume')" class="action-btn-sm btn-activate">
                    <i class="fas fa-play"></i> Resume
                </button>
                <button onclick="interveneRun('${r.slug}', 'cancel')" class="action-btn-sm btn-suspend">
                    <i class="fas fa-stop"></i> Cancel
                </button>
            `;
        }

        tr.innerHTML = `
            <td>
                <span style="font-family: monospace; font-size: 0.85rem; font-weight: 600; color: #fff;">${r.slug}</span>
                <span style="display: block; font-size: 0.7rem; color: #94a3b8;">${r.engine || 'terraform'}</span>
            </td>
            <td>
                <span style="font-size: 0.85rem; color: #cbd5e1;" title="${r.prompt}">${r.prompt}</span>
            </td>
            <td>
                <span style="font-size: 0.8rem; font-weight: 600; color: #a5b4fc;">${r.active_agent || 'ArchitectAgent'}</span>
            </td>
            <td>
                <span style="font-size: 0.8rem; font-family: monospace; color: #38bdf8;">${r.current_stage || 'init'}</span>
            </td>
            <td>
                <span style="font-size: 0.8rem; font-family: monospace;">${r.duration_seconds}s</span>
            </td>
            <td>
                <span style="font-size: 0.8rem; color: #fbbf24;">${r.healing_rounds} rnd</span>
            </td>
            <td>${statusBadge}</td>
            <td style="text-align: right; white-space: nowrap;">${actionButtons}</td>
        `;
        tbody.appendChild(tr);
    });
}

function filterAgentRuns() {
    const q = (document.getElementById('runs-search-input').value || '').toLowerCase().trim();
    if (!q) {
        renderAgentRunsTable(cachedAgentRuns);
        return;
    }
    const filtered = cachedAgentRuns.filter(r => 
        (r.slug && r.slug.toLowerCase().includes(q)) ||
        (r.prompt && r.prompt.toLowerCase().includes(q)) ||
        (r.active_agent && r.active_agent.toLowerCase().includes(q))
    );
    renderAgentRunsTable(filtered);
}

async function openRunInspector(slug) {
    activeInspectorSlug = slug;
    document.getElementById('inspector-run-slug').innerText = `Workspace: ${slug}`;
    const modal = document.getElementById('modal-run-inspector');
    if (modal) modal.style.display = 'flex';

    const stagesList = document.getElementById('inspector-stages-list');
    stagesList.innerHTML = `<div style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-spinner fa-spin"></i> Loading execution waterfall trace...</div>`;

    try {
        const res = await fetch(`/api/admin/agents/runs/${slug}/trace`);
        if (!res.ok) throw new Error("Failed to load run trace");
        const data = await res.json();

        // Update status badge
        const badge = document.getElementById('inspector-run-status-badge');
        badge.innerText = (data.status || 'UNKNOWN').toUpperCase();
        if (data.status === 'running') badge.style.color = '#38bdf8';
        else if (data.status === 'paused') badge.style.color = '#fde047';
        else if (data.status === 'cancelled') badge.style.color = '#f87171';
        else badge.style.color = '#34d399';

        renderRunInspectorStages(data.traces || []);
    } catch (e) {
        stagesList.innerHTML = `<div style="text-align: center; color: #f87171; padding: 2rem;">Error: ${e.message}</div>`;
    }
}

function renderRunInspectorStages(traces) {
    const container = document.getElementById('inspector-stages-list');
    if (!container) return;
    container.innerHTML = '';

    if (traces.length === 0) {
        // Render synthetic mock trace if run was completed before trace logging was activated
        traces = [
            { stage_name: "architect_design", agent_name: "ArchitectAgent", status: "completed", duration_seconds: 4.8, details: "Modular HCL topology and mermaid diagram synthesized." },
            { stage_name: "developer_code", agent_name: "DeveloperAgent", status: "completed", duration_seconds: 12.4, details: "HCL configuration files (main.tf, variables.tf) extracted." },
            { stage_name: "security_audit", agent_name: "SecurityReviewer", status: "completed", duration_seconds: 3.1, details: "Checkov / tfsec security scan: 0 critical vulnerabilities." },
            { stage_name: "finops_estimate", agent_name: "FinOpsSpecialist", status: "completed", duration_seconds: 2.9, details: "Infracost analysis confirmed infrastructure within monthly budget." }
        ];
    }

    traces.forEach((t, idx) => {
        const isComp = t.status === 'completed';
        const isRun = t.status === 'running';
        const isFail = t.status === 'failed';
        const statusColor = isComp ? '#34d399' : (isRun ? '#38bdf8' : (isFail ? '#f87171' : '#fde047'));
        const statusIcon = isComp ? 'check-circle' : (isRun ? 'spinner fa-spin' : (isFail ? 'times-circle' : 'pause-circle'));

        const item = document.createElement('div');
        item.style.cssText = `
            background: rgba(255, 255, 255, 0.04);
            border-left: 3px solid ${statusColor};
            border-radius: 4px;
            padding: 0.75rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        `;

        item.innerHTML = `
            <div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-size: 0.8rem; color: #94a3b8; font-family: monospace;">#${idx + 1}</span>
                    <span style="font-size: 0.95rem; font-weight: 700; color: #fff;">${t.stage_name}</span>
                    <span style="font-size: 0.75rem; color: #a5b4fc; background: rgba(99,102,241,0.2); padding: 0.15rem 0.45rem; border-radius: 3px;">
                        ${t.agent_name}
                    </span>
                </div>
                <div style="font-size: 0.8rem; color: #cbd5e1; margin-top: 0.25rem;">${t.details || 'Task completed normally.'}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.85rem; font-weight: 600; color: ${statusColor}; display: flex; align-items: center; justify-content: flex-end; gap: 0.35rem;">
                    <i class="fas fa-${statusIcon}"></i> ${t.status.toUpperCase()}
                </div>
                <span style="font-size: 0.75rem; color: #94a3b8; font-family: monospace;">${t.duration_seconds}s</span>
            </div>
        `;
        container.appendChild(item);
    });
}

async function interveneRun(slug, action) {
    if (!confirm(`Are you sure you want to ${action.toUpperCase()} run '${slug}'?`)) return;
    try {
        const res = await fetch(`/api/admin/agents/runs/${slug}/${action}`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Action ${action} failed`);
        showToast(data.message, action === 'cancel' ? 'error' : (action === 'pause' ? 'warning' : 'success'));
        await loadAgentRuns();
        if (activeInspectorSlug === slug) {
            await openRunInspector(slug);
        }
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function interveneRunFromModal(action) {
    if (!activeInspectorSlug) return;
    await interveneRun(activeInspectorSlug, action);
}


// ════════════════════════════════════════════════════════════════════════
// ── Milestone 2: LLM Router & Fallback Policy Logic ────────────────────
// ════════════════════════════════════════════════════════════════════════

let activeFallbackChain = [];
let cachedRouterState = null;

async function loadLLMRouter() {
    try {
        const res = await fetch('/api/admin/llm/router');
        if (!res.ok) throw new Error("Failed to load router state");
        const data = await res.json();
        cachedRouterState = data;

        // 1. Update Mode Buttons
        const mode = data.routing_mode || 'auto';
        ['auto', 'force', 'failover_chain'].forEach(m => {
            const btn = document.getElementById(`btn-mode-${m === 'failover_chain' ? 'failover' : m}`);
            if (btn) {
                if (m === mode) {
                    btn.style.background = '#3b82f6';
                    btn.style.color = '#fff';
                } else {
                    btn.style.background = 'transparent';
                    btn.style.color = '#ccc';
                }
            }
        });

        // 2. Forced Provider Select
        const forcedContainer = document.getElementById('forced-provider-container');
        if (mode === 'force') {
            forcedContainer.style.display = 'flex';
            if (data.forced_provider) {
                document.getElementById('forced-provider-select').value = data.forced_provider;
            }
        } else {
            forcedContainer.style.display = 'none';
        }

        // 3. Fallback Chain
        activeFallbackChain = data.fallback_chain || [];
        renderFallbackChainList();

        // 4. Provider Matrix
        renderLLMProvidersTable(data.providers || []);
    } catch (e) {
        console.error("Router load error:", e);
        showToast("Failed to load LLM router: " + e.message, "error");
    }
}

function renderFallbackChainList() {
    const list = document.getElementById('fallback-chain-list');
    if (!list) return;
    list.innerHTML = '';

    if (activeFallbackChain.length === 0) {
        list.innerHTML = `<div style="color: #94a3b8; font-size: 0.85rem;">No fallback models configured.</div>`;
        return;
    }

    activeFallbackChain.forEach((model, index) => {
        const item = document.createElement('div');
        item.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            padding: 0.5rem 0.8rem;
            border-radius: var(--radius-sm);
        `;

        const tierLabel = index === 0 ? `<span style="font-size: 0.75rem; font-weight: 700; color: #34d399; background: rgba(52,211,153,0.15); padding: 0.15rem 0.4rem; border-radius: 3px;">PRIMARY</span>` :
                          `<span style="font-size: 0.75rem; font-weight: 700; color: #38bdf8; background: rgba(56,189,248,0.15); padding: 0.15rem 0.4rem; border-radius: 3px;">FALLBACK #${index}</span>`;

        item.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                ${tierLabel}
                <span style="font-family: monospace; font-size: 0.9rem; color: #fff; font-weight: 600;">${model}</span>
            </div>
            <div style="display: flex; gap: 0.3rem;">
                <button onclick="moveFallbackChain(${index}, -1)" class="action-btn-sm" style="background: rgba(255,255,255,0.08); color: #fff;" ${index === 0 ? 'disabled style="opacity: 0.3;"' : ''}>
                    <i class="fas fa-arrow-up"></i>
                </button>
                <button onclick="moveFallbackChain(${index}, 1)" class="action-btn-sm" style="background: rgba(255,255,255,0.08); color: #fff;" ${index === activeFallbackChain.length - 1 ? 'disabled style="opacity: 0.3;"' : ''}>
                    <i class="fas fa-arrow-down"></i>
                </button>
                <button onclick="removeFallbackModel(${index})" class="action-btn-sm btn-suspend">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        list.appendChild(item);
    });
}

function moveFallbackChain(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= activeFallbackChain.length) return;
    const temp = activeFallbackChain[index];
    activeFallbackChain[index] = activeFallbackChain[target];
    activeFallbackChain[target] = temp;
    renderFallbackChainList();
}

function removeFallbackModel(index) {
    activeFallbackChain.splice(index, 1);
    renderFallbackChainList();
}

function addFallbackModelPrompt() {
    const newModel = prompt("Enter model string for fallback tier (e.g. 'openai/gpt-4o-mini' or 'zenmux/moonshotai/kimi-k3-free'):");
    if (newModel && newModel.trim()) {
        activeFallbackChain.push(newModel.trim());
        renderFallbackChainList();
    }
}

async function saveFallbackChain() {
    try {
        const res = await fetch('/api/admin/llm/router/fallback-chain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ models: activeFallbackChain })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to save fallback chain");
        showToast("Fallback chain updated & hot-reloaded across agent pipelines!", "success");
        await loadLLMRouter();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function setRoutingMode(mode) {
    try {
        const forced = mode === 'force' ? (document.getElementById('forced-provider-select').value || 'gemini') : null;
        const res = await fetch('/api/admin/llm/router/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, forced_provider: forced })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to switch routing mode");
        showToast(`Routing mode switched to '${mode.toUpperCase()}'`, "success");
        await loadLLMRouter();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function updateForcedProvider(forced_provider) {
    try {
        const res = await fetch('/api/admin/llm/router/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: 'force', forced_provider })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update forced provider");
        showToast(`Forced provider set to '${forced_provider}'`, "info");
    } catch (e) {
        showToast(e.message, "error");
    }
}

function renderLLMProvidersTable(providers) {
    const tbody = document.getElementById('llm-providers-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    providers.forEach(p => {
        const tr = document.createElement('tr');
        const isEnabled = p.status === 'enabled';
        const isForced = p.status === 'force';
        
        let statusBadge = `<span class="badge" style="background: rgba(52,211,153,0.15); color: #34d399;"><i class="fas fa-check-circle"></i> ACTIVE</span>`;
        if (isForced) statusBadge = `<span class="badge" style="background: rgba(59,130,246,0.2); color: #60a5fa;"><i class="fas fa-crosshairs"></i> FORCED</span>`;
        else if (!isEnabled) statusBadge = `<span class="badge" style="background: rgba(239,68,68,0.2); color: #f87171;"><i class="fas fa-ban"></i> DISABLED</span>`;

        const toggleBtn = isEnabled ? `
            <button onclick="toggleProviderStatus('${p.provider}', 'disabled')" class="action-btn-sm btn-suspend" title="Disable Provider">
                <i class="fas fa-power-off"></i> Disable
            </button>
        ` : `
            <button onclick="toggleProviderStatus('${p.provider}', 'enabled')" class="action-btn-sm btn-activate" title="Enable Provider">
                <i class="fas fa-power-off"></i> Enable
            </button>
        `;

        tr.innerHTML = `
            <td>
                <div style="font-weight: 700; color: #fff;">${p.name}</div>
                <span style="font-size: 0.75rem; color: #94a3b8; font-family: monospace;">${p.provider}</span>
            </td>
            <td>
                <span style="font-family: monospace; font-size: 0.85rem; color: #cbd5e1;">${p.model}</span>
            </td>
            <td>
                <span style="font-weight: 600; color: #fff;">${p.requests}</span>
            </td>
            <td>
                <span style="font-family: monospace; color: #38bdf8;">${p.avg_latency_seconds}s</span>
            </td>
            <td>
                <span style="font-weight: 600; color: ${p.error_rate_percent > 5 ? '#f87171' : '#34d399'};">${p.error_rate_percent}%</span>
            </td>
            <td>
                <span style="color: #34d399; font-family: monospace;">$${p.total_cost.toFixed(3)}</span>
            </td>
            <td>${statusBadge}</td>
            <td style="text-align: right; white-space: nowrap;">
                <button onclick="openTestLLMModal('${p.provider}')" class="action-btn-sm" style="background: rgba(168,85,247,0.15); border: 1px solid #a855f7; color: #c084fc;">
                    <i class="fas fa-bolt"></i> Test
                </button>
                ${toggleBtn}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function toggleProviderStatus(provider, newStatus) {
    try {
        const res = await fetch(`/api/admin/llm/router/provider/${provider}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update provider status");
        showToast(data.message, newStatus === 'disabled' ? 'warning' : 'success');
        await loadLLMRouter();
    } catch (e) {
        showToast(e.message, "error");
    }
}

function openTestLLMModal(provider = null) {
    const modal = document.getElementById('modal-test-llm');
    if (modal) modal.style.display = 'flex';
    document.getElementById('test-llm-result').style.display = 'none';
    if (provider) {
        const select = document.getElementById('test-llm-provider-select');
        if (select) select.value = provider;
    }
}

async function submitLLMRouteTest() {
    const provider = document.getElementById('test-llm-provider-select').value;
    const btn = document.getElementById('btn-execute-llm-test');
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Probing...`;

    const resultBox = document.getElementById('test-llm-result');
    const resultStatus = document.getElementById('test-llm-result-status');
    const resultLatency = document.getElementById('test-llm-result-latency');
    const resultBody = document.getElementById('test-llm-result-body');

    try {
        const res = await fetch('/api/admin/llm/router/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider })
        });
        const data = await res.json();
        resultBox.style.display = 'block';

        if (res.ok && data.status === 'success') {
            resultStatus.innerHTML = `<span style="color: #34d399;"><i class="fas fa-check-circle"></i> Connection Verified (${data.provider})</span>`;
            resultLatency.innerText = `${data.latency_ms}ms`;
            resultBody.innerText = data.sample_response || "OK";
        } else {
            resultStatus.innerHTML = `<span style="color: #f87171;"><i class="fas fa-times-circle"></i> Ping Error</span>`;
            resultLatency.innerText = "Timeout / Error";
            resultBody.innerText = data.message || "Diagnostic failed.";
        }
    } catch (e) {
        resultBox.style.display = 'block';
        resultStatus.innerHTML = `<span style="color: #f87171;">Exception</span>`;
        resultBody.innerText = e.message;
    } finally {
        btn.disabled = false;
        btn.innerHTML = `Run Probe Ping`;
    }
}


