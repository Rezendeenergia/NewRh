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


# ── Estrutura oficial da pasta digital do colaborador ─────────
ESTRUTURA_PASTA = {
    "01 DOCUMENTO PESSOAL": {
        "1.1 PESSOAL": None,
        "1.2 DEPENDENTES": None,
        "1.3 DADOS BANCARIOS E PIX": None,
    },
    "02 ADMISSAO": {
        "2.1 DOCUMENTO ASSINADO": None,
        "2.2 DOCUMENTO DA CONTABILIDADE": None,
        "2.3 AVALIACAO": None,
    },
    "03 SAUDE OCUPACIONAL": None,
    "04 MOBILIZACAO": {
        "4.1 TREINAMENTOS": None,
        "4.2 EPI E CAUTELAS": None,
        "4.3 OCORRENCIAS": None,
    },
    "05 TRABALHISTA E FINANCEIRO": {
        "5.1 CARTAO PONTO DIGITAL": None,
        "5.2 HOLERITES CONTRA CHEQUE": None,
        "5.3 COMPROVANTES DE PAGAMENTO": None,
        "5.4 FERIAS": None,
    },
    "06 MEDIDAS DISCIPLINAR": None,
}


def _criar_estrutura_recursiva(drive_id: str, caminho_base: str, estrutura: dict):
    """Cria recursivamente todas as subpastas da estrutura."""
    for nome_pasta, subpastas in estrutura.items():
        try:
            _criar_pasta(drive_id, caminho_base, nome_pasta)
            print(f"[SHAREPOINT] Pasta criada: {caminho_base}/{nome_pasta}")
            if subpastas:
                _criar_estrutura_recursiva(
                    drive_id,
                    f"{caminho_base}/{nome_pasta}",
                    subpastas
                )
        except Exception as e:
            print(f"[SHAREPOINT] Erro ao criar {nome_pasta}: {e}")


def criar_pasta_colaborador(nome: str, cpf: str) -> dict:
    """
    Cria pasta do colaborador com estrutura oficial completa:
    CANDIDATURAS/
    └── Nome - CPF/
        ├── 01.DOCUMENTOS PESSOAIS/
        │   ├── 01_PESSOAL/
        │   ├── 02_DEPENDENTES/
        │   └── 03_DADOS_BANCARIOS_E_PIX/
        ├── 02.ADMISSAO/
        │   ├── 01_DOCUMENTO DA CONTABILIDADE/
        │   ├── 02_DOCUMENTOS ASSINADOS/
        │   ├── 03_SAUDE_OCUPACIONAL/
        │   └── 04_MOBILIZACAO/
        │       ├── 01_TREINAMENTOS/
        │       ├── 03_EPI_E_CAUTELAS/
        │       └── 04_OCORRENCIAS/
        ├── 05_TRABALHISTA_FINANCEIRO/
        └── 06_DISCIPLINAR/
    """
    try:
        cpf_clean = cpf.replace(".", "").replace("-", "")
        pasta     = f"{nome} - {cpf_clean}"

        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)

        # 1. Cria pasta raiz do colaborador
        item = _criar_pasta(drive_id, BASE_PATH, pasta)
        url  = item.get("webUrl", "")
        print(f"[SHAREPOINT] Pasta raiz criada: {pasta}")

        # 2. Cria estrutura completa em background para não bloquear
        import threading
        def _build_structure():
            try:
                caminho_colab = f"{BASE_PATH}/{pasta}"
                _criar_estrutura_recursiva(drive_id, caminho_colab, ESTRUTURA_PASTA)
                print(f"[SHAREPOINT] Estrutura completa criada para: {pasta}")
            except Exception as ex:
                print(f"[SHAREPOINT] Erro na estrutura: {ex}")

        threading.Thread(target=_build_structure, daemon=True).start()

        return {
            "id":    item.get("id"),
            "url":   url,
            "pasta": pasta,
        }
    except Exception as e:
        print(f"[SHAREPOINT] Erro ao criar pasta: {e}")
        return {"id": None, "url": None, "pasta": None, "erro": str(e)}


# Mapeamento: código da etapa → pasta oficial no SharePoint
ETAPA_PARA_PASTA = {
    # Fase 1 — Seleção (sem arquivo)
    "TRIAGEM":              None,
    "ENTREVISTA":           None,
    "APROVACAO_FINAL":      None,
    # Fase 2 — Admissão formal
    "ASO":                  "03 SAUDE OCUPACIONAL",
    "DP_EXTERNO":           "02 ADMISSAO/2.2 DOCUMENTO DA CONTABILIDADE",
    "ASSINATURAS":          "02 ADMISSAO/2.1 DOCUMENTO ASSINADO",
    "CADASTRO_GPM":         "02 ADMISSAO/2.3 AVALIACAO",
    "ACESSO_TI":            "02 ADMISSAO/2.3 AVALIACAO",
    "BEMHOEFT":             "02 ADMISSAO/2.2 DOCUMENTO DA CONTABILIDADE",
    # Fase 3 — Segurança / SESMT
    "EPIS_UNIFORMES":       "04 MOBILIZACAO/4.2 EPI E CAUTELAS",
    "FORMACAO_NRS":         "04 MOBILIZACAO/4.1 TREINAMENTOS",
    "PRONTUARIO_SEGURANCA": "04 MOBILIZACAO/4.1 TREINAMENTOS",
    "CERTIFICADOS_NR":      "04 MOBILIZACAO/4.1 TREINAMENTOS",
    "PROVA_DEEP":           "04 MOBILIZACAO/4.1 TREINAMENTOS",
    # Fase 4 — Integração final
    "GRAFICA_CRACHA":       "02 ADMISSAO/2.3 AVALIACAO",
    "INTEGRACAO_EQUATORIAL":"02 ADMISSAO/2.3 AVALIACAO",
    "LIBERADO_CAMPO":       "02 ADMISSAO/2.3 AVALIACAO",
}


def _pasta_para_etapa(codigo_etapa: str) -> str | None:
    """Retorna o caminho relativo da pasta para o código da etapa."""
    return ETAPA_PARA_PASTA.get(codigo_etapa.upper())


def upload_documento(arquivo_path: str, nome_arquivo: str,
                     pasta_colaborador: str,
                     sub_pasta: str = None,
                     codigo_etapa: str = None) -> str:
    """
    Faz upload para a pasta correta baseado no código da etapa.
    Se codigo_etapa for fornecido, usa o mapeamento oficial.
    Caso contrário, usa sub_pasta como fallback.
    """
    try:
        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)
        caminho_base = f"{BASE_PATH}/{pasta_colaborador}"

        # Determina pasta destino
        pasta_destino = None
        if codigo_etapa:
            pasta_destino = _pasta_para_etapa(codigo_etapa)

        if pasta_destino:
            # Garante que toda a hierarquia existe
            partes = pasta_destino.split("/")
            caminho_atual = caminho_base
            for parte in partes:
                _criar_pasta(drive_id, caminho_atual, parte)
                caminho_atual = f"{caminho_atual}/{parte}"
            caminho_final = caminho_atual
        elif sub_pasta:
            _criar_pasta(drive_id, caminho_base, sub_pasta)
            caminho_final = f"{caminho_base}/{sub_pasta}"
        else:
            caminho_final = caminho_base

        with open(arquivo_path, "rb") as f:
            file_content = f.read()

        upload_url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{caminho_final}/{nome_arquivo}:/content"
        headers    = {
            "Authorization": f"Bearer {_get_token()}",
            "Content-Type":  "application/octet-stream",
        }
        r = requests.put(upload_url, headers=headers, data=file_content, timeout=30)
        r.raise_for_status()
        url = r.json().get("webUrl", "")
        print(f"[SHAREPOINT] Upload OK → {caminho_final}/{nome_arquivo}")
        return url

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
