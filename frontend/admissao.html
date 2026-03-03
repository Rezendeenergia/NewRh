<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Admissão — Rezende Energia</title>
  <link href="https://fonts.googleapis.com/css2?family=Sora:wght@700;800;900&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
<!-- Login Screen -->
<div id="login-screen" style="display:none;min-height:100vh;align-items:center;justify-content:center;background:var(--void);">
  <div style="background:var(--surface);border:1px solid rgba(255,255,255,.07);border-radius:28px;padding:40px 36px;width:100%;max-width:380px;box-shadow:0 32px 80px rgba(0,0,0,.6);">
    <div style="text-align:center;margin-bottom:28px;">
      <div style="font-size:2rem;margin-bottom:8px;">🔐</div>
      <h2 style="font-family:Sora,sans-serif;font-size:1.4rem;font-weight:900;color:#fff;margin-bottom:6px;">Acesso Restrito</h2>
      <p style="color:var(--ink-3);font-size:.85rem;">Portal de Admissão — Rezende Energia</p>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px;">
      <input id="l-user" type="text" placeholder="Usuário" class="form-field__input" style="width:100%;" onkeydown="if(event.key==='Enter')document.getElementById('l-pass').focus()">
      <input id="l-pass" type="password" placeholder="Senha" class="form-field__input" style="width:100%;" onkeydown="if(event.key==='Enter')doLogin()">
      <div id="l-err" style="display:none;background:rgba(255,82,82,.1);color:#FF5252;border:1px solid rgba(255,82,82,.3);border-radius:8px;padding:10px 14px;font-size:.83rem;"></div>
      <button id="l-btn" class="btn btn--primary btn--full" onclick="doLogin()">Entrar</button>
      <a href="/" style="text-align:center;color:var(--ink-3);font-size:.78rem;text-decoration:none;margin-top:4px;">← Voltar ao Portal</a>
    </div>
  </div>
</div>

<!-- App Screen -->
<div id="app-screen" class="adm-layout" style="display:none;">

  <!-- ── Sidebar ─────────────────────────────── -->
  <aside class="adm-sidebar">
    <div class="sidebar-header">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div class="sidebar-header__brand">⚡ Rezende RH</div>
          <div class="sidebar-header__sub">Admissão</div>
        </div>
        <a href="/" style="color:var(--ink-3);font-size:.75rem;text-decoration:none;">← Portal</a>
      </div>
    </div>

    <div class="sidebar-stats">
      <div class="s-stat"><div class="s-stat__n" id="stat-andamento">—</div><div class="s-stat__l">Em andamento</div></div>
      <div class="s-stat"><div class="s-stat__n" id="stat-concluidos">—</div><div class="s-stat__l">Concluídos</div></div>
    </div>

    <div class="sidebar-filter" style="display:flex;gap:6px;">
      <select id="filter-status" class="form-field__select" style="flex:1;padding:6px 8px;font-size:.78rem;" onchange="Adm.loadLista()">
        <option value="">Todos</option>
        <option value="EM_ANDAMENTO">Em andamento</option>
        <option value="CONCLUIDO">Concluídos</option>
        <option value="CANCELADO">Cancelados</option>
      </select>
      <select id="filter-dept" class="form-field__select" style="flex:1;padding:6px 8px;font-size:.78rem;" onchange="Adm.loadLista()">
        <option value="">Todos depts</option>
        <option value="RH">RH</option>
        <option value="DP">Depto Pessoal</option>
        <option value="DP_EXTERNO">DP Externo</option>
        <option value="SESMT">SESMT</option>
      </select>
    </div>

    <div class="processo-list" id="processo-list">
      <div style="padding:24px;text-align:center;color:var(--ink-3);font-size:.83rem;">Carregando...</div>
    </div>
  </aside>

  <!-- ── Main ─────────────────────────────────── -->
  <main class="adm-main" id="adm-main">
    <div class="empty-adm">
      <div class="empty-adm__icon">📋</div>
      <p>Selecione um processo na lista ao lado</p>
    </div>
  </main>

</div>

<!-- Modal de ação -->
<div class="modal" id="action-modal" onclick="Adm.closeModal()">
  <div class="modal__box" onclick="event.stopPropagation()" style="max-width:480px;">
    <h3 class="modal__title" id="modal-title">Confirmar ação</h3>
    <div id="modal-body"></div>
    <div style="display:flex;gap:10px;margin-top:20px;">
      <button class="btn btn--ghost btn--full" onclick="Adm.closeModal()">Cancelar</button>
      <button class="btn btn--primary btn--full" id="modal-confirm">Confirmar</button>
    </div>
  </div>
</div>

<script>
let TOKEN = sessionStorage.getItem('token');

function showLogin() {
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app-screen').style.display = 'none';
}
function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'grid';
}

async function doLogin() {
  const user = document.getElementById('l-user').value.trim();
  const pass = document.getElementById('l-pass').value;
  const btn  = document.getElementById('l-btn');
  const err  = document.getElementById('l-err');
  if (!user || !pass) return;
  btn.disabled = true; btn.textContent = 'Entrando...';
  err.style.display = 'none';
  try {
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({username: user, password: pass})
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || 'Credenciais inválidas');
    TOKEN = data.token;
    sessionStorage.setItem('token', TOKEN);
    showApp();
    await Promise.all([Adm.loadStats(), Adm.loadLista()]);
  } catch(e) {
    err.textContent = e.message;
    err.style.display = 'block';
    btn.disabled = false; btn.textContent = 'Entrar';
  }
}

if (!TOKEN) {
  document.addEventListener('DOMContentLoaded', showLogin);
}

const API = '';

async function req(url, opts={}) {
  const r = await fetch(API + url, {
    ...opts,
    headers: { 'Authorization':'Bearer '+TOKEN, 'Content-Type':'application/json', ...(opts.headers||{}) }
  });
  if (!r.ok) { const e = await r.json().catch(()=>({message:'Erro'})); throw new Error(e.message); }
  return r.json();
}

async function reqForm(url, fd) {
  const r = await fetch(API + url, { method:'POST', headers:{'Authorization':'Bearer '+TOKEN}, body:fd });
  if (!r.ok) { const e = await r.json().catch(()=>({message:'Erro'})); throw new Error(e.message); }
  return r.json();
}

const STATUS_LABEL = { PENDENTE:'Pendente', EM_ANDAMENTO:'Em andamento', APROVADO:'Aprovado', REPROVADO:'Reprovado', REENVIAR:'Reenviar doc.' };
const STATUS_ICON  = { PENDENTE:'○', EM_ANDAMENTO:'◉', APROVADO:'✅', REPROVADO:'❌', REENVIAR:'🔄' };
const TIPO_ICON    = { APROVACAO:'🗂', DOCUMENTO:'📄', CHECKLIST:'☑', ENTREVISTA:'🎤' };

let currentProcessoId = null;
let currentProcesso   = null;

const Adm = {

  async loadStats() {
    try {
      const s = await req('/api/processos/stats');
      document.getElementById('stat-andamento').textContent  = s.andamento;
      document.getElementById('stat-concluidos').textContent = s.concluidos;
    } catch(e) { console.error(e); }
  },

  async loadLista() {
    const status = document.getElementById('filter-status').value;
    const dept   = document.getElementById('filter-dept').value;
    const list   = document.getElementById('processo-list');
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--ink-3);font-size:.83rem;">Carregando...</div>';
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (dept)   params.set('departamento', dept);
      const data = await req(`/api/processos?${params}`);
      if (data.items.length === 0) {
        list.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-3);font-size:.83rem;">Nenhum processo encontrado</div>';
        return;
      }
      list.innerHTML = data.items.map(p => `
        <div class="processo-item ${p.id===currentProcessoId?'processo-item--active':''}"
             onclick="Adm.loadProcesso(${p.id})">
          <p class="processo-item__nome">${p.candidatura.nome}</p>
          <p class="processo-item__cargo">${p.candidatura.cargo} · ${p.candidatura.local}</p>
          <div class="processo-item__bottom">
            <div class="progress-mini"><div class="progress-mini__fill" style="width:${p.progresso}%"></div></div>
            <span style="font-size:.7rem;color:var(--ink-3);">${p.progresso}%</span>
          </div>
          <div style="margin-top:6px;">
            <span class="pill pill--${p.status}">${p.status==='EM_ANDAMENTO'?'⏳ Em andamento':p.status==='CONCLUIDO'?'✅ Concluído':'❌ Cancelado'}</span>
          </div>
        </div>`).join('');
    } catch(e) {
      list.innerHTML = `<div style="padding:20px;text-align:center;color:#FF5252;font-size:.83rem;">${e.message}</div>`;
    }
  },

  async loadProcesso(id) {
    currentProcessoId = id;
    document.querySelectorAll('.processo-item').forEach(el => el.classList.remove('processo-item--active'));
    document.querySelectorAll('.processo-item').forEach(el => {
      if(el.onclick.toString().includes(`(${id})`)) el.classList.add('processo-item--active');
    });
    const main = document.getElementById('adm-main');
    main.innerHTML = '<div style="padding:60px;text-align:center;color:var(--ink-3);">Carregando...</div>';
    try {
      const p = await req(`/api/processos/${id}`);
      currentProcesso = p;
      main.innerHTML = Adm.renderProcesso(p);
    } catch(e) {
      main.innerHTML = `<div style="padding:40px;text-align:center;color:#FF5252;">${e.message}</div>`;
    }
  },

  renderProcesso(p) {
    const c = p.candidatura;
    const etapasHtml = p.etapas.map(e => Adm.renderEtapa(e, p.id)).join('');
    return `
      <div class="detalhe-header">
        <div>
          <h2 class="detalhe-nome">${c.nome}</h2>
          <p class="detalhe-cargo">📋 ${c.cargo} · 📍 ${c.local}</p>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <span class="pill pill--${p.status}">${p.status==='EM_ANDAMENTO'?'⏳ Em andamento':p.status==='CONCLUIDO'?'✅ Concluído':'❌ Cancelado'}</span>
            <span style="font-size:.8rem;color:var(--ink-3);">📧 ${c.email}</span>
            <span style="font-size:.8rem;color:var(--ink-3);">📱 ${c.phone}</span>
          </div>
        </div>
        <div style="text-align:right;">
          ${p.sharepointUrl ? `<a href="${p.sharepointUrl}" target="_blank" class="btn btn--ghost btn--small">📁 Pasta SharePoint</a>` : '<span style="font-size:.75rem;color:var(--ink-3);">📁 Pasta SharePoint criando...</span>'}
        </div>
      </div>

      <div style="margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:.8rem;color:var(--ink-3);">Progresso: <strong style="color:#fff;">${p.progresso}%</strong></span>
        <span style="font-size:.8rem;color:var(--ink-3);">Etapa atual: <strong style="color:var(--fire);">${p.etapaAtual || '—'}</strong></span>
      </div>
      <div class="progress-bar"><div class="progress-bar__fill" style="width:${p.progresso}%"></div></div>

      <div class="etapas-wrap">${etapasHtml}</div>`;
  },

  renderEtapa(e, processoId) {
    const isAtiva    = e.status === 'EM_ANDAMENTO';
    const isAprovada = e.status === 'APROVADO';
    const temDocs    = e.tipo === 'DOCUMENTO';
    const docsHtml   = e.documentos.length > 0 ? `
      <div class="docs-list">
        ${e.documentos.map(d => `
          <div class="doc-item">
            <span>📄</span>
            <span class="doc-item__name">${d.nome}</span>
            <span class="pill pill--${d.status}" style="font-size:.68rem;">${STATUS_LABEL[d.status]||d.status}</span>
            ${d.sharepointUrl ? `<a href="${d.sharepointUrl}" target="_blank" style="color:var(--fire);font-size:.75rem;text-decoration:none;">SP ↗</a>` : ''}
            ${isAtiva && d.status === 'PENDENTE' ? `
              <button class="btn btn--ghost btn--small" onclick="Adm.revisarDoc(${processoId},${e.id},${d.id},'APROVADO')">✅</button>
              <button class="btn btn--ghost btn--small" onclick="Adm.revisarDoc(${processoId},${e.id},${d.id},'REENVIAR')">🔄</button>
              <button class="btn btn--ghost btn--small" onclick="Adm.revisarDoc(${processoId},${e.id},${d.id},'REPROVADO')">❌</button>
            ` : ''}
          </div>`).join('')}
      </div>` : '';

    const uploadHtml = isAtiva && temDocs ? `
      <div class="upload-zone" onclick="document.getElementById('upload-${e.id}').click()">
        <input type="file" id="upload-${e.id}" onchange="Adm.uploadDoc(${processoId},${e.id},this)">
        <span style="color:var(--ink-2);font-size:.85rem;">📎 Clique para anexar documento</span>
      </div>` : '';

    const actionsHtml = isAtiva ? `
      <div class="nota-field">
        <textarea id="nota-${e.id}" placeholder="Observação / nota interna (opcional)"></textarea>
      </div>
      <div class="etapa-actions">
        <button class="btn btn-aprovar btn--small" onclick="Adm.atualizarEtapa(${processoId},${e.id},'APROVADO')">✅ Aprovar</button>
        <button class="btn btn-reenviar btn--small" onclick="Adm.atualizarEtapa(${processoId},${e.id},'REENVIAR')">🔄 Reenviar Doc.</button>
        <button class="btn btn-reprovar btn--small" onclick="Adm.atualizarEtapa(${processoId},${e.id},'REPROVADO')">❌ Reprovar</button>
        <button class="btn btn--small" style="background:rgba(90,100,120,.15);color:#9AA3B2;border:1px solid rgba(90,100,120,.3);" onclick="Adm.atualizarEtapa(${processoId},${e.id},'NAO_APLICAVEL')" title="Marcar como Não Aplicável — etapa será pulada">🚫 N/A</button>
      </div>` : '';

    const notaHtml = e.nota ? `<p style="font-size:.8rem;color:var(--ink-2);margin-top:8px;font-style:italic;">💬 ${e.nota}</p>` : '';
    const respHtml = e.responsavel ? `<p style="font-size:.75rem;color:var(--ink-3);margin-top:4px;">👤 ${e.responsavel} ${e.concluidoEm ? '· '+new Date(e.concluidoEm).toLocaleDateString('pt-BR') : ''}</p>` : '';

    return `
      <div class="etapa-card etapa-card--${e.status}" id="etapa-${e.id}">
        <div class="etapa-header" onclick="Adm.toggleEtapa(${e.id})">
          <div class="etapa-ordem etapa-ordem--${e.status}">${isAprovada?'✓':e.ordem}</div>
          <div class="etapa-info">
            <p class="etapa-nome">${TIPO_ICON[e.tipo]||''} ${e.nome}</p>
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
              <span class="dept-badge dept-${e.departamento}">${e.deptLabel}</span>
              <span class="pill pill--${e.status}" style="font-size:.68rem;">${STATUS_LABEL[e.status]||e.status}</span>
              ${e.prazo_dias ? `<span style="font-size:.7rem;color:var(--ink-3);">⏱ ${e.prazo_dias}d</span>` : ''}
            </div>
          </div>
          <span class="etapa-chevron ${isAtiva?'etapa-chevron--open':''}">▼</span>
        </div>
        <div class="etapa-body" id="body-${e.id}" style="${isAtiva?'':'display:none'}">
          ${notaHtml}${respHtml}${docsHtml}${uploadHtml}${actionsHtml}
        </div>
      </div>`;
  },

  toggleEtapa(id) {
    const body    = document.getElementById(`body-${id}`);
    const chevron = body.previousElementSibling.querySelector('.etapa-chevron');
    const visible = body.style.display !== 'none';
    body.style.display    = visible ? 'none' : 'block';
    chevron.classList.toggle('etapa-chevron--open', !visible);
  },

  async atualizarEtapa(processoId, etapaId, status) {
    const nota = document.getElementById(`nota-${etapaId}`)?.value || '';
    const labels = { APROVADO:'Aprovar esta etapa?', REPROVADO:'⚠️ Reprovar cancela o processo. Confirmar?', REENVIAR:'Solicitar reenvio de documentação?' };
    if (!confirm(labels[status])) return;
    try {
      await req(`/api/processos/${processoId}/etapas/${etapaId}`, {
        method:'PATCH', body:JSON.stringify({ status, nota })
      });
      await Adm.loadProcesso(processoId);
      await Adm.loadStats();
      await Adm.loadLista();
    } catch(e) { alert('Erro: ' + e.message); }
  },

  async uploadDoc(processoId, etapaId, input) {
    if (!input.files[0]) return;
    const fd = new FormData();
    fd.append('arquivo', input.files[0]);
    try {
      await reqForm(`/api/processos/${processoId}/etapas/${etapaId}/documentos`, fd);
      await Adm.loadProcesso(processoId);
    } catch(e) { alert('Erro no upload: ' + e.message); }
    input.value = '';
  },

  async revisarDoc(processoId, etapaId, docId, status) {
    const obs = status === 'REENVIAR' ? prompt('Motivo para reenvio (opcional):') || '' : '';
    try {
      await req(`/api/processos/${processoId}/etapas/${etapaId}/documentos/${docId}`, {
        method:'PATCH', body:JSON.stringify({ status, observacao: obs })
      });
      await Adm.loadProcesso(processoId);
    } catch(e) { alert('Erro: ' + e.message); }
  },

  closeModal() { document.getElementById('action-modal').style.display = 'none'; },
};

// Init
document.addEventListener('DOMContentLoaded', async () => {
  if (TOKEN) {
    showApp();
    await Promise.all([Adm.loadStats(), Adm.loadLista()]);
  } else {
    showLogin();
  }
});
</script>
</div>
</body>
</html>
