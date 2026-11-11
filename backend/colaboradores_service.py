"""
Serviço para buscar colaboradores da Base de Colaboradores.xlsx no SharePoint.
"""
import os, re, unicodedata, base64, requests
from sharepoint_service import _get_token, _get_site_id, _get_drive_id

# Link de compartilhamento da planilha "Base de Colaboradores - Rezende Energia.xlsx",
# copiado direto do SharePoint. É a forma mais confiável de achar o arquivo: a Graph
# API resolve esse link pro item certo (endpoint /shares), sem depender de um ID
# interno fixo, que já ficou desatualizado uma vez (o arquivo foi movido/recriado).
BASE_COLAB_SHARE_URL = (
    "https://rezendeenergia.sharepoint.com/:x:/r/sites/Intranet/_layouts/15/doc2.aspx"
    "?sourcedoc=%7BF01BC0D3-1EF0-4E29-8CCF-61FF00DD2CD8%7D"
    "&file=Base%20de%20Colaboradores%20-%20Rezende%20Energia.xlsx"
    "&action=default"
)

# ID antigo, mantido só como última tentativa (ficou desatualizado em algum
# momento — por isso a leitura por link acima veio antes).
BASE_COLAB_FILE_ID = "5D573B4E-466F-49FA-84C2-CCC533509818"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_cache_colaboradores = {"data": None, "ts": 0}


def _encode_share_url(url: str) -> str:
    """Codifica uma URL de compartilhamento do SharePoint/OneDrive no formato
    que a Graph API espera para resolver o item direto pelo link
    (endpoint /shares/{id}/driveItem)."""
    b64 = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"u!{b64}"


def _resolver_arquivo(headers: dict):
    """Acha o drive_id e o file_id da planilha de colaboradores.

    Tenta primeiro resolver pelo link de compartilhamento (BASE_COLAB_SHARE_URL);
    se não der certo, cai para o método antigo (ID fixo + busca por nome).
    Retorna (drive_id, file_id) ou (None, None) se não achar de jeito nenhum."""

    # 1) Resolve direto pelo link de compartilhamento.
    share_id = _encode_share_url(BASE_COLAB_SHARE_URL)
    r = requests.get(f"{GRAPH_BASE}/shares/{share_id}/driveItem", headers=headers, timeout=10)
    print(f"[COLAB][diag] resolver por link de compartilhamento: status={r.status_code}")
    if r.status_code == 200:
        item = r.json()
        file_id  = item.get("id")
        drive_id = (item.get("parentReference") or {}).get("driveId")
        if file_id and drive_id:
            print(f"[COLAB][diag] resolvido pelo link: drive_id={drive_id!r} file_id={file_id!r}")
            return drive_id, file_id
    else:
        print(f"[COLAB][diag] corpo do erro (link): {r.text[:300]}")

    # 2) Método antigo: site/drive fixos da intranet + ID fixo do arquivo,
    #    com busca pelo nome se o ID fixo não funcionar.
    site_id  = _get_site_id()
    drive_id = _get_drive_id(site_id)
    print(f"[COLAB][diag] site_id={site_id!r} drive_id={drive_id!r}")

    file_id = BASE_COLAB_FILE_ID
    url = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets"
    r = requests.get(url, headers=headers, timeout=10)
    print(f"[COLAB][diag] 1a tentativa (ID fixo {file_id}): status={r.status_code}")
    if r.status_code == 200:
        return drive_id, file_id

    url2 = f"{GRAPH_BASE}/sites/{site_id}/drive/root/search(q='Base de Colaboradores')"
    r2 = requests.get(url2, headers=headers, timeout=10)
    print(f"[COLAB][diag] busca pelo nome: status={r2.status_code}")
    if r2.status_code != 200:
        print(f"[COLAB] Erro ao acessar planilha: {r.status_code}")
        return None, None
    items = r2.json().get("value", [])
    print(f"[COLAB][diag] itens encontrados na busca: {len(items)} -> {[it.get('name') for it in items]}")
    if not items:
        print("[COLAB] Erro: busca pelo nome não encontrou nenhum arquivo")
        return None, None
    return drive_id, items[0]["id"]


def _get_colaboradores_raw() -> list:
    """Busca colaboradores direto do Excel via Graph API."""
    import time
    now = time.time()
    # Cache de 5 minutos
    if _cache_colaboradores["data"] and (now - _cache_colaboradores["ts"]) < 300:
        return _cache_colaboradores["data"]

    try:
        token   = _get_token()
        headers = {"Authorization": f"Bearer {token}"}

        drive_id, file_id = _resolver_arquivo(headers)
        if not drive_id or not file_id:
            print("[COLAB] Erro: não foi possível achar o arquivo da planilha")
            return []

        url = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets"
        r = requests.get(url, headers=headers, timeout=10)
        print(f"[COLAB][diag] lista de abas: status={r.status_code}")
        if r.status_code != 200:
            print(f"[COLAB] Erro ao acessar planilha (fallback): {r.status_code}")
            return []

        sheets = r.json().get("value", [])
        nomes_abas = [s.get("name") for s in sheets]
        print(f"[COLAB][diag] abas encontradas: {nomes_abas}")
        if not sheets:
            print("[COLAB] Erro: planilha não tem nenhuma aba")
            return []

        # A planilha tem várias abas (ex.: "Planilha1" em branco, "PJ",
        # "COLABORADORES DE BENEFICIO INSS" etc.) — a aba com os colaboradores
        # ativos (a que interessa pra CIPA e pra "Mudança de Função") é
        # "COLABORADORES ATIVOS". Procura por ela primeiro (tolerando espaços/
        # acentuação no nome da aba); se não achar, tenta as outras em ordem
        # até achar uma com dados de verdade.
        def _chave_aba(nome):
            return 0 if _normalizar_nome(nome) == "COLABORADORES ATIVOS" else 1
        ordem_abas = sorted(nomes_abas, key=_chave_aba)

        values = []
        sheet_name = None
        for candidata in ordem_abas:
            url_range = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets('{candidata}')/usedRange"
            r2 = requests.get(url_range, headers=headers, timeout=15)
            print(f"[COLAB][diag] usedRange da aba {candidata!r}: status={r2.status_code}")
            if r2.status_code != 200:
                print(f"[COLAB] Erro ao ler range da aba {candidata!r}: {r2.status_code} -- corpo: {r2.text[:300]}")
                continue
            valores_aba = r2.json().get("values", [])
            print(f"[COLAB][diag] linhas lidas na aba {candidata!r} (com cabeçalho): {len(valores_aba)}")
            if len(valores_aba) >= 2:
                sheet_name = candidata
                values = valores_aba
                break

        if len(values) < 2:
            print("[COLAB] Erro: nenhuma aba retornou linhas de dados (só cabeçalho ou vazia)")
            return []

        # Monta lista de colaboradores. Usa o nome da coluna normalizado (sem
        # acento, maiúsculo, sem espaço sobrando) pra não depender de bater
        # exatamente com a acentuação/grafia usada na planilha.
        headers_row = [str(h).strip() for h in values[0]]
        headers_norm = [_normalizar_nome(h) for h in headers_row]
        print(f"[COLAB][diag] cabeçalhos da aba {sheet_name!r}: {headers_row}")
        colaboradores = []
        for row in values[1:]:
            obj = {}
            for i, h in enumerate(headers_norm):
                obj[h] = str(row[i]).strip() if i < len(row) else ""
            # Mapeia campos comuns
            nome  = obj.get("NOME", obj.get("COLABORADOR", obj.get("FUNCIONARIO", obj.get("NOME COMPLETO", ""))))
            cargo = obj.get("CARGO", obj.get("FUNCAO", obj.get("FUNCAO ATUAL", obj.get("CARGO ATUAL", ""))))
            mat   = obj.get("MATRICULA", obj.get("MAT", obj.get("MATR", obj.get("ID", ""))))
            local = obj.get("LOCALIDADE", obj.get("LOCAL", obj.get("CIDADE", obj.get("REGIONAL", ""))))
            if nome:
                colaboradores.append({
                    "nome":       nome,
                    "cargo":      cargo,
                    "matricula":  mat,
                    "localidade": local,
                })

        _cache_colaboradores["data"] = colaboradores
        _cache_colaboradores["ts"]   = now
        print(f"[COLAB] {len(colaboradores)} colaboradores carregados do SharePoint (aba {sheet_name!r})")
        return colaboradores

    except Exception as e:
        print(f"[COLAB] Erro: {type(e).__name__}: {e}")
        return []


def buscar_colaboradores(q: str = "", limit: int = 20) -> list:
    """Busca colaboradores por nome ou cargo."""
    todos = _get_colaboradores_raw()
    if not q:
        return todos[:limit]
    q_lower = q.lower()
    return [
        c for c in todos
        if q_lower in c["nome"].lower() or q_lower in c["cargo"].lower()
    ][:limit]


# ── Validação de colaborador ativo (formulários públicos) ──────

def _normalizar_nome(texto: str) -> str:
    """Remove acentos e espaços extras e deixa em caixa alta, p/ comparar nomes
    com tolerância a diferenças de acentuação/espaçamento na digitação."""
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.upper().split())


def _normalizar_matricula(valor: str) -> str:
    """Remove espaços/traços e zeros à esquerda (quando só números), p/ tolerar
    "0045" vs "45" continuando a exigir que o número seja o mesmo."""
    m = re.sub(r"[^A-Za-z0-9]", "", str(valor or "")).upper()
    if m.isdigit():
        m = m.lstrip("0") or "0"
    return m


def validar_colaborador_ativo(nome: str, matricula: str) -> str:
    """Confere se existe, na Base de Colaboradores do RH, um colaborador ativo
    com esse nome E matrícula (tolerando acento/caixa/espaços/zeros à esquerda).

    Retorna:
      "ok"            — encontrado
      "nao_encontrado"— não existe esse nome+matrícula juntos na planilha
      "indisponivel"  — não foi possível consultar a planilha agora
    """
    todos = _get_colaboradores_raw()
    if not todos:
        return "indisponivel"

    nome_norm = _normalizar_nome(nome)
    mat_norm  = _normalizar_matricula(matricula)
    if not nome_norm or not mat_norm:
        return "nao_encontrado"

    for c in todos:
        if _normalizar_nome(c.get("nome")) == nome_norm and _normalizar_matricula(c.get("matricula")) == mat_norm:
            return "ok"
    return "nao_encontrado"


# Lista fixa de cargos, usada quando a consulta ao SharePoint não estiver
# disponível (a planilha fica instável e os cargos quase não mudam).
# Tirada da base de folha de pagamento em 11/11/2026 — se a empresa criar
# um cargo novo, é só adicionar aqui.
CARGOS_PADRAO = [
    "AJUDANTE DE SERVIÇOS GERAIS",
    "ALMOXARIFE",
    "ALMOXARIFE II",
    "ANALISTA ADMINISTRATIVO",
    "ANALISTA DE DP",
    "ANALISTA DE TI",
    "ANALISTA FINANCEIRO",
    "ANALISTA TECNICO",
    "ASSISTENTE ADMINISTRATIVO I",
    "ASSISTENTE ADMINISTRATIVO II",
    "ASSISTENTE ADMINISTRATIVO III",
    "ASSISTENTE FINANCEIRO",
    "AUXILIAR DE ALMOXARIFADO",
    "AUXILIAR DE LOGISTICA II",
    "COMPRADOR",
    "COORDENADOR OPERACIONAL",
    "COPEIRO (A)",
    "ELETRICISTA",
    "ELETRICISTA CADASTRADOR",
    "ELETRICISTA II",
    "ENCARREGADO OPERACIONAL",
    "FISCAL DE OBRAS",
    "GERENTE OPERACIONAL",
    "GERENTE RH/DP",
    "JOVEM APRENDIZ/ ASSISTENTE LOG",
    "MECÂNICO DE VEÍCULOS AUTOMOTORES",
    "MOTORISTA OPERADOR DE MUNCK",
    "OPERADOR DE MAQUINAS",
    "OPERADOR DE MAQUINAS II",
    "OPERADOR DE MOTOSSERRA",
    "OPERADOR DE MOTOSSERRA II",
    "SUPERVISOR",
    "SUPERVISOR TECNICO EM SEGURANÇA DO TRABALHO",
    "TEC EM SEGURANCA NO TRABALHO",
]


def listar_cargos() -> list:
    """Lista única (ordenada) dos cargos existentes na Base de Colaboradores,
    para preencher listas suspensas em formulários públicos.

    Tenta buscar ao vivo no SharePoint; se não vier nada (planilha fora do
    ar, erro de acesso etc.), usa a lista fixa CARGOS_PADRAO como reserva."""
    todos = _get_colaboradores_raw()
    cargos = {c["cargo"].strip() for c in todos if c.get("cargo") and c["cargo"].strip()}
    if not cargos:
        return list(CARGOS_PADRAO)
    return sorted(cargos, key=_normalizar_nome)
