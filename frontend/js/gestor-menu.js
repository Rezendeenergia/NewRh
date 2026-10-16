/* Menu lateral da Área do Gestor.
   Pega a barra de abas (.subtab-bar) e a coloca numa barra lateral fixa, como no CromFolgas.
   Os botões continuam os mesmos (app.js segue controlando as abas); aqui só muda o lugar e o visual. */
(function () {
  'use strict';
  var side = document.getElementById('gs-side');
  var nav = document.getElementById('gs-nav');
  var barra = document.querySelector('.subtab-bar');
  var painel = document.getElementById('panel-manager');
  var dash = document.getElementById('manager-dashboard');
  if (!side || !nav || !barra || !painel || !dash) return;

  /* ícones de linha (24x24) por aba */
  var P = {
    'create-job': '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M12 12v5M9.5 14.5h5"/>',
    'job-list': '<rect x="8" y="3" width="8" height="4" rx="1"/><path d="M16 5h2a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2M9 12h6M9 16h6"/>',
    'applications': '<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0M16 4.8a3.2 3.2 0 0 1 0 6.4M18 14.5A6 6 0 0 1 21 20"/>',
    'charts': '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    'funil': '<path d="M3 4h18l-7 8.5V19l-4 2v-8.5z"/>',
    'headcount': '<circle cx="12" cy="7" r="3.2"/><path d="M5 21a7 7 0 0 1 14 0"/>',
    'audit': '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    'solicitacoes': '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/>',
    '/admissao': '<path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 10h4a1 1 0 0 1 1 1v10M2 21h20M8 8h3M8 12h3M8 16h3"/>',
    '/admissoes': '<path d="M3 21h18M5 21V12a7 7 0 0 1 14 0v9M12 5V3M9 21v-5h6v5"/>',
    'banco-talentos': '<circle cx="12" cy="9" r="5.5"/><path d="m8.5 13.5-1.5 7.5 5-3 5 3-1.5-7.5"/>',
    'colaboradores-admitidos': '<path d="m2 9 10-5 10 5-10 5z"/><path d="M6 11.2V16c0 1.4 2.7 3 6 3s6-1.6 6-3v-4.8M22 9v6"/>',
    'menor-aprendiz': '<path d="M12 21v-8M12 13c0-4 3-6.5 8-6.5 0 4-3 6.5-8 6.5zM12 15c0-3-2.2-5-6.5-5 0 3 2.2 5 6.5 5z"/>',
    'talentos-cadastros': '<circle cx="9" cy="8" r="3.4"/><path d="M3 20a6 6 0 0 1 12 0M18 8v6M15 11h6"/>'
  };
  var ROTULO_ROLE = { ROLE_ADMIN: 'Admin', ROLE_OWNER: 'Aprovador', ROLE_VIEWER: 'Equipe RH', ROLE_GESTOR: 'Gestor' };

  /* 1) move a barra de abas para o menu lateral e troca os emojis por ícones */
  nav.appendChild(barra);
  barra.querySelectorAll('.subtab').forEach(function (item) {
    var chave = item.getAttribute('data-subtab') || item.getAttribute('href');
    var no = null;
    for (var i = 0; i < item.childNodes.length; i++) {
      if (item.childNodes[i].nodeType === 3 && item.childNodes[i].nodeValue.trim()) { no = item.childNodes[i]; break; }
    }
    if (no) no.nodeValue = no.nodeValue.replace(/^[^\p{L}\p{N}]+/u, '');
    if (P[chave]) {
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('class', 'gs-ico');
      svg.setAttribute('aria-hidden', 'true');
      svg.innerHTML = P[chave];
      item.insertBefore(svg, item.firstChild);
    }
  });

  /* 2) gaveta no celular */
  function abrir(sim) {
    side.classList.toggle('aberto', !!sim);
    document.body.classList.toggle('gs-aberto', !!sim);
  }
  var btnMenu = document.getElementById('gs-menu-btn');
  if (btnMenu) btnMenu.addEventListener('click', function () { abrir(!side.classList.contains('aberto')); });
  document.getElementById('gs-veu').addEventListener('click', function () { abrir(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') abrir(false); });
  barra.addEventListener('click', function (e) { if (e.target.closest('.subtab')) abrir(false); });

  /* 3) rodapé: portal, usuário, sair */
  document.getElementById('gs-portal').addEventListener('click', function (e) {
    e.preventDefault();
    abrir(false);
    var aba = document.querySelector('.nav__tab[data-panel="candidate"]');
    if (aba) aba.click(); else location.href = '/';
  });
  document.getElementById('gs-sair').addEventListener('click', function () {
    if (typeof Manager !== 'undefined' && Manager.logout) Manager.logout();
    else { if (window.RzSessao) RzSessao.limpar(); location.href = '/login'; }
  });

  function atualizarUsuario() {
    var s = (window.RzSessao && RzSessao.ler && RzSessao.ler()) || {};
    var nome = s.name || s.username || '';
    document.getElementById('gs-nome').textContent = nome;
    document.getElementById('gs-av').textContent = (nome.trim().split(/\s+/).map(function (p) { return p[0]; }).slice(0, 2).join('') || '?').toUpperCase();
    document.getElementById('gs-role').textContent = ROTULO_ROLE[s.role] || '';
  }

  /* 4) o menu só aparece quando o painel do gestor está na tela */
  function sincronizar() {
    var ativo = painel.classList.contains('panel--active') && dash.style.display === 'block';
    if (ativo === document.body.classList.contains('gs-ativo')) return;
    document.body.classList.toggle('gs-ativo', ativo);
    if (ativo) atualizarUsuario(); else abrir(false);
  }
  var mo = new MutationObserver(sincronizar);
  mo.observe(painel, { attributes: true, attributeFilter: ['class'] });
  mo.observe(dash, { attributes: true, attributeFilter: ['style'] });
  sincronizar();
})();
