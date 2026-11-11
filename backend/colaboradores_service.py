"""
Serviço para buscar colaboradores da Base de Colaboradores.xlsx no SharePoint.
"""
import os, re, unicodedata, requests
from sharepoint_service import _get_token, _get_site_id, _get_drive_id

# ID do arquivo Base de Colaboradores - extraído da URL fornecida
BASE_COLAB_FILE_ID = "5D573B4E-466F-49FA-84C2-CCC533509818"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_cache_colaboradores = {"data": None, "ts": 0}


def _get_colaboradores_raw() -> list:
    """Busca colaboradores direto do Excel via Graph API."""
    import time
    now = time.time()
    # Cache de 5 minutos
    if _cache_colaboradores["data"] and (now - _cache_colaboradores["ts"]) < 300:
        return _cache_colaboradores["data"]

    try:
        token    = _get_token()
        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)
        headers  = {"Authorization": f"Bearer {token}"}

        print(f"[COLAB][diag] site_id={site_id!r} drive_id={drive_id!r}")

        # Busca o arquivo pelo ID fixo
        file_id = BASE_COLAB_FILE_ID
        url = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets"
        r = requests.get(url, headers=headers, timeout=10)
        print(f"[COLAB][diag] 1a tentativa (ID fixo {file_id}): status={r.status_code}")

        if r.status_code != 200:
            # ID fixo pode ter ficado desatualizado (arquivo movido/recriado
            # no SharePoint) — tenta achar o arquivo atual pelo nome.
            url2 = f"{GRAPH_BASE}/sites/{site_id}/drive/root/search(q='Base de Colaboradores')"
            r2 = requests.get(url2, headers=headers, timeout=10)
            print(f"[COLAB][diag] busca pelo nome: status={r2.status_code}")
            if r2.status_code != 200:
                print(f"[COLAB] Erro ao acessar planilha: {r.status_code}")
                return []
            items = r2.json().get("value", [])
            print(f"[COLAB][diag] itens encontrados na busca: {len(items)} -> {[it.get('name') for it in items]}")
            if not items:
                print("[COLAB] Erro: busca pelo nome não encontrou nenhum arquivo")
                return []
            file_id = items[0]["id"]
            url = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets"
            r = requests.get(url, headers=headers, timeout=10)
            print(f"[COLAB][diag] 2a tentativa (ID do fallback {file_id}): status={r.status_code}")
            if r.status_code != 200:
                print(f"[COLAB] Erro ao acessar planilha (fallback): {r.status_code}")
                return []

        sheets = r.json().get("value", [])
        print(f"[COLAB][diag] abas encontradas: {[s.get('name') for s in sheets]}")
        if not sheets:
            print("[COLAB] Erro: planilha não tem nenhuma aba")
            return []

        # Usa a primeira aba — mesmo file_id resolvido acima (fixo ou do fallback)
        sheet_name = sheets[0]["name"]
        url_range = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets('{sheet_name}')/usedRange"
        r2 = requests.get(url_range, headers=headers, timeout=15)
        print(f"[COLAB][diag] usedRange da aba {sheet_name!r}: status={r2.status_code}")
        if r2.status_code != 200:
            print(f"[COLAB] Erro ao ler range: {r2.status_code} -- corpo: {r2.text[:300]}")
            return []

        data = r2.json()
        values = data.get("values", [])
        print(f"[COLAB][diag] linhas lidas (com cabeçalho): {len(values)}")
        if len(values) < 2:
            print("[COLAB] Erro: planilha retornou sem linhas de dados (só cabeçalho ou vazia)")
            return []

        # Monta lista de colaboradores
        headers_row = [str(h).strip().upper() for h in values[0]]
        colaboradores = []
        for row in values[1:]:
            obj = {}
            for i, h in enumerate(headers_row):
                obj[h] = str(row[i]).strip() if i < len(row) else ""
            # Mapeia campos comuns
            nome  = obj.get("NOME", obj.get("COLABORADOR", obj.get("FUNCIONÁRIO", "")))
            cargo = obj.get("CARGO", obj.get("FUNÇÃO", obj.get("FUNÇÃO ATUAL", "")))
            mat   = obj.get("MATRÍCULA", obj.get("MAT", obj.get("ID", "")))
            local = obj.get("LOCALIDADE", obj.get("LOCAL", obj.get("CIDADE", "")))
            if nome:
                colaboradores.append({
                    "nome":       nome,
                    "cargo":      cargo,
                    "matricula":  mat,
                    "localidade": local,
                })

        _cache_colaboradores["data"] = colaboradores
        _cache_colaboradores["ts"]   = now
        print(f"[COLAB] {len(colaboradores)} colaboradores carregados do SharePoint")
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
