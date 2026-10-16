/* =====================================================================
   REZENDE ENERGIA — SESSÃO DO GESTOR (NewRh)
   ---------------------------------------------------------------------
   Guarda o login em UM só lugar (localStorage) para que todas as telas
   (menu inicial, Admissão, Admissões) compartilhem a mesma sessão.
   Antes, o login por Microsoft ficava só na memória da página inicial e
   num cookie; ao ir para /admissao e voltar, a página inicial não achava
   a sessão e pedia o login de novo.

   A sessão vale enquanto o token (JWT, 24 h) não expirar. "Sair" apaga tudo.
   ===================================================================== */
(function () {
  var CHAVES = ['rz_token', 'rz_username', 'rz_role', 'rz_email', 'rz_name'];

  function ls(op, k, v) {
    try {
      if (op === 'get') return localStorage.getItem(k);
      if (op === 'set') localStorage.setItem(k, v);
      if (op === 'del') localStorage.removeItem(k);
    } catch (e) { /* navegador sem storage */ }
    return null;
  }

  function cookie(nome) {
    var m = document.cookie.match('(?:^|;)\\s*' + nome + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m[1]) : null;
  }

  /* Lê o conteúdo (sem validar assinatura) do JWT: sub, role, exp */
  function decodificar(token) {
    try {
      var p = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      while (p.length % 4) p += '=';
      return JSON.parse(decodeURIComponent(escape(atob(p))));
    } catch (e) { return null; }
  }

  function expirado(token) {
    var d = decodificar(token);
    if (!d || !d.exp) return true;
    return d.exp * 1000 <= Date.now() + 15000; // 15 s de folga
  }

  var RzSessao = {
    /* Grava a sessão. dados: {token, username, role, email, name} */
    salvar: function (dados) {
      if (!dados || !dados.token) return;
      var d = decodificar(dados.token) || {};
      ls('set', 'rz_token', dados.token);
      ls('set', 'rz_username', dados.username || d.sub || '');
      ls('set', 'rz_role', dados.role || d.role || '');
      if (dados.email) ls('set', 'rz_email', String(dados.email).toLowerCase());
      if (dados.name) ls('set', 'rz_name', dados.name);
    },

    /* Devolve a sessão válida ou null. Aproveita o cookie do login Microsoft se o storage estiver vazio. */
    ler: function () {
      var token = ls('get', 'rz_token') || cookie('rz_token');
      if (!token) return null;
      if (expirado(token)) { this.limpar(); return null; }
      var d = decodificar(token) || {};
      var sessao = {
        token: token,
        username: ls('get', 'rz_username') || d.sub || '',
        role: ls('get', 'rz_role') || d.role || '',
        email: (ls('get', 'rz_email') || '').toLowerCase(),
        name: ls('get', 'rz_name') || ''
      };
      if (!ls('get', 'rz_token')) this.salvar(sessao); // sincroniza o que veio só do cookie
      return sessao;
    },

    valida: function () { return !!this.ler(); },

    /* Sair: apaga storage e cookie */
    limpar: function () {
      CHAVES.forEach(function (k) { ls('del', k); });
      ls('del', 'rz_gestor_autorizado');
      try {
        document.cookie = 'rz_token=; Max-Age=0; path=/; SameSite=Lax';
      } catch (e) { /* ignora */ }
      try { sessionStorage.removeItem('rz_token'); sessionStorage.removeItem('token'); } catch (e) { /* ignora */ }
    },

    /* Cabeçalho pronto para as chamadas da API */
    cabecalho: function () {
      var s = this.ler();
      return s ? { Authorization: 'Bearer ' + s.token } : {};
    },

    /* Sessão perdida/expirada: apaga e leva para a tela de login */
    expirou: function () {
      this.limpar();
      window.location.href = '/login?erro=sessao_expirada';
    }
  };

  window.RzSessao = RzSessao;
})();
