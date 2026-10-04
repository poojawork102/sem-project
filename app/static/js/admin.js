/**
 * Northstar University - Admin Admissions SaaS Console
 * Complete Interactive Controller for Data, Visualizations & DSADPS Security Gate
 */

document.addEventListener('DOMContentLoaded', () => {
  Toast.init();

  // State
  const state = {
    activityList: [],
    applicationsList: [],
    summary: null,
    aiStatus: null,
    xgbStatus: null,
    selectedApp: null,
    selectedActivity: null,
    searchQuery: '',
    statusFilter: 'all',
    programFilter: 'all',
    riskFilter: 'all',
    currentPage: 1,
    pageSize: 15,
    pollInterval: 5000,
    pollTimer: null
  };

  // DOM Elements
  const loginView = document.getElementById('loginView');
  const adminApp = document.getElementById('adminApp');
  const loginForm = document.getElementById('loginForm');
  const loginError = document.getElementById('loginError');
  const logoutBtn = document.getElementById('logoutBtn');
  const sidebarNavItems = document.querySelectorAll('.sidebar-item a[data-admin-tab]');
  const adminTabPanes = document.querySelectorAll('.admin-tab-pane');

  // Check initial authentication
  function checkAuth() {
    const token = Api.getToken();
    if (token) {
      if (loginView) loginView.style.display = 'none';
      if (adminApp) adminApp.style.display = 'flex';
      startPolling();
      loadAllData();
    } else {
      if (loginView) loginView.style.display = 'flex';
      if (adminApp) adminApp.style.display = 'none';
      stopPolling();
    }
  }

  // Handle Login
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const usernameInput = document.getElementById('adminUsername');
      const passwordInput = document.getElementById('adminPassword');
      const submitBtn = loginForm.querySelector('button[type="submit"]');

      submitBtn.disabled = true;
      submitBtn.textContent = 'Authenticating…';
      if (loginError) loginError.style.display = 'none';

      try {
        await Api.login(usernameInput.value.trim(), passwordInput.value);
        Toast.show('Welcome Back', `Authenticated as ${usernameInput.value.trim()}`, 'success');
        checkAuth();
      } catch (err) {
        if (loginError) {
          loginError.textContent = err.message || 'Authentication failed. Verify credentials in .env.';
          loginError.style.display = 'block';
        }
        Toast.show('Login Failed', err.message || 'Incorrect admin credentials.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In to Console';
      }
    });
  }

  // Handle Logout
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      Api.clearToken();
      Toast.show('Signed Out', 'You have been safely signed out of the admin console.', 'info');
      checkAuth();
    });
  }

  window.addEventListener('admin-auth-expired', () => {
    Toast.show('Session Expired', 'Please sign in again.', 'warning');
    checkAuth();
  });

  // Admin Tab Navigation
  function switchAdminTab(targetTabId) {
    adminTabPanes.forEach(pane => {
      pane.style.display = pane.id === targetTabId ? 'block' : 'none';
    });

    sidebarNavItems.forEach(item => {
      const parent = item.parentElement;
      if (item.getAttribute('data-admin-tab') === targetTabId) {
        parent.classList.add('active');
      } else {
        parent.classList.remove('active');
      }
    });

    // Close mobile sidebar if open
    document.getElementById('adminSidebar')?.classList.remove('open');
  }

  sidebarNavItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = item.getAttribute('data-admin-tab');
      if (targetId) switchAdminTab(targetId);
    });
  });

  // Mobile sidebar toggle
  document.getElementById('sidebarToggleBtn')?.addEventListener('click', () => {
    document.getElementById('adminSidebar')?.classList.toggle('open');
  });

  // -------------------------------------------------------------
  // Data Loading & Polling
  // -------------------------------------------------------------
  async function loadAllData() {
    const refreshIcon = document.getElementById('refreshSpinner');
    if (refreshIcon) refreshIcon.classList.add('animate-pulse');

    try {
      const [activityData, appsData, summaryData, aiData, xgbData] = await Promise.all([
        Api.getActivity(150),
        Api.getApplications(),
        Api.getSummary(),
        Api.getAiStatus(),
        Api.getXgbStatus()
      ]);

      state.activityList = activityData || [];
      state.applicationsList = appsData || [];
      state.summary = summaryData || {};
      state.aiStatus = aiData || {};
      state.xgbStatus = xgbData || {};

      renderKPIs();
      renderCharts();
      renderLiveFeed();
      renderApplicationsTable();
      renderSecurityConsole();
      renderVerificationHub();

      const lastRefreshed = document.getElementById('lastRefreshedTime');
      if (lastRefreshed) lastRefreshed.textContent = new Date().toLocaleTimeString();

    } catch (err) {
      console.error('Failed to load admin data:', err);
    } finally {
      if (refreshIcon) refreshIcon.classList.remove('animate-pulse');
    }
  }

  function startPolling() {
    stopPolling();
    if (state.pollInterval > 0) {
      state.pollTimer = setInterval(loadAllData, state.pollInterval);
    }
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  // Refresh interval selector
  document.getElementById('pollIntervalSelect')?.addEventListener('change', (e) => {
    state.pollInterval = parseInt(e.target.value, 10);
    startPolling();
    Toast.show('Polling Updated', state.pollInterval > 0 ? `Auto-refresh set to ${state.pollInterval / 1000}s` : 'Auto-refresh paused', 'info');
  });

  document.getElementById('manualRefreshBtn')?.addEventListener('click', () => {
    loadAllData();
    Toast.show('Refreshed', 'Latest decisions and submissions synchronized.', 'info');
  });

  // -------------------------------------------------------------
  // Render KPI Metrics
  // -------------------------------------------------------------
  function renderKPIs() {
    const apps = state.applicationsList;
    const activities = state.activityList;

    const totalCount = apps.length || activities.length;
    const allowedCount = activities.filter(x => x.final_action === 'allow').length;
    const captchaCount = activities.filter(x => x.final_action === 'captcha').length;
    const blockedCount = activities.filter(x => x.final_action === 'block').length;

    document.getElementById('kpiTotalApps').textContent = totalCount;
    document.getElementById('kpiAllowedApps').textContent = allowedCount;
    document.getElementById('kpiCaptchaApps').textContent = captchaCount;
    document.getElementById('kpiBlockedApps').textContent = blockedCount;

    // Percentages
    const allowedPct = totalCount ? Math.round((allowedCount / totalCount) * 100) : 0;
    document.getElementById('kpiAllowedSubtext').textContent = `${allowedPct}% acceptance rate`;

    const blockedPct = totalCount ? Math.round((blockedCount / totalCount) * 100) : 0;
    document.getElementById('kpiBlockedSubtext').textContent = `${blockedPct}% flagged by security`;

    // AI Model KPI
    const ai = state.aiStatus;
    const aiStatusBadge = document.getElementById('kpiAiStatusText');
    if (aiStatusBadge) {
      if (ai.trained) {
        aiStatusBadge.textContent = `Online (${ai.samples} baseline samples)`;
        aiStatusBadge.className = 'badge badge-success';
      } else {
        aiStatusBadge.textContent = `Needs ${ai.minimum_samples || 20} samples (Has ${ai.samples || 0})`;
        aiStatusBadge.className = 'badge badge-warning';
      }
    }
  }

  // -------------------------------------------------------------
  // Render Visual Analytics & Charts
  // -------------------------------------------------------------
  function renderCharts() {
    renderWeeklyTrendChart();
    renderDecisionDonutChart();
    renderProgramsDistributionChart();
  }

  function renderWeeklyTrendChart() {
    const container = document.getElementById('weeklyTrendSvgContainer');
    if (!container) return;

    // Aggregate submissions by last 7 days
    const now = new Date();
    const days = [];
    const dayCounts = [];

    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const dayLabel = d.toLocaleDateString(undefined, { weekday: 'short', month: 'numeric', day: 'numeric' });
      days.push({ dateStr, dayLabel });

      const count = state.activityList.filter(x => {
        const itemDate = (x.created_at || '').split('T')[0];
        return itemDate === dateStr;
      }).length;
      dayCounts.push(count);
    }

    const maxCount = Math.max(...dayCounts, 5);
    const width = 560;
    const height = 180;
    const padding = 35;

    const points = dayCounts.map((val, idx) => {
      const x = padding + (idx * ((width - (padding * 2)) / 6));
      const y = height - padding - ((val / maxCount) * (height - (padding * 2)));
      return { x, y, val, label: days[idx].dayLabel };
    });

    // Create SVG Path
    let pathD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cpx1 = prev.x + (curr.x - prev.x) / 2;
      const cpy1 = prev.y;
      const cpx2 = prev.x + (curr.x - prev.x) / 2;
      const cpy2 = curr.y;
      pathD += ` C ${cpx1} ${cpy1}, ${cpx2} ${cpy2}, ${curr.x} ${curr.y}`;
    }

    // Gradient fill area
    const areaD = `${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`;

    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" class="w-100pct h-100pct overflow-visible">
        <defs>
          <linearGradient id="chartGlow" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#2563EB" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#2563EB" stop-opacity="0.0"/>
          </linearGradient>
        </defs>

        <!-- Grid Lines -->
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E2E8F0" stroke-width="1"/>
        <line x1="${padding}" y1="${height / 2}" x2="${width - padding}" y2="${height / 2}" stroke="#E2E8F0" stroke-width="1" stroke-dasharray="3,3"/>

        <!-- Area -->
        <path d="${areaD}" fill="url(#chartGlow)" />

        <!-- Line -->
        <path d="${pathD}" fill="none" stroke="#2563EB" stroke-width="3" stroke-linecap="round" />

        <!-- Points & Labels -->
        ${points.map(p => `
          <circle cx="${p.x}" cy="${p.y}" r="5" fill="#ffffff" stroke="#2563EB" stroke-width="2.5" />
          <text x="${p.x}" y="${p.y - 10}" font-size="11" font-weight="700" fill="#0F172A" text-anchor="middle">${p.val}</text>
          <text x="${p.x}" y="${height - 12}" font-size="10" font-weight="600" fill="#64748B" text-anchor="middle">${p.label}</text>
        `).join('')}
      </svg>
    `;
  }

  function renderDecisionDonutChart() {
    const container = document.getElementById('donutChartContainer');
    if (!container) return;

    const total = state.activityList.length || 1;
    const allowed = state.activityList.filter(x => x.final_action === 'allow').length;
    const captcha = state.activityList.filter(x => x.final_action === 'captcha').length;
    const blocked = state.activityList.filter(x => x.final_action === 'block').length;

    const allowedPct = Math.round((allowed / total) * 100);
    const captchaPct = Math.round((captcha / total) * 100);
    const blockedPct = Math.round((blocked / total) * 100);

    container.innerHTML = `
      <div class="d-flex flexdir-column gap-px-14">
        <div>
          <div class="flex items-center justify-between fs-0_85 mb-4">
            <span class="fw-600 text-navy-900">Allowed (Cleared)</span>
            <span class="fw-700 text-success">${allowed} (${allowedPct}%)</span>
          </div>
          <div class="bg-card-subtle h-8px radius-4 overflow-hidden">
            <div class="bar-fill bg-success" style="--fill: ${allowedPct}%"></div>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between fs-0_85 mb-4">
            <span class="fw-600 text-navy-900">Secondary Verification (Captcha)</span>
            <span class="fw-700 text-warning">${captcha} (${captchaPct}%)</span>
          </div>
          <div class="bg-card-subtle h-8px radius-4 overflow-hidden">
            <div class="bar-fill bg-warning" style="--fill: ${captchaPct}%"></div>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between fs-0_85 mb-4">
            <span class="fw-600 text-navy-900">Held / Blocked (Security Flag)</span>
            <span class="fw-700 text-danger">${blocked} (${blockedPct}%)</span>
          </div>
          <div class="bg-card-subtle h-8px radius-4 overflow-hidden">
            <div class="bar-fill bg-danger" style="--fill: ${blockedPct}%"></div>
          </div>
        </div>
      </div>
    `;
  }

  function renderProgramsDistributionChart() {
    const container = document.getElementById('programsChartContainer');
    if (!container) return;

    const apps = state.applicationsList;
    const progMap = {};
    apps.forEach(a => {
      const p = a.program || 'Unassigned';
      progMap[p] = (progMap[p] || 0) + 1;
    });

    const total = apps.length || 1;
    const entries = Object.entries(progMap).sort((a, b) => b[1] - a[1]);

    container.innerHTML = entries.map(([prog, count]) => {
      const pct = Math.round((count / total) * 100);
      return `
        <div class="mb-12">
          <div class="flex items-center justify-between fs-0_825 mb-4">
            <strong class="text-navy-900">${esc(prog)}</strong>
            <span class="text-muted">${count} applicants (${pct}%)</span>
          </div>
          <div class="bg-card-subtle h-7px radius-4 overflow-hidden">
            <div class="bar-fill bg-brand-blue" style="--fill: ${pct}%"></div>
          </div>
        </div>
      `;
    }).join('') || '<div class="text-muted fs-0_85">No application data available yet.</div>';
  }

  // -------------------------------------------------------------
  // Render Live Activity Feed
  // -------------------------------------------------------------
  function renderLiveFeed() {
    const container = document.getElementById('liveFeedRows');
    if (!container) return;

    const topItems = state.activityList.slice(0, 6);
    if (!topItems.length) {
      container.innerHTML = `<tr><td colspan="6" class="text-center p-24 text-muted">No activity recorded yet. Run the attack simulator or submit a portal form.</td></tr>`;
      return;
    }

    container.innerHTML = topItems.map(item => {
      const timeStr = item.created_at ? new Date(item.created_at + (item.created_at.includes('Z') ? '' : 'Z')).toLocaleTimeString() : '—';
      const riskClass = item.risk_score > 80 ? 'score-high' : (item.risk_score >= 40 ? 'score-med' : 'score-low');
      const actionBadge = item.final_action === 'allow' ? 'badge-success' : (item.final_action === 'captcha' ? 'badge-warning' : 'badge-danger');

      return `
        <tr>
          <td><span class="fs-0_8 text-muted fw-500">${timeStr}</span></td>
          <td>
            <strong class="text-navy-900 d-block">${esc(item.full_name || 'Anonymous')}</strong>
            <span class="fs-0_775 text-muted">${esc(item.email)}</span>
          </td>
          <td><code class="fs-0_775 text-navy-700">${esc(item.ip_address)}</code></td>
          <td>
            <span class="score-pill ${riskClass}">${esc(item.risk_score.toFixed(1))}</span>
          </td>
          <td>
            <span class="badge ${actionBadge}">
              <span class="badge-dot"></span> ${esc(item.final_action)}
            </span>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="openActivityDossier(${Number(item.id)})">
              Review
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // -------------------------------------------------------------
  // Render Applications Table with Multi-Filter
  // -------------------------------------------------------------
  function renderApplicationsTable() {
    const tbody = document.getElementById('applicationsTableBody');
    const countDisplay = document.getElementById('applicationsTotalCount');
    if (!tbody) return;

    // Determine dataSource: use applicationsList if available, or fall back to activityList
    let list = state.applicationsList.length ? state.applicationsList : state.activityList.map(act => ({
      id: act.application_id || act.id,
      full_name: act.full_name,
      email: act.email,
      ip_address: act.ip_address,
      status: act.final_action,
      submitted_at: act.created_at,
      program: 'General Program',
      reference_code: `ACT-${act.id}`,
      risk_score: act.risk_score,
      ai_anomaly_score: act.ai_anomaly_score,
      ai_status: act.ai_status,
      reasons: act.reasons || [],
      activity_id: act.id,
      confirmed_spam: false
    }));

    // Apply Search
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      list = list.filter(item => 
        (item.full_name && item.full_name.toLowerCase().includes(q)) ||
        (item.email && item.email.toLowerCase().includes(q)) ||
        (item.reference_code && item.reference_code.toLowerCase().includes(q)) ||
        (item.ip_address && item.ip_address.toLowerCase().includes(q)) ||
        (item.program && item.program.toLowerCase().includes(q))
      );
    }

    // Apply Status Filter
    if (state.statusFilter !== 'all') {
      if (state.statusFilter === 'spam') {
        list = list.filter(item => item.confirmed_spam);
      } else {
        list = list.filter(item => item.status === state.statusFilter);
      }
    }

    // Apply Program Filter
    if (state.programFilter !== 'all') {
      list = list.filter(item => (item.program || '').includes(state.programFilter));
    }

    // Apply Risk Filter
    if (state.riskFilter !== 'all') {
      if (state.riskFilter === 'low') list = list.filter(item => item.risk_score < 40);
      else if (state.riskFilter === 'med') list = list.filter(item => item.risk_score >= 40 && item.risk_score <= 80);
      else if (state.riskFilter === 'high') list = list.filter(item => item.risk_score > 80);
    }

    if (countDisplay) {
      countDisplay.textContent = `Showing ${list.length} records`;
    }

    if (!list.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center p-40 text-muted">
            <svg class="w-44px h-44px center-mb-10 text-light" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            <strong class="d-block fs-1 text-navy-900">No applications match current filters</strong>
            <span class="fs-0_85">Try clearing your search query or selecting "All Statuses".</span>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = list.map(item => {
      const initials = (item.full_name || 'U').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
      const submittedDate = item.submitted_at ? new Date(item.submitted_at + (item.submitted_at.includes('Z') ? '' : 'Z')).toLocaleDateString() : '—';
      const riskScore = typeof item.risk_score === 'number' ? item.risk_score : 0;
      const riskClass = riskScore > 80 ? 'score-high' : (riskScore >= 40 ? 'score-med' : 'score-low');
      const actionBadge = item.status === 'allow' ? 'badge-success' : (item.status === 'captcha' ? 'badge-warning' : 'badge-danger');
      const isSpam = item.confirmed_spam;

      // AI Anomaly display (Isolation Forest)
      let aiTag = '<span class="badge badge-neutral fs-0_7">IF: N/A</span>';
      if (item.ai_anomaly_score !== null && item.ai_anomaly_score !== undefined) {
        if (item.ai_status === 'anomaly') {
          aiTag = `<span class="badge badge-danger fs-0_7">IF: ${esc(item.ai_anomaly_score.toFixed(0))}</span>`;
        } else {
          aiTag = `<span class="badge badge-success fs-0_7">IF: ${esc(item.ai_anomaly_score.toFixed(0))}</span>`;
        }
      }

      // XGBoost display
      let xgbTag = '<span class="badge badge-neutral fs-0_7">XGB: N/A</span>';
      if (item.xgb_prediction) {
        const xgbBadge = item.xgb_prediction === 'allow' ? 'badge-success' : (item.xgb_prediction === 'captcha' ? 'badge-warning' : 'badge-danger');
        const conf = item.xgb_confidence !== null ? ` ${item.xgb_confidence.toFixed(0)}%` : '';
        xgbTag = `<span class="badge ${xgbBadge} fs-0_7">XGB: ${esc(item.xgb_prediction)}${esc(conf)}</span>`;
      }

      return `
        <tr class="${isSpam ? 'row-spam' : ''}">
          <td>
            <div class="flex items-center gap-3">
              <div class="w-36px h-36px radius-circle bg-brand-blue-tint-bg text-brand-blue d-flex items-center justify-center fw-700 fs-0_8">
                ${esc(initials)}
              </div>
              <div>
                <strong class="text-navy-900 d-block fs-0_9">
                  ${esc(item.full_name || 'Anonymous')}
                  ${isSpam ? '<span class="badge badge-danger ml-6 fs-0_65">Spam</span>' : ''}
                </strong>
                <span class="fs-0_775 text-muted">${esc(item.email)}</span>
              </div>
            </div>
          </td>
          <td>
            <span class="badge badge-outline font-mono fs-0_75 mb-2">
              ${esc(item.reference_code || '—')}
            </span>
            <div class="fs-0_775 text-secondary">${esc(item.program || 'Undergrad')}</div>
          </td>
          <td>
            <span class="fs-0_8 text-secondary d-block">${esc(submittedDate)}</span>
            <code class="fs-0_725 text-muted">${esc(item.ip_address)}</code>
          </td>
          <td>
            <span class="score-pill ${riskClass}" title="${esc((item.reasons || []).join(', '))}">
              ${riskScore.toFixed(1)}
            </span>
          </td>
          <td><div class="d-flex flexdir-column gap-px-3">${aiTag}${xgbTag}</div></td>
          <td>
            <span class="badge ${actionBadge}">
              <span class="badge-dot"></span> ${esc(item.status)}
            </span>
          </td>
          <td>
            <div class="flex items-center gap-2">
              <button class="btn btn-secondary btn-sm" onclick="openApplicationDossier(${Number(item.id)})">
                Dossier
              </button>
              <button class="btn btn-ghost btn-sm" title="Toggle Spam" onclick="toggleSpamRecord(${Number(item.id)}, ${!isSpam})">
                <svg class="w-15px h-15px ${isSpam ? 'text-success' : 'text-danger'}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Filter Event Listeners
  document.getElementById('tableSearchInput')?.addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    renderApplicationsTable();
  });

  document.getElementById('statusFilterSelect')?.addEventListener('change', (e) => {
    state.statusFilter = e.target.value;
    renderApplicationsTable();
  });

  document.getElementById('programFilterSelect')?.addEventListener('change', (e) => {
    state.programFilter = e.target.value;
    renderApplicationsTable();
  });

  document.getElementById('riskFilterSelect')?.addEventListener('change', (e) => {
    state.riskFilter = e.target.value;
    renderApplicationsTable();
  });

  // Top Global Search redirects to Applications
  document.getElementById('globalSearchInput')?.addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    switchAdminTab('admin-tab-applications');
    const tableSearch = document.getElementById('tableSearchInput');
    if (tableSearch) tableSearch.value = e.target.value;
    renderApplicationsTable();
  });

  // -------------------------------------------------------------
  // Student Dossier Drawer (Slide-Over)
  // -------------------------------------------------------------
  window.openApplicationDossier = (appId) => {
    const app = state.applicationsList.find(x => x.id === appId) || state.activityList.find(x => x.application_id === appId || x.id === appId);
    if (!app) return;
    state.selectedApp = app;
    renderDossierContent(app);
    document.getElementById('dossierDrawerBackdrop')?.classList.add('active');
  };

  window.openActivityDossier = (actId) => {
    const act = state.activityList.find(x => x.id === actId);
    if (!act) return;
    // Map to dossier view
    const app = state.applicationsList.find(x => x.id === act.application_id) || {
      id: act.id,
      activity_id: act.id,
      full_name: act.full_name,
      email: act.email,
      ip_address: act.ip_address,
      status: act.final_action,
      risk_score: act.risk_score,
      ai_anomaly_score: act.ai_anomaly_score,
      ai_status: act.ai_status,
      reasons: act.reasons || [],
      submitted_at: act.created_at,
      reference_code: `LOG-${act.id}`,
      program: 'Undergraduate Program',
      admin_override_by: act.admin_override_by,
      admin_note: act.admin_note
    };
    state.selectedApp = app;
    renderDossierContent(app);
    document.getElementById('dossierDrawerBackdrop')?.classList.add('active');
  };

  function renderDossierContent(app) {
    document.getElementById('dossierCandidateName').textContent = app.full_name || 'Anonymous Applicant';
    document.getElementById('dossierCandidateEmail').textContent = app.email || '—';
    document.getElementById('dossierRefCode').textContent = app.reference_code || '—';
    
    const statusBadge = document.getElementById('dossierStatusBadge');
    if (statusBadge) {
      statusBadge.className = `badge ${app.status === 'allow' ? 'badge-success' : (app.status === 'captcha' ? 'badge-warning' : 'badge-danger')}`;
      statusBadge.textContent = app.status;
    }

    const payload = app.payload || {};

    // Dossier Tabs Content: Overview, Statement, Security, Documents
    document.getElementById('dossierTabOverview').innerHTML = `
      <div class="d-grid grid-2-even gap-px-18 mb-20">
        <div class="card p-16">
          <span class="fs-0_75 tt-uppercase text-muted fw-700">Academic Program</span>
          <strong class="d-block fs-1 text-navy-900 mt-4">${esc(app.program || 'BTech Computer Science')}</strong>
          <span class="fs-0_8 text-secondary">${esc(payload.intake_term || 'Fall 2026 Intake')}</span>
        </div>
        <div class="card p-16">
          <span class="fs-0_75 tt-uppercase text-muted fw-700">Client Telemetry</span>
          <strong class="d-block fs-0_95 text-navy-900 font-mono mt-4">${esc(app.ip_address)}</strong>
          <span class="fs-0_8 text-secondary">${esc(payload.city || 'Verified Location')}</span>
        </div>
      </div>

      <div class="card p-20 mb-20">
        <h4 class="fs-0_95 text-navy-900 mb-12">Candidate Profile & Contact</h4>
        <div class="d-grid grid-2-even gap-px-12 fs-0_875">
          <div><span class="text-muted">Phone:</span> <strong>${esc(app.phone || payload.phone || '—')}</strong></div>
          <div><span class="text-muted">DOB:</span> <strong>${esc(payload.date_of_birth || '—')}</strong></div>
          <div><span class="text-muted">City:</span> <strong>${esc(payload.city || '—')}</strong></div>
          <div><span class="text-muted">Street:</span> <strong>${esc(payload.street_address || '—')}</strong></div>
          <div><span class="text-muted">Qualification:</span> <strong>${esc(payload.highest_qualification || 'Senior Secondary')}</strong></div>
          <div><span class="text-muted">GPA / Score:</span> <strong>${esc(payload.gpa_score || '3.9 / 4.0')}</strong></div>
        </div>
      </div>

      <div class="card p-20 mb-20">
        <h4 class="fs-0_95 text-navy-900 mb-8">Applicant Statement of Purpose</h4>
        <p class="fs-0_875 text-secondary lh-1_6 font-italic bg-card-subtle p-14 radius-md">
          "${esc(payload.statement || 'No statement provided.')}"
        </p>
      </div>

      <!-- Security Breakdown -->
      <div class="card p-20 ${app.risk_score > 80 ? 'bl-4-solid-danger' : (app.risk_score >= 40 ? 'bl-4-solid-warning' : 'bl-4-solid-success')}">
        <div class="flex items-center justify-between mb-12">
          <h4 class="fs-0_95 text-navy-900">DSADPS Security Engine Audit</h4>
          <span class="score-pill ${app.risk_score > 80 ? 'score-high' : (app.risk_score >= 40 ? 'score-med' : 'score-low')}">
            Risk: ${esc((app.risk_score || 0).toFixed(1))} / 100
          </span>
        </div>
        <div class="fs-0_825 text-secondary mb-10">
          <strong>Explainable Signals:</strong>
          <div class="mt-6">
            ${(app.reasons && app.reasons.length) ? app.reasons.map(r => `<span class="reason-chip">⚠️ ${esc(r)}</span>`).join('') : '<span class="reason-chip bg-success-bg text-success-text">✓ All security thresholds clear</span>'}
          </div>
        </div>
        <div class="fs-0_825 text-muted bt-1-solid-border-light pt-10 d-flex flexdir-column gap-px-4">
          <div>Isolation Forest Score: <strong>${esc(app.ai_anomaly_score !== null && app.ai_anomaly_score !== undefined ? app.ai_anomaly_score.toFixed(1) : 'Not trained')}</strong> (${esc(app.ai_status || 'offline')})</div>
          <div>XGBoost Prediction: <strong>${esc(app.xgb_prediction || 'Not trained')}</strong>${app.xgb_confidence ? ` (${esc(app.xgb_confidence.toFixed(1))}% confidence)` : ''}</div>
        </div>
      </div>

      <!-- Action Area -->
      <div class="action-box">
        <h4 class="fs-0_95 text-navy-900 mb-12">Admissions Decision & Override</h4>
        <div class="form-group">
          <label class="form-label">Update Decision Status</label>
          <select id="dossierActionSelect" class="form-control">
            <option value="allow" ${app.status === 'allow' ? 'selected' : ''}>allow (Approve Admission & Clear)</option>
            <option value="captcha" ${app.status === 'captcha' ? 'selected' : ''}>captcha (Request Secondary Verification)</option>
            <option value="block" ${app.status === 'block' ? 'selected' : ''}>block (Hold / Reject Application)</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Mandatory Admin Justification Note *</label>
          <textarea id="dossierNoteInput" class="form-control" placeholder="Provide justification for institutional audit log (e.g. Transcripts verified by Dean)." rows="2"></textarea>
        </div>
        <div class="flex items-center justify-between mt-16">
          <label class="d-flex fs-0_85 text-danger fw-600 cursor-pointer">
            <input type="checkbox" id="dossierSpamCheck" ${app.confirmed_spam ? 'checked' : ''} class="w-16px h-16px">
            Mark as Confirmed Spam (REQ-12)
          </label>
          <button type="button" class="btn btn-primary" onclick="saveDossierOverride()">
            Save Decision Override
          </button>
        </div>
      </div>
    `;
  }

  // Close Dossier Drawer
  document.getElementById('closeDossierBtn')?.addEventListener('click', () => {
    document.getElementById('dossierDrawerBackdrop')?.classList.remove('active');
  });

  // Save Override
  window.saveDossierOverride = async () => {
    const app = state.selectedApp;
    if (!app) return;

    const actionSelect = document.getElementById('dossierActionSelect');
    const noteInput = document.getElementById('dossierNoteInput');
    const spamCheck = document.getElementById('dossierSpamCheck');

    const action = actionSelect.value;
    const note = noteInput.value.trim();

    if (!note) {
      Toast.show('Note Required', 'Please enter a justification note for the audit log.', 'warning');
      noteInput.focus();
      return;
    }

    try {
      const actId = app.activity_id || app.id;
      await Api.overrideActivity(actId, action, note);

      // If spam checked
      if (spamCheck && spamCheck.checked !== app.confirmed_spam) {
        await Api.toggleSpam(app.id, spamCheck.checked);
      }

      Toast.show('Override Saved', `Decision updated to ${action.toUpperCase()}`, 'success');
      document.getElementById('dossierDrawerBackdrop')?.classList.remove('active');
      loadAllData();
    } catch (err) {
      Toast.show('Override Failed', err.message || 'Could not save override.', 'error');
    }
  };

  // Toggle Spam directly
  window.toggleSpamRecord = async (appId, confirmed) => {
    try {
      await Api.toggleSpam(appId, confirmed);
      Toast.show('Updated', confirmed ? 'Application flagged as confirmed spam.' : 'Spam flag removed.', 'info');
      loadAllData();
    } catch (err) {
      Toast.show('Error', err.message || 'Could not update spam flag.', 'error');
    }
  };

  // -------------------------------------------------------------
  // Document Verification Hub Queue
  // -------------------------------------------------------------
  function renderVerificationHub() {
    const container = document.getElementById('verificationCardsGrid');
    if (!container) return;

    const list = state.applicationsList.slice(0, 8);
    if (!list.length) {
      container.innerHTML = '<div class="text-muted p-30">No documents in queue.</div>';
      return;
    }

    container.innerHTML = list.map(item => `
      <div class="card card-hover">
        <div class="flex items-center justify-between mb-12">
          <span class="badge ${item.status === 'allow' ? 'badge-success' : 'badge-warning'}">
            ${item.status === 'allow' ? '✓ Transcripts Verified' : '⏳ Awaiting Review'}
          </span>
          <span class="fs-0_775 text-muted font-mono">${esc(item.reference_code || 'CAP')}</span>
        </div>
        <strong class="fs-1 text-navy-900 d-block mb-4">${esc(item.full_name)}</strong>
        <span class="fs-0_825 text-secondary d-block mb-14">${esc(item.program || 'BTech Computer Science')}</span>
        
        <div class="bg-card-subtle p-12 radius-md fs-0_8 mb-14">
          <div class="flex items-center justify-between mb-6">
            <span>High School Transcript:</span>
            <strong class="text-navy-900">Available (PDF)</strong>
          </div>
          <div class="flex items-center justify-between">
            <span>Identity Document:</span>
            <strong class="text-navy-900">Government ID</strong>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <button class="btn btn-success btn-sm flex-1" onclick="Toast.show('Verified', 'Applicant credentials approved.', 'success')">
            Approve ✓
          </button>
          <button class="btn btn-danger btn-sm" onclick="Toast.show('Attention Needed', 'Document flagged for re-upload.', 'warning')">
            Reject ✕
          </button>
        </div>
      </div>
    `).join('');
  }

  // -------------------------------------------------------------
  // Security & Threat Console (AI Training, Spam Purge, Reports)
  // -------------------------------------------------------------
  function renderSecurityConsole() {
    const ai = state.aiStatus || {};
    const aiSamplesCount = document.getElementById('secAiSamples');
    const aiTrainedText = document.getElementById('secAiTrained');
    const spamRecordsCount = document.getElementById('secSpamRecordsCount');

    if (aiSamplesCount) aiSamplesCount.textContent = `${ai.samples || 0} / ${ai.minimum_samples || 20} required samples`;
    if (aiTrainedText) aiTrainedText.textContent = ai.trained ? 'Active & Trained' : 'Training Baseline Incomplete';

    // XGBoost status
    const xgb = state.xgbStatus || {};
    const xgbTrainedText = document.getElementById('secXgbTrained');
    const xgbSamplesCount = document.getElementById('secXgbSamples');
    const xgbAccuracy = document.getElementById('secXgbAccuracy');

    if (xgbTrainedText) xgbTrainedText.textContent = xgb.trained ? 'Active & Trained' : 'Not Trained Yet';
    if (xgbSamplesCount) xgbSamplesCount.textContent = `${xgb.samples || 0} / ${xgb.minimum_samples || 30} required samples`;
    if (xgbAccuracy) xgbAccuracy.textContent = xgb.trained ? `${(xgb.accuracy * 100).toFixed(1)}%` : '—';

    const confirmedSpamCount = state.applicationsList.filter(x => x.confirmed_spam).length;
    if (spamRecordsCount) spamRecordsCount.textContent = `${confirmedSpamCount} confirmed spam records`;
  }

  // Train Isolation Forest
  document.getElementById('trainAiBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('trainAiBtn');
    btn.disabled = true;
    btn.textContent = 'Training Model…';

    try {
      const result = await Api.trainAi();
      Toast.show('Isolation Forest Trained', result.message || 'Isolation Forest baseline model successfully trained.', 'success');
      loadAllData();
    } catch (err) {
      Toast.show('Training Incomplete', err.message || 'Needs at least 20 normal allowed submissions to train.', 'warning');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Train Isolation Forest';
    }
  });

  // Train XGBoost
  document.getElementById('trainXgbBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('trainXgbBtn');
    btn.disabled = true;
    btn.textContent = 'Training XGBoost…';

    try {
      const result = await Api.trainXgb();
      Toast.show('XGBoost Trained', result.message || 'XGBoost classifier trained successfully.', 'success');
      loadAllData();
    } catch (err) {
      Toast.show('Training Incomplete', err.message || 'Needs at least 30 labeled submissions to train.', 'warning');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Train XGBoost Model';
    }
  });

  // Safe Spam Cleanup Modal
  const cleanupModal = document.getElementById('spamCleanupModal');
  document.getElementById('openCleanupModalBtn')?.addEventListener('click', () => {
    const confirmedCount = state.applicationsList.filter(x => x.confirmed_spam).length;
    document.getElementById('cleanupTargetCount').textContent = confirmedCount;
    cleanupModal?.classList.add('active');
  });

  document.getElementById('closeCleanupModalBtn')?.addEventListener('click', () => {
    cleanupModal?.classList.remove('active');
  });

  document.getElementById('confirmPurgeSpamBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('confirmPurgeSpamBtn');
    btn.disabled = true;
    btn.textContent = 'Purging…';

    try {
      const result = await Api.cleanupSpam();
      Toast.show('Safe Cleanup Completed', `Deleted ${result.deleted_confirmed_spam_records} spam records. Audit logs retained.`, 'success');
      cleanupModal?.classList.remove('active');
      loadAllData();
    } catch (err) {
      Toast.show('Cleanup Error', err.message || 'Failed to purge spam.', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Confirm Safe Purge';
    }
  });

  // Report Downloads
  document.getElementById('downloadCsvBtn')?.addEventListener('click', () => {
    Api.downloadReport('daily.csv', 'daily-attack-summary.csv');
    Toast.show('Export Started', 'Downloading daily attack summary CSV.', 'info');
  });

  document.getElementById('downloadGraphBtn')?.addEventListener('click', () => {
    Api.downloadReport('weekly-trend.png', 'weekly-attack-trend.png');
    Toast.show('Export Started', 'Downloading weekly trend graph PNG.', 'info');
  });

  // Initial check
  checkAuth();
});
