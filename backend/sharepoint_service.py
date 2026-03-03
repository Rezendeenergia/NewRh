"""
Serviço de integração com SharePoint via Microsoft Graph API.
Pasta base: Documentos Compartilhados/ADMINISTRAÇÃO/Departamento de Gestão de Pessoas/RH/CANDIDATURAS
"""
import os
import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

load_dotenv()

TENANT_ID     = os.getenv("MS_TENANT_ID")
CLIENT_ID     = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES     = ["https://graph.microsoft.com/.default"]

# Caminho base já existente no SharePoint
BASE_PATH  = "ADMINISTRAÇÃO/Departamento de Gestão de Pessoas/RH/CANDIDATURAS"


def _get_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_silent(SCOPES, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=SCOPES)
    if "access_token" not in result:
        raise Exception(f"Token falhou: {result.get('error_description')}")
    return result["access_token"]


def _headers(json=True):
    h = {"Authorization": f"Bearer {_get_token()}"}
    if json:
        h["Content-Type"] = "application/json"
    return h


def _get_site_id():
    url = f"{GRAPH_BASE}/sites/rezendeenergia.sharepoint.com:/sites/Intranet"
    r   = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["id"]


def _get_drive_id(site_id):
    url    = f"{GRAPH_BASE}/sites/{site_id}/drives"
    r      = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    drives = r.json().get("value", [])
    print(f"[SHAREPOINT] Drives disponíveis: {[d.get('name') for d in drives]}")
    for name in ("Documentos Compartilhados", "Shared Documents", "Documents", "Documentos"):
        for d in drives:
            if d.get("name") == name:
                print(f"[SHAREPOINT] Drive selecionado: {name}")
                return d["id"]
    if drives:
        print(f"[SHAREPOINT] Drive fallback: {drives[0].get('name')}")
        return drives[0]["id"]
    return None


def _criar_pasta(drive_id, caminho_pai_encoded, nome_pasta):
    """Cria uma subpasta. Retorna o item criado ou existente."""
    # Verifica se já existe
    check = f"{GRAPH_BASE}/drives/{drive_id}/root:/{caminho_pai_encoded}/{nome_pasta}"
    r = requests.get(check, headers=_headers(), timeout=10)
    if r.status_code == 200:
        return r.json()

    # Cria
    url  = f"{GRAPH_BASE}/drives/{drive_id}/root:/{caminho_pai_encoded}:/children"
    body = {"name": nome_pasta, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
    r    = requests.post(url, headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def criar_pasta_colaborador(nome: str, cpf: str) -> dict:
    """
    Cria pasta do colaborador dentro de CANDIDATURAS/:
    CANDIDATURAS/
    └── Nome Colaborador - CPF/
            └── (documentos por etapa)

    Retorna {'id': ..., 'url': ..., 'pasta': ...}
    """
    try:
        cpf_clean = cpf.replace(".", "").replace("-", "")
        pasta     = f"{nome} - {cpf_clean}"

        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)

        # Cria a pasta do colaborador dentro de CANDIDATURAS
        item = _criar_pasta(drive_id, BASE_PATH, pasta)

        return {
            "id":    item.get("id"),
            "url":   item.get("webUrl", ""),
            "pasta": pasta,
        }
    except Exception as e:
        print(f"[SHAREPOINT] Erro ao criar pasta: {e}")
        return {"id": None, "url": None, "pasta": None, "erro": str(e)}


def upload_documento(arquivo_path: str, nome_arquivo: str,
                     pasta_colaborador: str, sub_pasta: str = None) -> str:
    """
    Faz upload para:
    CANDIDATURAS/Nome - CPF/[sub_pasta]/nome_arquivo

    Retorna a URL do arquivo no SharePoint.
    """
    try:
        caminho = f"{BASE_PATH}/{pasta_colaborador}"
        if sub_pasta:
            # Garante que a sub-pasta da etapa existe
            site_id  = _get_site_id()
            drive_id = _get_drive_id(site_id)
            _criar_pasta(drive_id, caminho, sub_pasta)
            caminho  = f"{caminho}/{sub_pasta}"

        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)

        with open(arquivo_path, "rb") as f:
            content = f.read()

        upload_url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{caminho}/{nome_arquivo}:/content"
        headers    = {
            "Authorization": f"Bearer {_get_token()}",
            "Content-Type":  "application/octet-stream",
        }
        r = requests.put(upload_url, headers=headers, data=content, timeout=30)
        r.raise_for_status()
        return r.json().get("webUrl", "")

    except Exception as e:
        print(f"[SHAREPOINT] Erro no upload: {e}")
        return None


def criar_subpasta_etapa(pasta_colaborador: str, etapa_nome: str) -> str:
    """Garante que a subpasta da etapa existe. Retorna URL."""
    try:
        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)
        caminho  = f"{BASE_PATH}/{pasta_colaborador}"
        item     = _criar_pasta(drive_id, caminho, etapa_nome)
        return item.get("webUrl", "")
    except Exception as e:
        print(f"[SHAREPOINT] Erro subpasta etapa: {e}")
        return None
