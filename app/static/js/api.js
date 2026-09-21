/**
 * Northstar University Admissions Platform - Core API & UI Helper Module
 */

// Toast notification manager
const Toast = {
  container: null,

  init() {
    if (!this.container) {
      this.container = document.getElementById('toast-container');
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        document.body.appendChild(this.container);
      }
    }
  },

  show(title, message = '', type = 'info', duration = 4500) {
    this.init();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
      success: `<svg class="toast-icon" fill="none" viewBox="0 0 24 24" stroke="#10B981" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
      error: `<svg class="toast-icon" fill="none" viewBox="0 0 24 24" stroke="#EF4444" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
      warning: `<svg class="toast-icon" fill="none" viewBox="0 0 24 24" stroke="#F59E0B" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>`,
      info: `<svg class="toast-icon" fill="none" viewBox="0 0 24 24" stroke="#0284C7" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`
    };

    toast.innerHTML = `
      ${icons[type] || icons.info}
      <div class="toast-content">
        <div class="toast-title">${title}</div>
        ${message ? `<div class="toast-message">${message}</div>` : ''}
      </div>
      <button class="toast-close" aria-label="Close">&times;</button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => {
      this.dismiss(toast);
    });

    this.container.appendChild(toast);
    // Trigger animation
    requestAnimationFrame(() => toast.classList.add('show'));

    if (duration > 0) {
      setTimeout(() => this.dismiss(toast), duration);
    }
  },

  dismiss(toast) {
    toast.classList.remove('show');
    setTimeout(() => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    }, 300);
  }
};

// API Client
const Api = {
  TOKEN_KEY: 'dsadps_admin_token',

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY) || '';
  },

  setToken(token) {
    localStorage.setItem(this.TOKEN_KEY, token);
  },

  clearToken() {
    localStorage.removeItem(this.TOKEN_KEY);
  },

  getHeaders(requiresAuth = false) {
    const headers = { 'Content-Type': 'application/json' };
    if (requiresAuth) {
      const token = this.getToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }
    return headers;
  },

  async request(endpoint, options = {}, requiresAuth = false) {
    const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const headers = { ...this.getHeaders(requiresAuth), ...(options.headers || {}) };

    try {
      const response = await fetch(url, { ...options, headers });
      
      // If unauthorized on a protected call
      if (response.status === 401 && requiresAuth) {
        this.clearToken();
        window.dispatchEvent(new CustomEvent('admin-auth-expired'));
        throw new Error('Session expired or unauthorized. Please sign in again.');
      }

      if (!response.ok) {
        let errorMsg = `Request failed (${response.status})`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorData.message || errorMsg;
        } catch (_) {}
        const error = new Error(errorMsg);
        error.status = response.status;
        throw error;
      }

      // Handle non-json downloads
      const contentType = response.headers.get('content-type');
      if (contentType && (contentType.includes('text/csv') || contentType.includes('image/png') || contentType.includes('application/octet-stream'))) {
        return await response.blob();
      }

      return await response.json();
    } catch (err) {
      console.error(`[API Error] ${options.method || 'GET'} ${url}:`, err);
      throw err;
    }
  },

  // Auth
  async login(username, password) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  },

  // Portal Student Endpoints
  async submitApplication(payload) {
    return await this.request('/v1/portal/applications', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async getApplicationStatus(reference_code, email) {
    return await this.request('/v1/portal/application-status', {
      method: 'POST',
      body: JSON.stringify({ reference_code, email })
    });
  },

  // Admin Endpoints
  async getActivity(limit = 100) {
    return await this.request(`/v1/admin/activity?limit=${limit}`, { method: 'GET' }, true);
  },

  async getApplications() {
    return await this.request('/v1/admin/applications', { method: 'GET' }, true);
  },

  async overrideActivity(activityId, action, note) {
    return await this.request(`/v1/admin/activity/${activityId}/override`, {
      method: 'PUT',
      body: JSON.stringify({ action, note })
    }, true);
  },

  async toggleSpam(appId, confirmed = true) {
    return await this.request(`/v1/admin/applications/${appId}/spam?confirmed=${confirmed}`, {
      method: 'PUT'
    }, true);
  },

  async getSummary() {
    return await this.request('/v1/admin/reports/summary', { method: 'GET' }, true);
  },

  async getAiStatus() {
    return await this.request('/v1/admin/ai/status', { method: 'GET' }, true);
  },

  async trainAi() {
    return await this.request('/v1/admin/ai/train', { method: 'POST' }, true);
  },

  async cleanupSpam() {
    return await this.request('/v1/admin/cleanup', { method: 'POST' }, true);
  },

  async downloadReport(kind, filename = '') {
    const blob = await this.request(`/v1/admin/reports/${kind}`, { method: 'POST' }, true);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || kind;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },

  // XGBoost ML endpoints
  async getXgbStatus() {
    return await this.request('/v1/admin/ai/xgboost/status', { method: 'GET' }, true);
  },

  async trainXgb() {
    return await this.request('/v1/admin/ai/xgboost/train', { method: 'POST' }, true);
  },

  // Gemini Admin Chatbot
  async sendChatMessage(message, history = []) {
    return await this.request('/v1/admin/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history })
    }, true);
  }
};

window.Toast = Toast;
window.Api = Api;
