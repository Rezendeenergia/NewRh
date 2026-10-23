# NewRh — Recrutamento e Admissão

Sistema de RH da Rezende Energia: **vagas** (abertas pelo RH ou por **solicitação de vaga** aprovada por e-mail), **candidaturas** (portal do candidato com conta própria, acompanhamento e documentos), **banco de talentos**, **menor aprendiz** e o **processo de admissão** em etapas por departamento (RH → DP → DP externo → TI → SESMT → DP) até a liberação para campo, com a **pasta do colaborador** no SharePoint.

- Produção: https://newrh.onrender.com (Render). O deploy automático já falhou antes: depois de um push, confira no Render se a versão nova subiu.
- Banco: Supabase **NewRh** (`rstwkptsfdptkfuuunaa`) via SQLAlchemy + `pg8000` (`DATABASE_URL`). Modelos em `backend/models.py`; `Base.metadata.create_all` cria tabelas novas na subida, mas **não altera** tabelas existentes. Coluna nova vai em SQL versionado (ex.: `migration_solicitacoes.sql`) aplicado pelo dono.
- Indicadores no Portal Rezende: fonte `newrh` (caixa **RH**) — SQL em `PortalRez/database/kpis/newrh.sql`, inclusive os **tempos médios de contratação** (vaga → ASO, eSocial/`DP_EXTERNO` → `INTEGRACAO_EQUATORIAL`, vaga → `INTEGRACAO_EQUATORIAL`).

## Stack e estrutura

- `backend/` — **Python 3.11 / Flask** (`main.py`), servido por gunicorn com gevent (`gunicorn.conf.py`, 2 workers; o `monkey.patch_all()` precisa rodar antes de qualquer import de rede). Flask também serve o `frontend/`.
  - `routers/`: `auth`, `jobs` (vagas), `candidaturas`, `processos` (admissão), `solicitacoes` (pedido de vaga), `banco_talentos`, `menor_aprendiz`; mais `colaboradores_router.py`.
  - `auth_microsoft.py` (login dos gestores), `candidato_auth.py` (conta e senha do candidato), `security.py` (JWT e papéis), `email_service.py` (Graph, remetente `MS_SENDER_EMAIL`), `sharepoint_service.py` e `pasta_colaborador.py` (pastas e documentos), `alertas.py` (APScheduler: processos parados há `ALERTA_DIAS_PARADO` dias), `audit.py`, `cache.py`.
- `frontend/` — páginas HTML + `app.js` (área do gestor com menu lateral `js/gestor-menu.js`), `admissao.html` / `admissoes.html`, páginas do candidato (`acompanhar.html`, `ativar.html`, `definir-senha-candidato.html`, `redefinir-senha.html`), tema `css/rezende-tema.css` + `js/rezende-tema.js`, sessão em `js/rz-sessao.js`.

## Papéis

JWT com `role`: `ROLE_OWNER` e `ROLE_ADMIN` (editam), `ROLE_VIEWER` (só leitura — bloqueado nas rotas que usam `require_admin`). Candidatos têm login separado (`candidato_contas`).

- Quem entra no painel de gestão e com qual `role` é decidido pelo **Portal Rezende** (`backend/portal_client.py`, setor **RH**), consultado a cada login via `GET /api/integracao/acesso?sistema=newrh&email=…` (cache de 1 min, tolera até 15 min de portal fora do ar). Nível do portal → role: `administrar`/`editar` → `ROLE_ADMIN`, `visualizar` → `ROLE_VIEWER`.
- `ROLE_OWNER` (hoje só Rafael, em `DONOS_APROVACAO`) é uma permissão isolada só para aprovar abertura de vaga (`routers/solicitacoes.py`) — não é um nível do portal, fica como lista própria por cima do que o portal disser.
- `ROLE_GESTOR` (gerentes de campo que só pedem abertura de vaga, em `GESTORES_CAMPO`) também fica fora do portal: não são da equipe de RH/DP, então não fazem sentido no setor RH. **Atenção:** `require_admin` só bloqueia `ROLE_VIEWER` — hoje um `ROLE_GESTOR` passa por qualquer rota que não seja `ROLE_OWNER`-only, mais acesso do que "só solicitar vaga" sugere; não criei essa restrição, é um comportamento pré-existente.
- O cadastro local (`models.User`) é espelho: `role` é sempre sobrescrito no login a partir do portal (ou das listas acima) — editar `role` direto no banco não pega.

## Processo de admissão

- As etapas e a ordem ficam em `ETAPAS_FLUXO` (`routers/processos.py`): TRIAGEM, ENTREVISTA, CERTIFICADOS_NR, APROVACAO_FINAL, ASO, DP_EXTERNO, CADASTRO_GPM, ACESSO_TI, SOLIDES, ATLAS, ACEITE_BERNHOEFT, PRONTUARIO_SEGURANCA, EPIS_UNIFORMES, FORMACAO_NRS, PROVA_DEEP, ASSINATURAS, BEMHOEFT, GRAFICA_CRACHA, INTEGRACAO_EQUATORIAL, LIBERADO_CAMPO. O departamento responsável por etapa pode ser trocado em `etapa_config`.
- Os **códigos** das etapas são usados pelo portal e pelas pastas do SharePoint (`sharepoint_service.py`); não renomeie um código existente.
- Processos antigos guardam a ordem da época em `etapa_processo.ordem`; não reordene registros já criados.
- Devolver/reabrir etapa exige motivo; responsável e editores por etapa ficam gravados.

## Variáveis (Render)

`DATABASE_URL`, `SECRET_KEY`, `MS_CLIENT_ID/MS_CLIENT_SECRET/MS_TENANT_ID`, `MS_SENDER_EMAIL`, `BASE_URL`, `RH_EMAIL`, `EMAIL_ENABLED`, `ALERTA_DIAS_PARADO`, `PORTAL_URL` (`https://portalrez.onrender.com`), `PORTAL_INTEGRACAO_TOKEN` (mesmo valor do `INTEGRACAO_TOKEN` configurado no PortalRez).

## Cuidados

- Candidaturas têm dados pessoais (CPF, RG, data de nascimento, nome da mãe, tamanhos de uniforme) e consentimento LGPD (`lgpd_consent`): não exponha em listas públicas, logs ou exportações sem necessidade.
- `EMAIL_ENABLED` controla o envio real de e-mails; para testes, deixe desligado.
- Não versione `__pycache__` (já está no `.gitignore`).

## Ecossistema Rezende (vale para todos os sistemas)

- **Portal Rezende** (repo `Rezendeenergia/PortalRez`, https://portalrez.onrender.com) é a porta de entrada e o centro dos acessos: setores, pessoas e nível (visualizar / editar / administrar) ficam na tela **Acessos** do portal. Sistema novo deve perguntar ao portal quem pode entrar, em vez de manter lista própria de usuários.
- **Indicadores no portal:** o portal lê os totais de cada sistema chamando a função `portal.kpis()` no banco Supabase do sistema, com o usuário `portal_leitura` (só executa essa função). O SQL fica em `PortalRez/database/kpis/<chave>.sql`. Ao renomear ou mudar tabelas/colunas usadas ali, ajuste esse arquivo e a função no banco, senão a caixa do setor no portal quebra. Não apague o schema `portal` nem o papel `portal_leitura`.
- **Login:** somente conta Microsoft corporativa `@rezendeenergia.com.br`, tenant `56a8eefc-c653-4efd-a3db-db881ffbde6e`. O app do Azure usado para ler o SharePoint é o mesmo dos outros sistemas (variáveis `SHAREPOINT_CLIENT_ID/SECRET/TENANT_ID`).
- **Visual:** padrão Rezende (`rezende-tema.css` / `rezende-tema.js`, modo claro e escuro, laranja da marca, fontes Barlow). Telas novas seguem esse tema.
- **Idioma:** telas, mensagens, comentários e commits em português do Brasil, em linguagem simples (quem usa não é desenvolvedor). Datas no fuso de Santarém-PA (`America/Santarem`, UTC−3).
- **Deploy:** Render, com deploy automático a cada push na `main`. Banco: Supabase (região São Paulo).
- **Fluxo de trabalho:** mudanças vão por branch + pull request para a `main` (o dono revisa e faz o merge); só o PortalRez pode receber commit direto na `main`. Mudança de banco vai em arquivo `.sql` versionado no repo e é aplicada pelo dono no SQL Editor do Supabase; não rode SQL de alteração em produção sem ele pedir.
- **Segredos:** nunca escreva senha, chave ou token no código nem em commit; tudo vem de variável de ambiente no Render. Dados pessoais (CPF, salário, telefone) não vão para logs, prints ou planilhas exportadas sem necessidade.
