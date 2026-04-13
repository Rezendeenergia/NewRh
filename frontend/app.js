/**
 * Rezende Energia — Portal de Carreiras
 */

const API_BASE = '';

let sessionToken    = null;
let sessionUsername = null;
let selectedJob     = null;
let currentPage     = 1;
let chartInstances  = {};
let allJobs         = [];   // cache para busca local

// Estado global do usuário logado
const AppState = { role: null, username: null };



// ── Microsoft SSO callback handler ───────────────────────────
(function() {
  const hash = window.location.hash;
  if (!hash.includes('ms-token=')) return;
  const params = new URLSearchParams(hash.slice(1));
  const token  = params.get('ms-token');
  const user   = params.get('ms-user');
  const role   = params.get('ms-role');
  const name   = params.get('ms-name');
  const errMsg = params.get('ms-error');

  // Limpa o hash da URL
  history.replaceState(null, '', window.location.pathname);

  if (errMsg) {
    // Mostra erro no painel de login
    setTimeout(() => {
      const alert = document.getElementById('login-alert');
      if (alert) { alert.textContent = decodeURIComponent(errMsg.replace(/\+/g,' ')); alert.style.display='block'; }
      // Ativa aba do gestor
      document.querySelectorAll('.nav__tab').forEach(t => t.classList.remove('nav__tab--active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('panel--active'));
      document.querySelector('[data-panel="manager"]')?.classList.add('nav__tab--active');
      document.getElementById('panel-manager')?.classList.add('panel--active');
    }, 300);
    return;
  }

  if (token && user) {
    sessionToken    = token;
    sessionUsername = user;
    AppState.role   = role;
    AppState.username = user;
    // Ativa dashboard
    setTimeout(() => {
      document.getElementById('manager-login').style.display    = 'none';
      document.getElementById('manager-dashboard').style.display = 'block';
      document.getElementById('dashboard-greeting').textContent  = `Olá, ${name || user} 👋`;
      document.querySelectorAll('.nav__tab').forEach(t => t.classList.remove('nav__tab--active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('panel--active'));
      document.querySelector('[data-panel="manager"]')?.classList.add('nav__tab--active');
      document.getElementById('panel-manager')?.classList.add('panel--active');
      Manager.loadStats();
      Manager.loadJobList();
      Solicitacoes.loadBadge();
    }, 100);
  }
})();

// ── CandidatoPortal ──────────────────────────────────────────
const CandidatoPortal = {
  _token: null,

  abrir() {
    const overlay = document.getElementById('candidato-portal-overlay');
    if (overlay) overlay.style.display = 'flex';
    if (this._token) this._showDashboard();
    else this.setTab('login');
  },

  fechar() {
    const el = document.getElementById('candidato-portal-overlay');
    if (el) el.style.display = 'none';
  },

  logout() {
    this._token = null;
    document.getElementById('cand-login-panel').style.display    = 'block';
    document.getElementById('cand-dashboard-panel').style.display = 'none';
    this.setTab('login');
  },

  setTab(tab) {
    // Esconde todos os forms
    ['login','primeiro','recuperar'].forEach(t => {
      const el = document.getElementById('cand-form-' + t);
      if (el) el.style.display = 'none';
    });
    // Reseta abas visuais
    const tabLogin   = document.getElementById('cand-tab-login');
    const tabPrimeiro = document.getElementById('cand-tab-primeiro');
    if (tabLogin)    { tabLogin.style.borderBottomColor = 'transparent'; tabLogin.style.color = '#9AA3B2'; }
    if (tabPrimeiro) { tabPrimeiro.style.borderBottomColor = 'transparent'; tabPrimeiro.style.color = '#9AA3B2'; }

    // Mostra form correto
    const form = document.getElementById('cand-form-' + tab);
    if (form) form.style.display = 'block';

    if (tab === 'login' && tabLogin) {
      tabLogin.style.borderBottomColor = '#FF6A00'; tabLogin.style.color = '#FF6A00';
    } else if (tab === 'primeiro' && tabPrimeiro) {
      tabPrimeiro.style.borderBottomColor = '#FF6A00'; tabPrimeiro.style.color = '#FF6A00';
    }
  },

  async login() {
    const email = document.getElementById('cand-email')?.value?.trim();
    const senha = document.getElementById('cand-senha')?.value;
    const alertEl = document.getElementById('cand-login-alert');
    const btn     = document.getElementById('cand-btn-login');
    if (!email || !senha) {
      alertEl.textContent = '❌ Preencha e-mail e senha.';
      alertEl.style.display = 'block'; return;
    }
    alertEl.style.display = 'none';
    btn.textContent = 'Entrando...'; btn.disabled = true;
    try {
      const r = await fetch('/api/candidato/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, senha }),
      });
      const d = await r.json();
      if (!r.ok) {
        if (d.primeiroAcesso) {
          alertEl.innerHTML = `⚠️ ${d.message} <a href="#" onclick="CandidatoPortal.setTab('primeiro');return false;" style="color:#FF6A00;">Clique aqui</a>`;
        } else {
          alertEl.textContent = '❌ ' + (d.message || 'Erro ao autenticar');
        }
        alertEl.style.display = 'block'; return;
      }
      this._token = d.token;
      document.getElementById('cand-nome').textContent = d.nome;
      this._showDashboard();
    } catch(e) {
      alertEl.textContent = '❌ Erro de conexão'; alertEl.style.display = 'block';
    } finally {
      btn.textContent = 'Entrar'; btn.disabled = false;
    }
  },

  async solicitarAcesso() {
    const email   = document.getElementById('cand-email-primeiro')?.value?.trim();
    const alertEl = document.getElementById('cand-primeiro-alert');
    const btn     = document.getElementById('cand-btn-primeiro');
    if (!email) { alertEl.textContent = '❌ Informe seu e-mail.'; alertEl.style.display = 'block'; return; }
    alertEl.style.display = 'none';
    btn.textContent = 'Enviando...'; btn.disabled = true;
    try {
      const r = await fetch('/api/candidato/primeiro-acesso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const d = await r.json();
      alertEl.textContent = r.ok ? '✅ ' + d.message : '❌ ' + (d.message || 'Erro');
      alertEl.style.display = 'block';
      alertEl.style.background = r.ok ? 'rgba(46,204,113,.1)' : 'rgba(255,82,82,.1)';
      alertEl.style.color = r.ok ? '#2ECC71' : '#FF5252';
    } catch(e) {
      alertEl.textContent = '❌ Erro de conexão'; alertEl.style.display = 'block';
    } finally {
      btn.textContent = 'Enviar Link de Acesso'; btn.disabled = false;
    }
  },

  async recuperarSenha() {
    const email   = document.getElementById('cand-email-recuperar')?.value?.trim();
    const alertEl = document.getElementById('cand-recuperar-alert');
    const btn     = document.getElementById('cand-btn-recuperar');
    if (!email) { alertEl.textContent = '❌ Informe seu e-mail.'; alertEl.style.display = 'block'; return; }
    alertEl.style.display = 'none';
    btn.textContent = 'Enviando...'; btn.disabled = true;
    try {
      const r = await fetch('/api/candidato/recuperar-senha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const d = await r.json();
      alertEl.textContent = r.ok ? '✅ ' + d.message : '❌ ' + (d.message || 'Erro');
      alertEl.style.display = 'block';
      alertEl.style.background = r.ok ? 'rgba(46,204,113,.1)' : 'rgba(255,82,82,.1)';
      alertEl.style.color = r.ok ? '#2ECC71' : '#FF5252';
    } catch(e) {
      alertEl.textContent = '❌ Erro de conexão'; alertEl.style.display = 'block';
    } finally {
      btn.textContent = 'Enviar Link'; btn.disabled = false;
    }
  },

  async _showDashboard() {
    document.getElementById('cand-login-panel').style.display     = 'none';
    document.getElementById('cand-dashboard-panel').style.display = 'flex';
    this.setDashTab('candidaturas');
    await this._loadCandidaturas();
    await this._loadDocs();
  },

  setDashTab(tab) {
    // Abas
    const tabs = ['candidaturas', 'documentos'];
    tabs.forEach(t => {
      const btn    = document.getElementById(`tab-${t}`);
      const painel = document.getElementById(`painel-${t}`);
      const isActive = t === tab;
      if (btn) {
        btn.style.borderBottomColor = isActive ? '#FF6A00' : 'transparent';
        btn.style.color = isActive ? '#FF6A00' : '#9AA3B2';
      }
      if (painel) painel.style.display = isActive ? 'block' : 'none';
    });
    if (tab === 'documentos') this._loadDocs();
  },

  abrirUpload() {
    // Garante que está na aba documentos
    this.setDashTab('documentos');
    const form = document.getElementById('cand-upload-form');
    if (!form) return;
    const visible = form.style.display !== 'none';
    form.style.display = visible ? 'none' : 'block';
    if (!visible) {
      const desc = document.getElementById('cand-doc-descricao');
      const label = document.getElementById('cand-doc-label');
      const alert = document.getElementById('cand-doc-alert');
      const zone  = document.getElementById('cand-doc-zone');
      if (desc)  desc.value = '';
      if (label) label.textContent = 'Toque para selecionar o arquivo';
      if (alert) alert.style.display = 'none';
      if (zone)  zone.style.borderColor = 'rgba(255,106,0,.5)';
    }
  },

  async uploadDoc(input) {
    if (!input.files[0]) return;
    const file      = input.files[0];
    const tipo      = document.getElementById('cand-doc-tipo').value;
    const descricao = document.getElementById('cand-doc-descricao').value;
    const label     = document.getElementById('cand-doc-label');
    const zone      = document.getElementById('cand-doc-zone');
    const alertEl   = document.getElementById('cand-doc-alert');

    label.textContent = `⏳ Enviando ${file.name}...`;
    zone.style.borderColor = '#FF6A00';
    alertEl.style.display = 'none';

    const fd = new FormData();
    fd.append('arquivo', file);
    fd.append('tipo', tipo);
    fd.append('descricao', descricao);

    try {
      const r = await fetch('/api/candidato/enviar-documento', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + this._token },
        body: fd,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.message || 'Erro');
      zone.style.borderColor = '#2ECC71';
      label.textContent = `✅ ${file.name} enviado!`;
      alertEl.textContent = '✅ Documento enviado com sucesso!';
      alertEl.style.background = 'rgba(46,204,113,.1)';
      alertEl.style.color = '#2ECC71';
      alertEl.style.display = 'block';
      setTimeout(() => { this.abrirUpload(); this._loadDocs(); }, 1500);
    } catch(e) {
      label.textContent = '📎 Clique para selecionar';
      zone.style.borderColor = 'rgba(255,82,82,.4)';
      alertEl.textContent = '❌ ' + e.message;
      alertEl.style.background = 'rgba(255,82,82,.1)';
      alertEl.style.color = '#FF5252';
      alertEl.style.display = 'block';
    }
    input.value = '';
  },

  async _loadDocs() {
    const lista = document.getElementById('cand-docs-lista');
    if (!lista) return;
    try {
      const r = await fetch('/api/candidato/meus-documentos', {
        headers: { 'Authorization': 'Bearer ' + this._token },
      });
      const docs = await r.json();
      if (!r.ok || !docs.length) {
        lista.innerHTML = '<p style="color:#5A6478;font-size:12px;text-align:center;padding:8px 0;">Nenhum documento enviado ainda.</p>';
        return;
      }
      const TIPO_ICON = { NR:'📜', DIPLOMA:'🎓', CERTIFICADO:'📋', CNH:'🪪', OUTRO:'📄' };
      lista.innerHTML = docs.map(d => `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;
                    background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
                    border-radius:8px;padding:10px 12px;">
          <div style="display:flex;align-items:center;gap:8px;overflow:hidden;">
            <span style="font-size:1.1rem;">${TIPO_ICON[d.tipo] || '📄'}</span>
            <div style="overflow:hidden;">
              <p style="margin:0;font-size:13px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${d.nome}</p>
              <p style="margin:0;font-size:11px;color:#5A6478;">${d.descricao || d.tipo} · ${d.enviadoEm}</p>
            </div>
          </div>
          ${d.url ? `<a href="${d.url}" target="_blank" style="color:#FF6A00;font-size:11px;white-space:nowrap;text-decoration:none;">Ver ↗</a>` : '<span style="color:#5A6478;font-size:11px;">Processando...</span>'}
        </div>`).join('');
    } catch(e) {
      lista.innerHTML = `<p style="color:#FF5252;font-size:12px;text-align:center;">${e.message}</p>`;
    }
  },

  async _loadCandidaturas() {
    const lista = document.getElementById('cand-lista');
    if (!lista) return;
    lista.innerHTML = '<p style="color:#9AA3B2;text-align:center;padding:20px;">Carregando...</p>';
    try {
      const r = await fetch('/api/candidato/minhas-candidaturas', {
        headers: { 'Authorization': 'Bearer ' + this._token },
      });
      const items = await r.json();
      if (!r.ok) throw new Error(items.message || 'Erro');
      if (!items.length) {
        lista.innerHTML = '<p style="color:#9AA3B2;text-align:center;padding:20px;">Nenhuma candidatura encontrada.</p>';
        return;
      }
      const COR = {
        PENDING:'#FFB830', TRIAGEM:'#5B8DEF', TRIAGEM_OK:'#2ECC71',
        ENTREVISTA:'#A78BFA', ENTREVISTA_OK:'#2ECC71',
        APROVACAO_FINAL:'#F39C12', APPROVED:'#2ECC71', REJECTED:'#FF5252',
      };
      lista.innerHTML = items.map(c => {
        const cor = COR[c.statusKey] || '#9AA3B2';
        return `<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:14px 16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
            <div>
              <p style="margin:0 0 2px;font-size:15px;font-weight:700;color:#fff;">${c.vaga}</p>
              <p style="margin:0;font-size:12px;color:#9AA3B2;">📍 ${c.local} · ${c.appliedAt}</p>
            </div>
            <span style="background:${cor}18;border:1px solid ${cor}44;color:${cor};border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700;white-space:nowrap;">${c.status}</span>
          </div>
        </div>`;
      }).join('');
    } catch(e) {
      lista.innerHTML = `<p style="color:#FF5252;text-align:center;">${e.message}</p>`;
    }
  },
};

// Fecha modal ao clicar fora
document.getElementById('candidato-portal-overlay')?.addEventListener('click', function(e) {
  if (e.target === this) CandidatoPortal.fechar();
});

// ── Dropdown customizado de filtro de auditoria ───────────────
function toggleAuditDropdown() {
  const list = document.getElementById('audit-action-list');
  if (!list) return;
  const open = list.style.display === 'block';
  list.style.display = open ? 'none' : 'block';
}

function selectAuditAction(el) {
  const val   = el.dataset.val;
  const label = el.textContent.trim();
  document.getElementById('audit-action-filter').value = val;
  document.getElementById('audit-action-label').textContent = label || 'Todas as ações';
  document.getElementById('audit-action-list').style.display = 'none';
  // Marca selecionado
  document.querySelectorAll('.adf-opt').forEach(o => o.classList.remove('adf-selected'));
  el.classList.add('adf-selected');
  Manager.loadAudit(1);
}

// Fecha dropdown ao clicar fora
document.addEventListener('click', function(e) {
  const dd = document.getElementById('audit-action-dropdown');
  if (dd && !dd.contains(e.target)) {
    const list = document.getElementById('audit-action-list');
    if (list) list.style.display = 'none';
  }
});

// ─── API helper (com detecção de 401) ────────────────────────

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (sessionToken) headers['Authorization'] = 'Bearer ' + sessionToken;

  const response = await fetch(API_BASE + path, { ...options, headers });

  // Sessão expirada → logout automático com aviso
  if (response.status === 401 && sessionToken) {
    sessionToken = sessionUsername = null;
    localStorage.removeItem('rz_token');
    showToast('Sessão expirada', 'Faça login novamente.', 'warning');
    document.getElementById('manager-dashboard').style.display = 'none';
    document.getElementById('manager-login').style.display     = 'block';
    document.getElementById('login-form').reset();
    // Vai para aba do gestor
    document.querySelectorAll('.nav__tab').forEach(t => t.classList.remove('nav__tab--active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('panel--active'));
    document.querySelector('[data-panel="manager"]').classList.add('nav__tab--active');
    document.getElementById('panel-manager').classList.add('panel--active');
    throw new Error('Sessão expirada');
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error((data && data.message) || `Erro ${response.status}`);
  return data;
}

// ─── Toast ────────────────────────────────────────────────────

function showToast(title, message, type = 'success') {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `
    <span class="toast__icon">${icons[type] || icons.info}</span>
    <div class="toast__content">
      <div class="toast__title">${title}</div>
      ${message ? `<div class="toast__message">${message}</div>` : ''}
    </div>`;
  document.getElementById('toast-container').appendChild(toast);
  setTimeout(() => {
    toast.classList.add('toast--leaving');
    setTimeout(() => toast.remove(), 250);
  }, 4500);
}

function showAlert(id, msg, type = 'error') {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `alert alert--${type}`;
  el.textContent = msg;
  el.style.display = 'block';
}

function clearAlert(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

// ─── Masks ────────────────────────────────────────────────────

function maskCpf(v) {
  return v.replace(/\D/g,'').slice(0,11)
    .replace(/(\d{3})(\d)/,'$1.$2')
    .replace(/(\d{3})\.(\d{3})(\d)/,'$1.$2.$3')
    .replace(/\.(\d{3})(\d)/,'.$1-$2');
}

function maskPhone(v) {
  const d = v.replace(/\D/g,'').slice(0,11);
  return d.length <= 10
    ? d.replace(/(\d{2})(\d{4})(\d*)/,'($1) $2-$3')
    : d.replace(/(\d{2})(\d{5})(\d*)/,'($1) $2-$3');
}

function getCheckedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(i => i.value);
}

function detailCell(label, value) {
  return `<div class="detail-cell">
    <span class="detail-cell__label">${label}</span>
    <span class="detail-cell__value">${value || '—'}</span>
  </div>`;
}

function statusLabel(s) {
  return { APPROVED: '✅ Aprovado', REJECTED: '❌ Reprovado', PENDING: '⏳ Pendente' }[s] || s;
}

function statusIcon(s) {
  return { APPROVED: '✅', REJECTED: '❌', PENDING: '⏳' }[s] || '•';
}

// ═══════════════════════════════════════════════════════════
//  PORTAL (candidato)
// ═══════════════════════════════════════════════════════════

const Portal = {

  async loadJobList() {
    const grid    = document.getElementById('job-list__grid');
    const loading = document.getElementById('job-list__loading');
    const empty   = document.getElementById('job-list__empty');
    loading.style.display = 'block';
    grid.style.display    = 'none';
    empty.style.display   = 'none';
    try {
      allJobs = await request('/api/jobs');
      loading.style.display = 'none';
      this.renderJobGrid(allJobs);
    } catch (err) {
      loading.style.display = 'none';
      empty.style.display   = 'block';
    }
  },

  renderJobGrid(jobs) {
    const grid  = document.getElementById('job-list__grid');
    const empty = document.getElementById('job-list__empty');
    const count = document.getElementById('job-search-count');

    if (!jobs || !jobs.length) {
      grid.style.display  = 'none';
      empty.style.display = 'block';
      if (count) count.textContent = '';
      return;
    }

    if (count) count.textContent = `${jobs.length} vaga${jobs.length !== 1 ? 's' : ''}`;
    grid.style.display = 'grid';
    empty.style.display = 'none';
    grid.innerHTML = jobs.map(job => `
      <div class="job-card" onclick="Portal.selectJob(${job.id})">
        <h3 class="job-card__title">${job.position}</h3>
        <div class="job-card__tags">
          <span class="tag">📍 ${job.location}</span>
          ${job.tipo ? `<span class="tag">${job.tipo}</span>` : ''}
          ${job.expiresAt ? `<span class="tag tag--warning">⏱ Encerra ${new Date(job.expiresAt).toLocaleDateString('pt-BR')}</span>` : ''}
          <span class="tag tag--success">${job.numVagas} vaga${job.numVagas !== 1 ? 's' : ''}</span>
        </div>
        <p class="job-card__description">
          ${job.finalidade
            ? job.finalidade.slice(0, 130) + (job.finalidade.length > 130 ? '...' : '')
            : 'Consulte os detalhes da vaga.'}
        </p>
        <div class="job-card__footer">
          <span class="job-card__date">📅 ${new Date(job.createdAt).toLocaleDateString('pt-BR')}</span>
          <button class="btn btn--primary btn--small">Candidatar-se →</button>
        </div>
      </div>`).join('');
  },

  filterJobs() {
    const search   = (document.getElementById('job-search-input')?.value || '').toLowerCase().trim();
    const location = document.getElementById('job-filter-location')?.value || '';

    const filtered = allJobs.filter(job => {
      const matchSearch   = !search   || job.position.toLowerCase().includes(search) || (job.finalidade||'').toLowerCase().includes(search);
      const matchLocation = !location || job.location === location;
      return matchSearch && matchLocation;
    });

    this.renderJobGrid(filtered);
  },

  clearJobFilters() {
    const s = document.getElementById('job-search-input');
    const l = document.getElementById('job-filter-location');
    if (s) s.value = '';
    if (l) l.value = '';
    this.renderJobGrid(allJobs);
  },

  async selectJob(jobId) {
    selectedJob = allJobs.find(j => j.id === jobId);
    if (!selectedJob) {
      try {
        const jobs = await request('/api/jobs');
        selectedJob = jobs.find(j => j.id === jobId);
        if (!selectedJob) return;
      } catch (err) { showToast('Erro', err.message, 'error'); return; }
    }

    document.getElementById('apply-job-title').textContent = selectedJob.position;
    document.getElementById('apply-job-tags').innerHTML = `
      <span class="tag">📍 ${selectedJob.location}</span>
      ${selectedJob.tipo ? `<span class="tag">${selectedJob.tipo}</span>` : ''}
      <span class="tag">${selectedJob.numVagas} vaga${selectedJob.numVagas !== 1 ? 's' : ''}</span>`;

    const url = new URL(window.location.href);
    url.searchParams.set('vaga', jobId);
    window.history.pushState({}, '', url);

    document.getElementById('job-list').style.display        = 'none';
    document.getElementById('apply-form-view').style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  },

  backToJobList() {
    selectedJob = null;
    const url = new URL(window.location.href);
    url.searchParams.delete('vaga');
    window.history.pushState({}, '', url);

    document.getElementById('apply-form-view').style.display = 'none';
    document.getElementById('job-list').style.display        = 'block';
    document.getElementById('apply-form').reset();
    document.querySelectorAll('#apply-form input[type="checkbox"]').forEach(cb => cb.checked = false);

    const dz = document.getElementById('resume-drop-zone');
    dz.classList.remove('file-drop--ready', 'file-drop--over');
    dz.querySelector('.file-drop__text').textContent = 'Clique ou arraste o PDF aqui';
    dz.querySelector('.file-drop__hint').textContent = 'Máx. 5 MB';
    clearAlert('apply-form-alert');
  },

  handleResumeFile(input) {
    const file = input.files[0];
    if (!file) return;
    if (file.type !== 'application/pdf') { showToast('Formato inválido', 'Apenas PDFs são aceitos.', 'error'); input.value = ''; return; }
    if (file.size > 5 * 1024 * 1024)    { showToast('Arquivo muito grande', 'Máximo 5 MB.', 'error'); input.value = ''; return; }
    const dz = document.getElementById('resume-drop-zone');
    dz.classList.add('file-drop--ready');
    dz.querySelector('.file-drop__text').textContent = '✅ ' + file.name;
    dz.querySelector('.file-drop__hint').textContent = (file.size / 1024 / 1024).toFixed(2) + ' MB';
  },
};

// ═══════════════════════════════════════════════════════════
//  MANAGER
// ═══════════════════════════════════════════════════════════

const Manager = {

  init() {
    if (sessionToken) this.showDashboard();
    else {
      document.getElementById('manager-login').style.display     = 'block';
      document.getElementById('manager-dashboard').style.display = 'none';
    }
  },

  showDashboard() {
    document.getElementById('manager-login').style.display     = 'none';
    document.getElementById('manager-dashboard').style.display = 'block';
    document.getElementById('dashboard-greeting').textContent  = `Olá, ${sessionUsername} 👋`;
    this.loadStats();
    this.loadJobList();
    setTimeout(() => Solicitacoes.loadBadge(), 500);
  },

  logout() {
    sessionToken = sessionUsername = null;
    document.getElementById('manager-dashboard').style.display = 'none';
    document.getElementById('manager-login').style.display     = 'block';
    document.getElementById('login-form').reset();
    showToast('Sessão encerrada', '', 'info');
  },

  toggleRegisterPanel() {
    const p = document.getElementById('register-panel');
    p.style.display = p.style.display === 'none' ? 'block' : 'none';
    clearAlert('register-alert');
  },

  async inviteUser() {
    const username = document.getElementById('register-username').value.trim();
    const email    = document.getElementById('register-email').value.trim().toLowerCase();
    if (!username || !email) { showAlert('register-alert', 'Preencha o usuário e o e-mail.'); return; }
    if (!email.endsWith('@rezendeenergia.com.br')) {
      showAlert('register-alert', '❌ Apenas e-mails @rezendeenergia.com.br são permitidos.');
      return;
    }
    try {
      await request('/api/auth/invite', { method: 'POST', body: JSON.stringify({ username, email }) });
      showAlert('register-alert', `✅ Convite enviado para ${email}!`, 'success');
      showToast('Convite enviado!', email, 'success');
      setTimeout(() => {
        this.toggleRegisterPanel();
        document.getElementById('register-username').value = '';
        document.getElementById('register-email').value    = '';
      }, 2200);
    } catch (err) { showAlert('register-alert', '❌ ' + err.message); }
  },

  // ── Stats ─────────────────────────────────────────────────

  async loadStats() {
    try {
      const [jobs, stats] = await Promise.all([request('/api/jobs/all'), request('/api/candidaturas/stats')]);
      document.getElementById('stat-open-jobs').textContent          = jobs.filter(j => j.status === 'OPEN').length;
      document.getElementById('stat-total-applications').textContent = stats.total    ?? 0;
      document.getElementById('stat-pending').textContent            = stats.pending  ?? 0;
      document.getElementById('stat-approved').textContent           = stats.approved ?? 0;
      document.getElementById('count-jobs').textContent              = jobs.length;
      document.getElementById('count-applications').textContent      = stats.total ?? 0;
    } catch (_) {}
  },

  // ── Vagas ──────────────────────────────────────────────────

  async loadJobList() {
    const container = document.getElementById('manager-job-list');
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
      const jobs = await request('/api/jobs/all');
      if (!jobs.length) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state__icon">📋</div><h3>Nenhuma vaga criada</h3><p>Crie sua primeira vaga na aba "Nova Vaga".</p></div>`;
        return;
      }
      container.innerHTML = jobs.map(job => `
        <div class="manager-job" id="manager-job-${job.id}">
          <div class="manager-job__top">
            <div class="manager-job__title">${job.position}</div>
            <div class="manager-job__actions">
              <button class="btn btn--small btn--outline" onclick="Manager.openEditModal(${job.id})">✏️ Editar</button>
              <button class="btn btn--small ${job.status === 'OPEN' ? 'btn--danger' : 'btn--success'}"
                      onclick="Manager.toggleJobStatus(${job.id})">
                ${job.status === 'OPEN' ? '⏸ Fechar' : '▶ Reabrir'}
              </button>
              <button class="btn btn--small btn--outline"
                      onclick="Manager.deleteJob(${job.id}, '${job.position.replace(/'/g,"\\'")}')">🗑</button>
            </div>
          </div>
          <div class="manager-job__tags">
            <span class="tag">📍 ${job.location}</span>
            ${job.tipo ? `<span class="tag">${job.tipo}</span>` : ''}
          ${job.expiresAt ? `<span class="tag tag--warning">⏱ Encerra ${new Date(job.expiresAt).toLocaleDateString('pt-BR')}</span>` : ''}
            <span class="tag ${job.status === 'OPEN' ? 'tag--success' : 'tag--error'}">
              ${job.status === 'OPEN' ? '🟢 Aberta' : '🔴 Fechada'}
            </span>
            <span class="tag tag--warning">👤 ${job.numVagas} vaga${job.numVagas !== 1 ? 's' : ''}</span>
            <span class="tag">📅 ${new Date(job.createdAt).toLocaleDateString('pt-BR')}</span>
          </div>
          ${job.finalidade ? `<p class="manager-job__description">${job.finalidade.slice(0, 200)}${job.finalidade.length > 200 ? '...' : ''}</p>` : ''}
          <p class="manager-job__responsible">Responsável: ${job.responsavel} · ${job.emailResp}</p>
          <div class="manager-job__sharelink">
            🔗 Link direto:
            <code>?vaga=${job.id}</code>
            <button class="btn btn--ghost btn--small"
              onclick="navigator.clipboard.writeText(window.location.origin + window.location.pathname + '?vaga=${job.id}'); showToast('Link copiado!','','success')">
              📋 Copiar
            </button>
          </div>
        </div>`).join('');
    } catch (err) {
      container.innerHTML = `<p style="color:var(--error);padding:20px;">${err.message}</p>`;
    }
  },

  async toggleJobStatus(jobId) {
    try {
      await request(`/api/jobs/${jobId}/status`, { method: 'PATCH' });
      showToast('Status alterado', '', 'info');
      this.loadJobList(); this.loadStats(); Portal.loadJobList();
    } catch (err) { showToast('Erro', err.message, 'error'); }
  },

  async deleteJob(jobId, jobTitle) {
    if (!confirm(`Excluir a vaga "${jobTitle}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await request(`/api/jobs/${jobId}`, { method: 'DELETE' });
      showToast('Vaga excluída', jobTitle, 'success');
      this.loadJobList(); this.loadStats(); Portal.loadJobList();
    } catch (err) { showToast('Erro', err.message, 'error'); }
  },

  // ── Edição de vaga ────────────────────────────────────────

  async openEditModal(jobId) {
    const jobs = await request('/api/jobs/all');
    const job  = jobs.find(j => j.id === jobId);
    if (!job) return;
    document.getElementById('edit-job-id').value            = job.id;
    document.getElementById('edit-job-position').value      = job.position;
    document.getElementById('edit-job-num-vagas').value     = job.numVagas;
    document.getElementById('edit-job-location').value      = job.location;
    document.getElementById('edit-job-tipo').value          = job.tipo || '';
    document.getElementById('edit-job-description').value   = job.finalidade || '';
    document.getElementById('edit-job-manager-name').value  = job.responsavel;
    document.getElementById('edit-job-manager-email').value = job.emailResp;
    document.getElementById('edit-job-expires').value = job.expiresAt ? job.expiresAt.substring(0,10) : '';
    clearAlert('edit-job-alert');
    document.getElementById('edit-job-modal').classList.add('modal--open');
  },

  closeEditModal() { document.getElementById('edit-job-modal').classList.remove('modal--open'); },

  // ── Candidaturas ──────────────────────────────────────────

  async loadApplications(search = '', statusFilter = '', jobFilter = '', page = 1) {
    currentPage = page;
    const container = document.getElementById('manager-applications');

    if (!document.getElementById('applications-filter-bar')) {
      const jobs = await request('/api/jobs/all');
      const bar  = document.createElement('div');
      bar.id = 'applications-filter-bar';
      bar.className = 'filter-bar';
      bar.innerHTML = `
        <input id="filter-search" type="text" class="form-field__input filter-bar__search"
               placeholder="🔍 Buscar por nome, CPF ou e-mail..." value="${search}">
        <select id="filter-status" class="form-field__select filter-bar__select">
          <option value="">Todos os status</option>
          <option value="PENDING"  ${statusFilter==='PENDING'  ?'selected':''}>⏳ Pendente</option>
          <option value="APPROVED" ${statusFilter==='APPROVED' ?'selected':''}>✅ Aprovado</option>
          <option value="REJECTED" ${statusFilter==='REJECTED' ?'selected':''}>❌ Reprovado</option>
        </select>
        <select id="filter-job" class="form-field__select filter-bar__select">
          <option value="">Todas as vagas</option>
          ${jobs.map(j => `<option value="${j.id}" ${jobFilter==j.id?'selected':''}>${j.position}</option>`).join('')}
        </select>
        <button class="btn btn--outline btn--small" onclick="Manager.clearFilters()">✕ Limpar</button>`;
      container.parentElement.insertBefore(bar, container);

      let dt;
      document.getElementById('filter-search').addEventListener('input', () => {
        clearTimeout(dt); dt = setTimeout(() => Manager.applyFilters(), 400);
      });
      document.getElementById('filter-status').addEventListener('change', () => Manager.applyFilters());
      document.getElementById('filter-job').addEventListener('change',    () => Manager.applyFilters());
    }

    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';

    try {
      const params = new URLSearchParams({ page });
      if (search)       params.set('search', search);
      if (statusFilter) params.set('status', statusFilter);
      if (jobFilter)    params.set('jobId',  jobFilter);

      const [result, jobs] = await Promise.all([
        request('/api/candidaturas?' + params),
        request('/api/jobs/all'),
      ]);

      const bar = document.getElementById('pagination-bar');
      if (result.totalPages > 1) {
        bar.style.display = 'flex';
        document.getElementById('page-info').textContent = `Página ${page} de ${result.totalPages} · ${result.total} registros`;
        document.getElementById('page-prev').disabled = page <= 1;
        document.getElementById('page-next').disabled = page >= result.totalPages;
        bar._meta = { totalPages: result.totalPages, search, statusFilter, jobFilter };
      } else {
        bar.style.display = 'none';
      }

      if (!result.items.length) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state__icon">👥</div><h3>Nenhuma candidatura encontrada</h3><p>Tente ajustar os filtros.</p></div>`;
        return;
      }

      const groups = {};
      result.items.forEach(app => {
        const id = app.job?.id ?? 'x';
        if (!groups[id]) {
          const j = jobs.find(j => j.id === app.job?.id);
          groups[id] = { title: j?.position ?? 'Vaga', location: j?.location ?? '', items: [] };
        }
        groups[id].items.push(app);
      });

      container.innerHTML = Object.values(groups).map(g => `
        <div class="job-group">
          <div class="job-group__header">
            <div class="job-group__title">⚡ ${g.title} <span class="tag">${g.location}</span></div>
            <span class="tag tag--warning">${g.items.length} candidato${g.items.length !== 1 ? 's' : ''}</span>
          </div>
          ${g.items.map(app => `
            <div class="application-row" onclick="Manager.showApplicationModal(${app.id})">
              <div class="application-row__avatar">${(app.fullName||'?').charAt(0).toUpperCase()}</div>
              <div class="application-row__info">
                <div class="application-row__name">${app.fullName}</div>
                <div class="application-row__details">📧 ${app.email} · 📱 ${app.phone} · 🏠 ${app.cidadeAtual ?? '—'}</div>
              </div>
              <span class="status-badge status-badge--${app.status}">${statusLabel(app.status)}</span>
            </div>`).join('')}
        </div>`).join('');
    } catch (err) {
      container.innerHTML = `<p style="color:var(--error);padding:20px;">${err.message}</p>`;
    }
  },

  changePage(delta) {
    const meta = document.getElementById('pagination-bar')?._meta;
    if (!meta) return;
    const np = currentPage + delta;
    if (np < 1 || np > meta.totalPages) return;
    this.loadApplications(meta.search, meta.statusFilter, meta.jobFilter, np);
  },

  applyFilters() {
    this.loadApplications(
      document.getElementById('filter-search')?.value || '',
      document.getElementById('filter-status')?.value || '',
      document.getElementById('filter-job')?.value    || '',
      1
    );
  },

  clearFilters() {
    ['filter-search','filter-status','filter-job'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    this.loadApplications('','','',1);
  },

  // ── Modal do candidato ────────────────────────────────────

  async showApplicationModal(appId) {
    try {
      // Busca em todas as páginas
      let app = null;
      for (let p = 1; p <= 50 && !app; p++) {
        const r = await request(`/api/candidaturas?page=${p}`);
        app = r.items.find(i => i.id === appId);
        if (p >= r.totalPages) break;
      }
      if (!app) return;

      // Busca histórico
      let history = [];
      try { history = await request(`/api/candidaturas/${appId}/history`); } catch (_) {}

      document.getElementById('modal-candidate-name').textContent = app.fullName;
      document.getElementById('modal-candidate-body').innerHTML = `

        <!-- Cabeçalho de ações -->
        <div class="modal-actions-bar">
          <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:center;">
            <span class="tag tag--warning">⚡ ${app.job?.position ?? '—'}</span>
            <span class="tag">📅 ${new Date(app.appliedAt).toLocaleString('pt-BR')}</span>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            <select class="form-field__select" style="max-width:175px;padding:5px 9px;font-size:0.8rem;"
                    onchange="Manager.updateApplicationStatus(${app.id}, this.value)">
              <option value="PENDING"  ${app.status==='PENDING'  ?'selected':''}>⏳ Pendente</option>
              <option value="APPROVED" ${app.status==='APPROVED' ?'selected':''}>✅ Aprovado</option>
              <option value="REJECTED" ${app.status==='REJECTED' ?'selected':''}>❌ Reprovado</option>
            </select>
            <button class="btn btn--outline btn--small" onclick="Manager.printProfile(${app.id})">🖨️ Imprimir</button>
          </div>
        </div>

        <!-- Dados para impressão -->
        <div id="print-profile-${app.id}" class="print-profile">
          <div class="print-header">
            <div class="print-header__title">Ficha do Candidato — Rezende Energia</div>
            <div class="print-header__meta">
              Vaga: <strong>${app.job?.position ?? '—'}</strong> &nbsp;|&nbsp;
              Data: <strong>${new Date(app.appliedAt).toLocaleString('pt-BR')}</strong> &nbsp;|&nbsp;
              Status: <strong>${statusLabel(app.status)}</strong>
            </div>
          </div>

          <p class="detail-section-title">Dados Pessoais</p>
          <div class="detail-grid">
            ${detailCell('Nome',         app.fullName)}
            ${detailCell('CPF',          app.cpf)}
            ${detailCell('RG',           app.rg)}
            ${detailCell('Nascimento',   app.dataNascimento ? new Date(app.dataNascimento+'T12:00:00').toLocaleDateString('pt-BR') : null)}
            ${detailCell('Tipo Sang.',   app.tipoSanguineo)}
            ${detailCell('Nome da Mãe', app.nomeMae)}
            ${detailCell('Cidade Natal', app.cidadeNatal)}
            ${detailCell('Cidade Atual', app.cidadeAtual)}
          </div>

          <p class="detail-section-title">Contato</p>
          <div class="detail-grid">
            ${detailCell('Telefone', app.phone)}
            ${detailCell('E-mail',   app.email)}
            ${detailCell('LinkedIn', app.linkedin)}
          </div>

          <p class="detail-section-title">Formação & EPI</p>
          <div class="detail-grid">
            ${detailCell('Formação',      app.education)}
            ${detailCell('Experiência',   app.experience)}
            ${detailCell('Disp. Viagem', app.disponibilidadeViagem)}
            ${detailCell('Calça',         app.tamanhoCalca)}
            ${detailCell('Camisa',        app.tamanhoCamisa)}
            ${detailCell('Bota',          app.tamanhoBota)}
          </div>

          <p class="detail-section-title">Habilitações & Certificações</p>
          <div class="detail-grid">
            ${detailCell('CNH',     (app.carteira||[]).join(', '))}
            ${detailCell('NRs',     (app.nrs     ||[]).join(', '))}
            ${detailCell('Escolas', (app.escolas ||[]).join(', '))}
            ${app.hasResume
              ? `<div class="detail-cell">
                   <span class="detail-cell__label">Currículo</span>
                   <button class="btn btn--small btn--outline no-print" style="margin-top:4px;"
                     onclick="Manager.downloadResume(${app.id},'${app.resumeName}')">⬇ Baixar PDF</button>
                   <span class="print-only" style="font-size:0.83rem;">Arquivo enviado</span>
                 </div>`
              : detailCell('Currículo', 'Não enviado')}
          </div>

          ${app.motivation
            ? `<p class="detail-section-title">Motivação</p>
               <div class="detail-text-block">${app.motivation}</div>`
            : ''}
        </div>

        <!-- Observações RH -->
        <p class="detail-section-title no-print">📝 Observações Internas (RH)</p>
        <textarea id="modal-observacoes" class="form-field__textarea no-print"
                  placeholder="Anotações internas sobre este candidato..."
                  style="min-height:80px;">${app.observacoes || ''}</textarea>
        <div style="display:flex;justify-content:flex-end;margin-top:8px;" class="no-print">
          <button class="btn btn--primary btn--small"
                  onclick="Manager.saveObservacoes(${app.id})">💾 Salvar Observações</button>
        </div>

        <!-- Histórico de status -->
        ${history.length > 0 ? `
          <p class="detail-section-title no-print">📋 Histórico de Status</p>
          <div class="status-history no-print">
            ${history.map(h => `
              <div class="status-history__item">
                <div class="status-history__icon">${statusIcon(h.newStatus)}</div>
                <div class="status-history__content">
                  <div class="status-history__line">
                    <span class="status-history__label">${statusLabel(h.newStatus)}</span>
                    ${h.oldStatus ? `<span class="status-history__from">← era ${statusLabel(h.oldStatus)}</span>` : ''}
                  </div>
                  <div class="status-history__meta">
                    por <strong>${h.changedBy}</strong> ·
                    ${new Date(h.changedAt).toLocaleString('pt-BR')}
                    ${h.note ? `· <em>${h.note}</em>` : ''}
                  </div>
                </div>
              </div>`).join('')}
          </div>` : ''}
      `;

      document.getElementById('candidate-modal').classList.add('modal--open');
    } catch (err) { showToast('Erro', err.message, 'error'); }
  },

  printProfile(appId) {
    const content = document.getElementById(`print-profile-${appId}`);
    if (!content) return;
    const name = document.getElementById('modal-candidate-name')?.textContent || 'candidato';
    const win = window.open('', '_blank', 'width=900,height=700');
    win.document.write(`
      <!DOCTYPE html><html lang="pt-BR">
      <head>
        <meta charset="UTF-8">
        <title>Ficha — ${name}</title>
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: -apple-system, sans-serif; background: #fff; color: #111; font-size: 13px; padding: 28px 32px; line-height: 1.5; }
          .print-header { border-bottom: 2px solid #F7931E; padding-bottom: 12px; margin-bottom: 18px; }
          .print-header__title { font-size: 16px; font-weight: 800; color: #F7931E; }
          .print-header__meta  { font-size: 12px; color: #555; margin-top: 4px; }
          .detail-section-title {
            font-size: 10px; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.1em; color: #F7931E; margin: 16px 0 8px;
            padding-bottom: 4px; border-bottom: 1px solid #eee;
          }
          .detail-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
          .detail-cell { background: #f7f7f7; border-radius: 5px; padding: 7px 10px; }
          .detail-cell__label { display: block; font-size: 9px; font-weight: 700; text-transform: uppercase; color: #F7931E; letter-spacing: 0.07em; margin-bottom: 2px; }
          .detail-cell__value { font-size: 12px; font-weight: 500; }
          .detail-text-block { background: #f7f7f7; border-radius: 6px; padding: 10px 12px; font-size: 12px; line-height: 1.7; margin-top: 8px; }
          @media print { body { padding: 0; } }
        </style>
      </head>
      <body>${content.innerHTML}</body>
      </html>`);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 400);
  },

  async saveObservacoes(appId) {
    const text = document.getElementById('modal-observacoes')?.value || '';
    try {
      await request(`/api/candidaturas/${appId}/observacoes`, {
        method: 'PATCH',
        body: JSON.stringify({ observacoes: text }),
      });
      showToast('Observações salvas', '', 'success');
    } catch (err) { showToast('Erro ao salvar', err.message, 'error'); }
  },

  async downloadResume(appId, filename) {
    try {
      const r = await fetch(`${API_BASE}/api/candidaturas/${appId}/resume`, {
        headers: { 'Authorization': 'Bearer ' + sessionToken },
      });
      if (!r.ok) throw new Error('Arquivo não encontrado');
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename || 'curriculo.pdf';
      a.click();
    } catch (err) { showToast('Erro', err.message, 'error'); }
  },

  async updateApplicationStatus(appId, newStatus) {
    try {
      const updated = await request(`/api/candidaturas/${appId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      showToast('Status atualizado', statusLabel(newStatus), 'success');
      this.loadStats();

      // Atualiza histórico no modal sem fechar
      const historySection = document.querySelector('.status-history');
      if (updated.history && updated.history.length) {
        const newHtml = `
          <div class="status-history">
            ${updated.history.map(h => `
              <div class="status-history__item">
                <div class="status-history__icon">${statusIcon(h.newStatus)}</div>
                <div class="status-history__content">
                  <div class="status-history__line">
                    <span class="status-history__label">${statusLabel(h.newStatus)}</span>
                    ${h.oldStatus ? `<span class="status-history__from">← era ${statusLabel(h.oldStatus)}</span>` : ''}
                  </div>
                  <div class="status-history__meta">
                    por <strong>${h.changedBy}</strong> ·
                    ${new Date(h.changedAt).toLocaleString('pt-BR')}
                  </div>
                </div>
              </div>`).join('')}
          </div>`;
        if (historySection) {
          historySection.outerHTML = newHtml;
        }
      }
    } catch (err) { showToast('Erro', err.message, 'error'); }
  },

  closeModal() { document.getElementById('candidate-modal').classList.remove('modal--open'); },

  // ── Gráficos ──────────────────────────────────────────────

  async loadCharts() {
    try {
      const data = await request('/api/candidaturas/chart-stats');

    // ── Comparativo entre vagas ──────────────────────────
    const compTbody = document.getElementById('job-comparison-tbody');
    if (compTbody) {
      if (data.jobComparison && data.jobComparison.length > 0) {
        const fmtH = h => h === null ? '—' : h < 24 ? `${h}h` : `${(h/24).toFixed(1)}d`;
        compTbody.innerHTML = data.jobComparison.map(j => {
          const barW = j.total > 0 ? 100 : 0;
          const approvedW  = j.total > 0 ? Math.round(j.approved  / j.total * 100) : 0;
          const rejectedW  = j.total > 0 ? Math.round(j.rejected  / j.total * 100) : 0;
          const pendingW   = j.total > 0 ? Math.round(j.pending   / j.total * 100) : 0;
          return `
          <tr style="border-bottom:1px solid rgba(255,255,255,.04);">
            <td style="padding:10px 16px;">
              <div style="font-weight:700;color:#fff;">${j.position}</div>
              <div style="font-size:.72rem;color:var(--ink-3);">📍 ${j.location}</div>
              <div style="margin-top:6px;height:4px;border-radius:4px;background:rgba(255,255,255,.06);overflow:hidden;display:flex;">
                <div style="width:${approvedW}%;background:#2ECC71;"></div>
                <div style="width:${rejectedW}%;background:#FF5252;"></div>
                <div style="width:${pendingW}%;background:#FFB830;"></div>
              </div>
            </td>
            <td style="padding:10px 16px;text-align:center;font-weight:800;color:#fff;font-size:1.1rem;">${j.total}</td>
            <td style="padding:10px 16px;text-align:center;color:#2ECC71;font-weight:700;">${j.approved}</td>
            <td style="padding:10px 16px;text-align:center;color:#FF5252;font-weight:700;">${j.rejected}</td>
            <td style="padding:10px 16px;text-align:center;color:#FFB830;font-weight:700;">${j.pending}</td>
            <td style="padding:10px 16px;text-align:center;">
              <span style="font-weight:700;color:${j.approvalRate>=50?'#2ECC71':j.approvalRate>=20?'#FFB830':'#FF5252'};">
                ${j.approvalRate}%
              </span>
            </td>
            <td style="padding:10px 16px;text-align:center;color:var(--ink-2);">${fmtH(j.avgHours)}</td>
            <td style="padding:10px 16px;text-align:center;">
              <span style="padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700;
                           background:${j.status==='OPEN'?'rgba(46,204,113,.12)':'rgba(255,255,255,.06)'};
                           color:${j.status==='OPEN'?'#2ECC71':'var(--ink-3)'};">
                ${j.status==='OPEN'?'Aberta':'Fechada'}
              </span>
            </td>
          </tr>`}).join('');
      } else {
        compTbody.innerHTML = '<tr><td colspan="8" style="padding:24px;text-align:center;color:var(--ink-3);">Nenhuma vaga com candidatos ainda</td></tr>';
      }
    }

    // ── Tempo de resposta ─────────────────────────────
    if (data.timeStats) {
      const t = data.timeStats;
      const fmtHours = h => h < 24 ? `${h}h` : `${(h/24).toFixed(1)}d`;
      document.getElementById('avg-time').textContent      = t.avgHours    ? fmtHours(t.avgHours)    : '—';
      document.getElementById('median-time').textContent   = t.medianHours ? fmtHours(t.medianHours) : '—';
      document.getElementById('total-responded').textContent = t.totalResponded ?? '—';
      const tbody = document.getElementById('oldest-pending-tbody');
      if (tbody) {
        if (t.oldestPending && t.oldestPending.length > 0) {
          tbody.innerHTML = t.oldestPending.map(p => {
            const cor   = p.days >= 7 ? '#FF5252' : p.days >= 3 ? '#FFB830' : '#2ECC71';
            const icon  = p.days >= 7 ? '🚨' : p.days >= 3 ? '⚠️' : '✅';
            const label = p.days >= 7 ? 'Crítico' : p.days >= 3 ? 'Atenção' : 'OK';
            return `
            <tr style="border-bottom:1px solid rgba(255,255,255,.05);transition:background .15s;"
                onmouseover="this.style.background='rgba(255,255,255,.03)'"
                onmouseout="this.style.background=''">
              <td style="padding:10px 16px;color:#fff;font-weight:600;">${p.name}</td>
              <td style="padding:10px 16px;color:var(--ink-2);">${p.position}</td>
              <td style="padding:10px 16px;">
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="background:${cor}18;border:1px solid ${cor}44;color:${cor};
                               border-radius:20px;padding:3px 10px;font-size:12px;font-weight:800;white-space:nowrap;">
                    ${icon} ${p.days}d — ${label}
                  </span>
                </div>
              </td>
            </tr>`;
          }).join('');
        } else {
          tbody.innerHTML = '<tr><td colspan="3" style="padding:20px;text-align:center;color:var(--ink-3);">✅ Nenhuma candidatura pendente</td></tr>';
        }
      }
    }
      const orange = 'rgba(247,147,30,0.85)';
      const orangeB = 'rgba(247,147,30,1)';
      const statusColors = {
        APPROVED: 'rgba(34,197,94,0.8)',
        PENDING:  'rgba(247,147,30,0.85)',
        REJECTED: 'rgba(239,68,68,0.8)',
      };

      const makeChart = (id, type, labels, values, colors) => {
        const ctx = document.getElementById(id)?.getContext('2d');
        if (!ctx) return;
        if (chartInstances[id]) chartInstances[id].destroy();
        chartInstances[id] = new Chart(ctx, {
          type,
          data: {
            labels,
            datasets: [{
              data: values,
              backgroundColor: colors || orange,
              borderColor:     type === 'line' ? orangeB : undefined,
              borderWidth:     type === 'bar'  ? 0 : 2,
              fill:            type === 'line',
              tension: 0.4,
              pointBackgroundColor: orangeB,
            }],
          },
          options: {
            responsive: true,
            plugins: { legend: { display: type === 'doughnut', labels: { color: '#aaa' } } },
            scales: type !== 'doughnut' ? {
              x: { ticks: { color: '#666' }, grid: { color: 'rgba(255,255,255,0.04)' } },
              y: { ticks: { color: '#666', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.06)' }, beginAtZero: true },
            } : undefined,
          },
        });
      };

      makeChart('chart-by-job',    'bar',      data.byJob.map(d => d.label.length > 20 ? d.label.slice(0,20)+'…' : d.label), data.byJob.map(d => d.value), orange);
      makeChart('chart-by-month',  'line',     data.byMonth.map(d => d.label),  data.byMonth.map(d => d.value));
      makeChart('chart-by-status', 'doughnut', data.byStatus.map(d => statusLabel(d.label)), data.byStatus.map(d => d.value), data.byStatus.map(d => statusColors[d.label] || 'rgba(160,160,160,0.7)'));
    } catch (err) { showToast('Erro nos gráficos', err.message, 'error'); }
  },

  // ── CSV ───────────────────────────────────────────────────

  async exportCsv() {
    try {
      const r = await fetch(API_BASE + '/api/candidaturas/export', {
        headers: { 'Authorization': 'Bearer ' + sessionToken },
      });
      if (!r.ok) throw new Error('Sem dados para exportar');
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href     = URL.createObjectURL(blob);
      const hoje = new Date().toISOString().slice(0,10).replace(/-/g,'');
      a.download = `candidaturas_rezende_${hoje}.xlsx`;
      a.click();
      showToast('Excel exportado!', 'Arquivo com abas por etapa do funil', 'success');
    } catch (err) { showToast('Erro', err.message, 'error'); }
  },
};

// ═══════════════════════════════════════════════════════════
//  Event listeners
// ═══════════════════════════════════════════════════════════

// Nav
document.querySelectorAll('.nav__tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav__tab').forEach(t => t.classList.remove('nav__tab--active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('panel--active'));
    tab.classList.add('nav__tab--active');
    document.getElementById('panel-' + tab.dataset.panel).classList.add('panel--active');
    if (tab.dataset.panel === 'manager') Manager.init();
  });
});

// Subtabs
// ── Auditoria ─────────────────────────────────────────────────
async function loadAudit(page = 1) {
  const userF   = (document.getElementById('audit-user-filter')?.value   || '').trim();
  const actionF = document.getElementById('audit-action-filter')?.value || '';
  try {
    const params = new URLSearchParams({ page });
    if (userF)   params.set('username', userF);
    if (actionF) params.set('action', actionF);
    const data = await request(`/api/auth/audit?${params}`);

    // Mapeamento completo de ações → label legível + cor da categoria
    const ACTION_MAP = {
      // Autenticação
      LOGIN:                { label: '🔑 Login',                   color: '#5B8DEF' },
      LOGIN_FAILED:         { label: '⚠️ Login Falho',             color: '#FFB830' },
      LOGOUT:               { label: '🚪 Logout',                  color: '#9AA3B2' },
      FORGOT_PASSWORD:      { label: '📧 Esqueceu Senha',          color: '#9AA3B2' },
      RESET_PASSWORD:       { label: '🔑 Redefinir Senha',         color: '#9AA3B2' },
      INVITE_USER:          { label: '✉️ Convidar Gestor',         color: '#A78BFA' },
      ACTIVATE_USER:        { label: '✅ Ativar Conta',            color: '#2ECC71' },
      // Vagas
      CREATE_JOB:           { label: '➕ Vaga Criada',             color: '#2ECC71' },
      UPDATE_JOB:           { label: '✏️ Vaga Editada',           color: '#5B8DEF' },
      DELETE_JOB:           { label: '🗑 Vaga Excluída',          color: '#FF5252' },
      TOGGLE_JOB:           { label: '🔄 Abrir/Fechar Vaga',       color: '#FFB830' },
      // Candidaturas
      NEW_APPLICATION:      { label: '📥 Nova Candidatura',        color: '#2ECC71' },
      UPDATE_STATUS:        { label: '📋 Status Candidatura',      color: '#5B8DEF' },
      FUNNEL_ADVANCE:       { label: '⏩ Avançou no Funil',        color: '#2ECC71' },
      FUNNEL_REJECTED:      { label: '⏹ Reprovado no Funil',      color: '#FF5252' },
      DOWNLOAD_RESUME:      { label: '⬇ Download Currículo',       color: '#9AA3B2' },
      EXPORT_CSV:           { label: '📤 Exportar CSV',            color: '#9AA3B2' },
      AUTO_ADMISSION:       { label: '🏢 Admissão Iniciada',       color: '#A78BFA' },
      // Solicitações de vaga
      CREATE_SOLICITACAO:   { label: '📋 Solicitação Criada',      color: '#FFB830' },
      SOLICITACAO_APROVADA: { label: '✅ Solicitação Aprovada',    color: '#2ECC71' },
      SOLICITACAO_REJEITADA:{ label: '❌ Solicitação Rejeitada',   color: '#FF5252' },
    };

    const ENTITY_LABEL = {
      job: 'Vaga', candidatura: 'Candidatura', user: 'Usuário',
      solicitacao_vaga: 'Solicitação', admission: 'Admissão',
    };

    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;
    if (!data || !data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="padding:24px;text-align:center;color:var(--ink-3);">Nenhum registro encontrado.</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(r => {
        const map   = ACTION_MAP[r.action] || { label: r.action, color: '#9AA3B2' };
        const entLabel = r.entity ? (ENTITY_LABEL[r.entity] || r.entity) : '—';
        const entId    = r.entityId ? ` #${r.entityId}` : '';
        return `
        <tr style="border-bottom:1px solid rgba(255,255,255,.04);transition:background .15s;"
            onmouseover="this.style.background='rgba(255,255,255,.03)'"
            onmouseout="this.style.background=''">
          <td style="padding:9px 16px;color:var(--ink-3);white-space:nowrap;font-size:.75rem;">
            ${r.createdAt ? new Date(r.createdAt).toLocaleString('pt-BR') : '—'}
          </td>
          <td style="padding:9px 16px;color:#fff;font-weight:700;">${r.username}</td>
          <td style="padding:9px 16px;white-space:nowrap;">
            <span style="background:${map.color}18;border:1px solid ${map.color}44;color:${map.color};
                         border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;white-space:nowrap;">
              ${map.label}
            </span>
          </td>
          <td style="padding:9px 16px;white-space:nowrap;">
            <span style="font-size:12px;color:var(--ink-2);">${entLabel}${entId}</span>
          </td>
          <td style="padding:9px 16px;color:var(--ink-2);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
              title="${r.detail || ''}">${r.detail || '—'}</td>
          <td style="padding:9px 16px;color:var(--ink-3);font-size:.75rem;">${r.ip || '—'}</td>
        </tr>`;
      }).join('');
    }

    const pgDiv = document.getElementById('audit-pagination');
    if (pgDiv && data.totalPages > 1) {
      pgDiv.innerHTML = Array.from({length: Math.min(data.totalPages, 10)}, (_, i) =>
        `<button class="btn btn--ghost btn--small${i+1===page?' btn--primary':''}" onclick="loadAudit(${i+1})">${i+1}</button>`
      ).join('');
      if (data.totalPages > 10) pgDiv.innerHTML += `<span style="color:var(--ink-3);padding:0 8px;font-size:12px;">... ${data.totalPages} páginas</span>`;
    } else if (pgDiv) pgDiv.innerHTML = '';

  } catch(e) {
    const tbody = document.getElementById('audit-tbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="padding:24px;text-align:center;color:#FF5252;">${e.message}</td></tr>`;
  }
}

// expose to Manager namespace
Manager.loadAudit = loadAudit;

// LGPD checkbox — habilita botão de envio
document.addEventListener('change', function(e) {
  if (e.target && e.target.id === 'lgpd-consent') {
    const btn = document.getElementById('apply-submit-btn');
    if (btn) {
      btn.disabled = !e.target.checked;
      btn.style.opacity = e.target.checked ? '1' : '.5';
      btn.style.cursor  = e.target.checked ? 'pointer' : 'not-allowed';
    }
  }
});


document.querySelectorAll('.subtab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.subtab').forEach(t => t.classList.remove('subtab--active'));
    document.querySelectorAll('.subtab-panel').forEach(p => p.classList.remove('subtab-panel--active'));
    tab.classList.add('subtab--active');
    document.getElementById('subtab-' + tab.dataset.subtab)?.classList.add('subtab-panel--active');
    if (tab.dataset.subtab === 'job-list')     Manager.loadJobList();
    if (tab.dataset.subtab === 'applications') Manager.loadApplications();
    if (tab.dataset.subtab === 'charts')       Manager.loadCharts();
    if (tab.dataset.subtab === 'audit')        Manager.loadAudit(1);
  });
});

// Job search (candidato)
let jobSearchTimer;
document.getElementById('job-search-input')?.addEventListener('input', () => {
  clearTimeout(jobSearchTimer);
  jobSearchTimer = setTimeout(() => Portal.filterJobs(), 300);
});
document.getElementById('job-filter-location')?.addEventListener('change', () => Portal.filterJobs());

// Masks
document.getElementById('apply-cpf').addEventListener('input',  function() { this.value = maskCpf(this.value); });
document.getElementById('apply-phone').addEventListener('input', function() { this.value = maskPhone(this.value); });

// Drop zone
const dz = document.getElementById('resume-drop-zone');
dz.addEventListener('dragover',  e => { e.preventDefault(); dz.classList.add('file-drop--over'); });
dz.addEventListener('dragleave', () => dz.classList.remove('file-drop--over'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('file-drop--over');
  const file = e.dataTransfer.files[0];
  if (file) { document.getElementById('apply-resume').files = e.dataTransfer.files; Portal.handleResumeFile(document.getElementById('apply-resume')); }
});

// Login
document.getElementById('login-form').addEventListener('submit', async function(e) {
  e.preventDefault(); clearAlert('login-alert');
  const btn = this.querySelector('[type="submit"]');
  btn.disabled = true; btn.textContent = 'Entrando...';
  try {
    const r = await request('/api/auth/login', { method: 'POST', body: JSON.stringify({
      username: document.getElementById('login-username').value.trim(),
      password: document.getElementById('login-password').value,
    })});
    sessionToken = r.token; sessionUsername = r.username;
    AppState.role = r.role; AppState.username = r.username;
    localStorage.setItem('rz_token', r.token);
    showToast('Bem-vindo!', `Logado como ${r.username}`, 'success');
    Manager.showDashboard();
  } catch (err) { showAlert('login-alert', '❌ ' + err.message); }
  finally { btn.disabled = false; btn.textContent = 'Entrar'; }
});


// ── Solicitações de Vaga ─────────────────────────────────────
const Solicitacoes = {
  async load() {
    const el = document.getElementById('solicitacoes-list');
    if (!el) return;
    try {
      const items = await request('/api/solicitacoes');
      this._renderBadge(items.filter(s => s.status === 'PENDENTE').length);
      if (!items.length) { el.innerHTML = '<p style="color:var(--ink-3);text-align:center;padding:32px;">Nenhuma solicitação encontrada.</p>'; return; }
      const isOwner = AppState.role === 'ROLE_OWNER';
      el.innerHTML = items.map(s => {
        const statusColor = { PENDENTE: '#FFB830', APROVADA: '#2ECC71', REJEITADA: '#FF5252' }[s.status] || '#AAA';
        const statusLabel = { PENDENTE: '⏳ Pendente', APROVADA: '✅ Aprovada', REJEITADA: '❌ Rejeitada' }[s.status] || s.status;
        const decideButtons = isOwner && s.status === 'PENDENTE' ? `
          <div style="display:flex;gap:8px;margin-top:12px;">
            <button onclick="Solicitacoes.decide(${s.id},'APROVADA')" style="flex:1;padding:10px;border-radius:8px;background:#0D2E1A;border:2px solid #2ECC71;color:#2ECC71;font-weight:700;cursor:pointer;">✅ Aprovar</button>
            <button onclick="Solicitacoes.rejeitar(${s.id})" style="flex:1;padding:10px;border-radius:8px;background:#2E0D0D;border:2px solid #FF5252;color:#FF5252;font-weight:700;cursor:pointer;">❌ Rejeitar</button>
          </div>` : '';
        const motivoHtml = s.motivoRejeicao ? `<p style="margin:6px 0 0;font-size:12px;color:#FF5252;">Motivo: ${s.motivoRejeicao}</p>` : '';
        return `<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:18px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
            <div>
              <p style="font-size:16px;font-weight:800;color:#fff;margin:0 0 2px;">${s.position}</p>
              <p style="font-size:13px;color:#A8A8B8;margin:0;">📍 ${s.location} · ${s.numVagas} vaga(s) · ${s.tipo || ''}</p>
              ${isOwner ? `<p style="font-size:12px;color:#5A6478;margin:4px 0 0;">Solicitante: ${s.solicitanteNome} &lt;${s.solicitanteEmail}&gt;</p>` : ''}
              <p style="font-size:12px;color:#5A6478;margin:4px 0 0;">Justificativa: ${s.justificativa}</p>
            </div>
            <span style="background:rgba(0,0,0,.3);border:1px solid ${statusColor};color:${statusColor};border-radius:20px;padding:4px 14px;font-size:12px;font-weight:700;white-space:nowrap;">${statusLabel}</span>
          </div>
          ${motivoHtml}
          ${decideButtons}
        </div>`;
      }).join('');
    } catch(e) { el.innerHTML = '<p style="color:#FF5252;text-align:center;padding:24px;">Erro ao carregar solicitações.</p>'; }
  },

  _renderBadge(count) {
    const badge = document.getElementById('count-solicitacoes');
    if (!badge) return;
    if (count > 0) { badge.textContent = count; badge.style.display = 'inline-block'; }
    else badge.style.display = 'none';
  },

  async loadBadge() {
    try {
      const d = await request('/api/solicitacoes/pending-count');
      this._renderBadge(d.count || 0);
    } catch {}
  },

  async decide(id, decision, motivo) {
    try {
      await request(`/api/solicitacoes/${id}/decide`, { method: 'POST', body: JSON.stringify({ decision, motivo: motivo || '' }) });
      showToast(decision === 'APROVADA' ? 'Vaga aprovada!' : 'Solicitação rejeitada', '', decision === 'APROVADA' ? 'success' : 'error');
      Manager.loadStats(); Portal.loadJobList(); this.load();
    } catch(e) { showToast('Erro', e.message, 'error'); }
  },

  rejeitar(id) {
    const motivo = prompt('Motivo da rejeição (será enviado ao gestor):');
    if (motivo === null) return;
    this.decide(id, 'REJEITADA', motivo);
  }
};

// Subtab: Solicitações
document.querySelector('[data-subtab="solicitacoes"]')?.addEventListener('click', () => {
  Solicitacoes.load();
});

// Solicitar vaga (envia para aprovação do Rafael)
document.getElementById('create-job-form').addEventListener('submit', async function(e) {
  e.preventDefault(); clearAlert('create-job-alert');
  const position      = document.getElementById('job-position').value;
  const location      = document.getElementById('job-location').value;
  const tipo          = document.getElementById('job-tipo').value;
  const name          = document.getElementById('job-manager-name').value.trim();
  const email         = document.getElementById('job-manager-email').value.trim();
  const justificativa = document.getElementById('job-justificativa').value.trim();
  if (!position || !location || !tipo || !name || !email || !justificativa) {
    showAlert('create-job-alert','❌ Preencha todos os campos obrigatórios, incluindo a justificativa.'); return;
  }
  const btn = document.getElementById('create-job-btn');
  btn.disabled = true; btn.textContent = 'Enviando...';
  try {
    await request('/api/solicitacoes', { method: 'POST', body: JSON.stringify({
      position, location, tipo, lgpdConsent: true,
      numVagas:     parseInt(document.getElementById('job-num-vagas').value) || 1,
      finalidade:   document.getElementById('job-description').value.trim() || null,
      responsavel:  name,
      emailResp:    email,
      justificativa,
      expiresAt:    document.getElementById('job-expires').value || null,
    })});
    showAlert('create-job-alert','✅ Solicitação enviada! Aguardando aprovação da diretoria.','success');
    showToast('Solicitação enviada!', `${position} — ${location}`, 'success');
    Solicitacoes.load();
    setTimeout(() => { clearAlert('create-job-alert'); document.getElementById('create-job-form').reset(); }, 4000);
  } catch (err) { showAlert('create-job-alert','❌ ' + err.message); }
  finally { btn.disabled = false; btn.textContent = 'Enviar para Aprovação'; }
});

// Editar vaga
document.getElementById('edit-job-form').addEventListener('submit', async function(e) {
  e.preventDefault(); clearAlert('edit-job-alert');
  const jobId    = document.getElementById('edit-job-id').value;
  const position = document.getElementById('edit-job-position').value;
  const location = document.getElementById('edit-job-location').value;
  const tipo     = document.getElementById('edit-job-tipo').value;
  const name     = document.getElementById('edit-job-manager-name').value.trim();
  const email    = document.getElementById('edit-job-manager-email').value.trim();
  if (!position || !location || !tipo || !name || !email) { showAlert('edit-job-alert','❌ Preencha todos os campos obrigatórios.'); return; }
  const btn = document.getElementById('edit-job-btn');
  btn.disabled = true; btn.textContent = 'Salvando...';
  try {
    await request(`/api/jobs/${jobId}`, { method: 'PUT', body: JSON.stringify({
      position, location, tipo,
      numVagas:    parseInt(document.getElementById('edit-job-num-vagas').value) || 1,
      finalidade:  document.getElementById('edit-job-description').value.trim() || null,
      responsavel: name, emailResp: email,
      expiresAt: document.getElementById('edit-job-expires').value || null,
    })});
    showToast('Vaga atualizada!', position, 'success');
    Manager.closeEditModal(); Manager.loadJobList(); Portal.loadJobList();
  } catch (err) { showAlert('edit-job-alert','❌ ' + err.message); }
  finally { btn.disabled = false; btn.textContent = 'Salvar Alterações'; }
});

// Candidatura
document.getElementById('apply-form').addEventListener('submit', async function(e) {
  e.preventDefault();
  if (!selectedJob) return;
  const required = ['apply-full-name','apply-cpf','apply-rg','apply-current-city','apply-phone','apply-email','apply-education','apply-experience','apply-pants-size','apply-shirt-size','apply-boot-size'];
  let valid = true;
  required.forEach(id => {
    const f = document.getElementById(id);
    if (!f || !f.value.trim()) {
      valid = false;
      f?.classList.add('form-field__input--invalid');
      setTimeout(() => f?.classList.remove('form-field__input--invalid'), 3000);
    }
  });
  if (!valid) { showAlert('apply-form-alert','❌ Preencha todos os campos obrigatórios.'); return; }
  clearAlert('apply-form-alert');
  const btn = document.getElementById('apply-submit-btn');
  btn.disabled = true; btn.textContent = 'Enviando...';
  try {
    const fd = new FormData();
    fd.append('jobId',                 selectedJob.id);
    fd.append('fullName',              document.getElementById('apply-full-name').value.trim());
    fd.append('cpf',                   document.getElementById('apply-cpf').value.trim());
    fd.append('rg',                    document.getElementById('apply-rg').value.trim());
    fd.append('dataNascimento',        document.getElementById('apply-birth-date').value || '');
    fd.append('tipoSanguineo',         document.getElementById('apply-blood-type').value || '');
    fd.append('nomeMae',               document.getElementById('apply-mothers-name').value.trim());
    fd.append('cidadeNatal',           document.getElementById('apply-birth-city').value.trim());
    fd.append('cidadeAtual',           document.getElementById('apply-current-city').value.trim());
    fd.append('phone',                 document.getElementById('apply-phone').value.trim());
    fd.append('email',                 document.getElementById('apply-email').value.trim());
    fd.append('linkedin',              document.getElementById('apply-linkedin').value.trim());
    fd.append('education',             document.getElementById('apply-education').value);
    fd.append('experience',            document.getElementById('apply-experience').value);
    fd.append('disponibilidadeViagem', document.getElementById('apply-travel').value);
    fd.append('tamanhoCalca',          document.getElementById('apply-pants-size').value);
    fd.append('tamanhoCamisa',         document.getElementById('apply-shirt-size').value);
    fd.append('tamanhoBota',           document.getElementById('apply-boot-size').value);
    fd.append('carteira',              getCheckedValues('cnh').join(','));
    fd.append('nrs',                   getCheckedValues('nrs').join(','));
    fd.append('escolas',               getCheckedValues('escola').join(','));
    fd.append('motivation',            document.getElementById('apply-motivation').value.trim());
    const resumeFile = document.getElementById('apply-resume').files[0];
    if (resumeFile) fd.append('resume', resumeFile);

    const r = await fetch(API_BASE + '/api/candidaturas', { method: 'POST', body: fd });
    if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.message || `Erro ${r.status}`); }
    showAlert('apply-form-alert','✅ Candidatura enviada! Entraremos em contato em breve.','success');
    showToast('Candidatura enviada!', selectedJob.position, 'success');
    setTimeout(() => Portal.backToJobList(), 3500);
  } catch (err) { showAlert('apply-form-alert','❌ ' + err.message); showToast('Erro', err.message, 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Enviar Candidatura'; }
});

// ─── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Restaura sessão do gestor a partir do localStorage (persiste navegação entre páginas)
  const savedToken = localStorage.getItem('rz_token');
  const savedUser  = localStorage.getItem('rz_username');
  const savedRole  = localStorage.getItem('rz_role');
  if (savedToken && !sessionToken) {
    sessionToken    = savedToken;
    sessionUsername = savedUser || '';
    AppState.role   = savedRole || 'ROLE_ADMIN';
    AppState.username = savedUser || '';
  }

  // Se veio de /admissao ou /admissoes, abre direto na aba do gestor
  if (new URLSearchParams(window.location.search).get('gestor') === '1') {
    history.replaceState({}, '', '/');
    if (sessionToken) {
      // Já logado — abre dashboard do gestor direto
      document.querySelectorAll('.nav__tab').forEach(t => t.classList.remove('nav__tab--active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('panel--active'));
      const tabGestor = document.querySelector('[data-panel="manager"]');
      if (tabGestor) tabGestor.classList.add('nav__tab--active');
      const panelGestor = document.getElementById('panel-manager');
      if (panelGestor) panelGestor.classList.add('panel--active');
      Manager.showDashboard();
    }
  }

  await Portal.loadJobList();
  const vagaId = new URLSearchParams(window.location.search).get('vaga');
  if (vagaId) Portal.selectJob(parseInt(vagaId));
});
