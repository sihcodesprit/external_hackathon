/**
 * NetWatch SOC — Shared JavaScript Utilities
 * Handles: sidebar toggle, toast notifications, formatters, badge helpers, gauge rendering
 */

(function() {
  'use strict';

  // ============================================================
  // DOM Ready
  // ============================================================
  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else { fn(); }
  }

  // ============================================================
  // Sidebar Toggle
  // ============================================================
  function initSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const toggle = document.getElementById('sidebarToggle');
    if (!sidebar || !toggle) return;

    // Load persisted state
    const collapsed = localStorage.getItem('nw_sidebar_collapsed') === 'true';
    if (collapsed) sidebar.classList.add('collapsed');

    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem('nw_sidebar_collapsed', sidebar.classList.contains('collapsed'));
    });

    // Keyboard: Ctrl+B to toggle
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.key === 'b') {
        e.preventDefault();
        sidebar.classList.toggle('collapsed');
        localStorage.setItem('nw_sidebar_collapsed', sidebar.classList.contains('collapsed'));
      }
    });
  }

  // ============================================================
  // Toast Notifications
  // ============================================================
  const toastContainer = (() => {
    let el = document.getElementById('toastContainer');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toastContainer';
      el.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:500;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
      document.body.appendChild(el);
    }
    return el;
  })();

  window.showToast = function(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.style.cssText = `
      display:flex;align-items:center;gap:12px;padding:12px 16px;
      background:var(--bg-card);border:1px solid var(--border);
      border-radius:10px;box-shadow:var(--shadow-lg);
      min-width:280px;max-width:420px;pointer-events:auto;
      animation:slideIn 0.3s ease;color:var(--text-primary);
    `;
    
    const icons = {
      success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
      danger: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
      warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
      info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    };
    
    const colors = {
      success: 'var(--success)',
      danger: 'var(--danger)',
      warning: 'var(--warning)',
      info: 'var(--info)'
    };
    
    toast.innerHTML = `
      <span style="color:${colors[type] || colors.info};flex-shrink:0;">${icons[type] || icons.info}</span>
      <span style="flex:1;font-size:0.85rem;">${message}</span>
      <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:4px;line-height:1;">✕</button>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  };

  // Add toast animations
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn { from { opacity:0; transform:translateX(100px); } to { opacity:1; transform:translateX(0); } }
    @keyframes slideOut { from { opacity:1; transform:translateX(0); } to { opacity:0; transform:translateX(100px); } }
  `;
  document.head.appendChild(style);

  // Auto-convert Flask flash messages to toasts
  function convertFlashMessages() {
    const flashes = document.querySelectorAll('.flashes li, .alert');
    flashes.forEach(el => {
      const text = el.textContent.trim();
      const classList = el.className || '';
      let type = 'info';
      if (classList.includes('success') || classList.includes('good')) type = 'success';
      else if (classList.includes('danger') || classList.includes('error')) type = 'danger';
      else if (classList.includes('warning')) type = 'warning';
      if (text) showToast(text, type);
      el.remove();
    });
  }

  // ============================================================
  // Formatters
  // ============================================================
  window.formatPercent = function(value, decimals = 0) {
    if (value == null) return '—';
    const pct = (value * 100).toFixed(decimals);
    return pct + '%';
  };

  window.formatNumber = function(value, decimals = 0) {
    if (value == null) return '—';
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  window.formatBytes = function(bytes) {
    if (!bytes && bytes !== 0) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let val = bytes;
    while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
    return val.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
  };

  window.formatDateTime = function(isoString) {
    if (!isoString) return '—';
    try { return new Date(isoString).toLocaleString(); } catch { return isoString; }
  };

  window.truncate = function(str, length = 40) {
    if (!str) return '—';
    return str.length > length ? str.slice(0, length) + '…' : str;
  };

  // ============================================================
  // Badge Helpers
  // ============================================================
  window.getRiskBadgeClass = function(risk) {
    if (risk >= 0.7) return 'badge-danger';
    if (risk >= 0.4) return 'badge-warning';
    if (risk >= 0.15) return 'badge-info';
    return 'badge-success';
  };

  window.getRiskLabel = function(risk) {
    if (risk >= 0.7) return 'CRITICAL';
    if (risk >= 0.4) return 'HIGH';
    if (risk >= 0.15) return 'MEDIUM';
    if (risk >= 0.05) return 'LOW';
    return 'BENIGN';
  };

  window.getStageBadgeClass = function(stage) {
    const s = (stage || '').toLowerCase();
    if (s.includes('recon') || s.includes('discovery')) return 'badge-info';
    if (s.includes('initial') || s.includes('execution') || s.includes('privilege') || s.includes('defense') || s.includes('credential')) return 'badge-warning';
    if (s.includes('lateral') || s.includes('collection') || s.includes('exfil') || s.includes('command') || s.includes('impact')) return 'badge-danger';
    return 'badge-neutral';
  };

  // ============================================================
  // Risk Gauge SVG Generator
  // ============================================================
  window.renderRiskGauge = function(container, risk, size = 120, showLabel = true) {
    if (!container) return;
    const circumference = 2 * Math.PI * 45; // r=45
    const offset = circumference * (1 - Math.min(Math.max(risk, 0), 1));
    const color = risk >= 0.7 ? 'var(--danger)' : risk >= 0.4 ? 'var(--warning)' : 'var(--accent)';
    
    container.innerHTML = `
      <svg width="${size}" height="${size}" viewBox="0 0 100 100" style="transform:rotate(-90deg);">
        <circle class="risk-gauge-bg" cx="50" cy="50" r="45" stroke-width="8" fill="none" stroke="var(--border)"/>
        <circle class="risk-gauge-fill" cx="50" cy="50" r="45" stroke-width="8" fill="none"
          stroke="${color}" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
          stroke-linecap="round" style="transition:stroke-dashoffset 1s ease-out;"/>
      </svg>
      ${showLabel ? `<div class="risk-gauge-text">
        <span class="risk-gauge-value">${formatPercent(risk, 0)}</span>
        <span class="risk-gauge-label">Risk</span>
      </div>` : ''}
    `;
  };

  // ============================================================
  // Chart.js Defaults
  // ============================================================
  window.initChartDefaults = function() {
    if (typeof Chart !== 'undefined') {
      Chart.defaults.color = '#94a3b8';
      Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      Chart.defaults.font.size = 11;
      Chart.defaults.plugins.legend.labels.usePointStyle = true;
      Chart.defaults.plugins.legend.labels.padding = 16;
      Chart.defaults.scales = {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' } }
      };
    }
  };

  // ============================================================
  // File Upload Zone
  // ============================================================
  function initUploadZones() {
    document.querySelectorAll('.upload-zone').forEach(zone => {
      const input = zone.querySelector('input[type="file"]');
      const fileInfo = zone.querySelector('.upload-zone-file');
      const hint = zone.querySelector('.upload-zone-hint');
      
      if (!input) return;
      
      ['dragenter', 'dragover'].forEach(evt => {
        zone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); zone.classList.add('drag-over'); });
      });
      ['dragleave', 'drop'].forEach(evt => {
        zone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); zone.classList.remove('drag-over'); });
      });
      
      zone.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files.length) { input.files = files; input.dispatchEvent(new Event('change')); }
      });
      
      input.addEventListener('change', () => {
        if (input.files.length) {
          const f = input.files[0];
          if (fileInfo) {
            fileInfo.textContent = f.name + ' (' + formatBytes(f.size) + ')';
            fileInfo.classList.add('visible');
          }
          if (hint) hint.style.display = 'none';
        } else {
          if (fileInfo) { fileInfo.classList.remove('visible'); fileInfo.textContent = ''; }
          if (hint) hint.style.display = 'block';
        }
      });
      
      zone.addEventListener('click', (e) => {
        if (e.target === zone || zone.contains(e.target) && e.target !== input) input.click();
      });
    });
  }

  // ============================================================
  // Active Nav Highlight
  // ============================================================
  function highlightActiveNav() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
      const href = item.getAttribute('href');
      if (href && (path === href || (href !== '/' && path.startsWith(href)))) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  }

  // ============================================================
  // Table Sort (simple)
  // ============================================================
  window.makeTableSortable = function(table) {
    if (!table || table.dataset.sortable === 'true') return;
    table.dataset.sortable = 'true';
    table.querySelectorAll('th').forEach((th, idx) => {
      th.style.cursor = 'pointer';
      th.style.userSelect = 'none';
      th.addEventListener('click', () => {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const isAsc = th.dataset.sort !== 'asc';
        
        rows.sort((a, b) => {
          const aVal = a.cells[idx].textContent.trim();
          const bVal = b.cells[idx].textContent.trim();
          const aNum = parseFloat(aVal);
          const bNum = parseFloat(bVal);
          let cmp = 0;
          if (!isNaN(aNum) && !isNaN(bNum)) cmp = aNum - bNum;
          else cmp = aVal.localeCompare(bVal);
          return isAsc ? cmp : -cmp;
        });
        
        tbody.innerHTML = '';
        rows.forEach(r => tbody.appendChild(r));
        
        table.querySelectorAll('th').forEach(h => delete h.dataset.sort);
        th.dataset.sort = isAsc ? 'asc' : 'desc';
      });
    });
  };

  // ============================================================
  // API Helper
  // ============================================================
  window.api = {
    get: (url) => fetch(url).then(r => r.ok ? r.json() : Promise.reject(r)),
    post: (url, data) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }).then(r => r.ok ? r.json() : Promise.reject(r)),
    upload: (url, formData) => fetch(url, { method: 'POST', body: formData }).then(r => r.ok ? r.json() : Promise.reject(r))
  };

  // ============================================================
  // Initialization
  // ============================================================
  onReady(() => {
    initSidebar();
    initUploadZones();
    highlightActiveNav();
    convertFlashMessages();
    initChartDefaults();
    
    // Make all data-tables sortable
    document.querySelectorAll('.data-table').forEach(makeTableSortable);
  });

})();