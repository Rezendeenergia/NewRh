"""
Serviço para buscar colaboradores da Base de Colaboradores.xlsx no SharePoint.
"""
import os, requests
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

        # Busca o arquivo pelo ID
        url = f"{GRAPH_BASE}/drives/{drive_id}/items/{BASE_COLAB_FILE_ID}/workbook/worksheets"
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            # Tenta buscar pelo nome
            url2 = f"{GRAPH_BASE}/sites/{site_id}/drive/root/search(q='Base de Colaboradores')"
            r2 = requests.get(url2, headers=headers, timeout=10)
            if r2.status_code != 200:
                print(f"[COLAB] Erro ao acessar planilha: {r.status_code}")
                return []
            items = r2.json().get("value", [])
            if not items:
                return []
            file_id = items[0]["id"]
            url = f"{GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/worksheets"
            r = requests.get(url, headers=headers, timeout=10)

        sheets = r.json().get("value", [])
        if not sheets:
            return []

        # Usa a primeira aba
        sheet_name = sheets[0]["name"]
        url_range = f"{GRAPH_BASE}/drives/{drive_id}/items/{BASE_COLAB_FILE_ID}/workbook/worksheets('{sheet_name}')/usedRange"
        r2 = requests.get(url_range, headers=headers, timeout=15)
        if r2.status_code != 200:
            print(f"[COLAB] Erro ao ler range: {r2.status_code}")
            return []

        data = r2.json()
        values = data.get("values", [])
        if len(values) < 2:
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
        print(f"[COLAB] Erro: {e}")
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
