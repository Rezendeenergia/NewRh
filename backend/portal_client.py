"""
Acesso ao painel de gestão (ROLE_OWNER/ROLE_ADMIN/ROLE_VIEWER) decidido pelo
Portal Rezende, setor RH. Consultado a cada login via
GET {PORTAL_URL}/api/integracao/acesso?sistema=newrh&email=...
Cache curto + tolerância se o portal cair (usa a última resposta boa).

Não cobre os GESTORES_CAMPO (ROLE_GESTOR) em auth_microsoft.py: eles não
são da equipe de RH, só podem pedir abertura de vaga, e continuam numa
lista própria, fora do portal.
"""
import os
import time
import requests

CHAVE_SISTEMA = "newrh"
CACHE_SEGUNDOS = 60
TOLERANCIA_SEGUNDOS = 15 * 60

_cache: dict[str, tuple[dict, float]] = {}  # email -> (resultado, buscado_em)


def _configurado() -> bool:
    return bool(os.getenv("PORTAL_URL")) and len(os.getenv("PORTAL_INTEGRACAO_TOKEN", "")) >= 32


def _consultar_portal(email: str) -> dict:
    base = os.getenv("PORTAL_URL", "").rstrip("/")
    resp = requests.get(
        f"{base}/api/integracao/acesso",
        params={"sistema": CHAVE_SISTEMA, "email": email},
        headers={"Authorization": f"Bearer {os.getenv('PORTAL_INTEGRACAO_TOKEN')}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def verificar_acesso(email: str) -> dict:
    """Retorna {"permitido": bool, "nivel": str|None, "nome": str|None, "motivo": str|None}."""
    chave = (email or "").strip().lower()
    if not chave:
        return {"permitido": False, "nivel": None, "nome": None, "motivo": "email_vazio"}

    if not _configurado():
        print("[portal] PORTAL_URL/PORTAL_INTEGRACAO_TOKEN não configurados — acesso negado por segurança.")
        return {"permitido": False, "nivel": None, "nome": None, "motivo": "integracao_nao_configurada"}

    agora = time.time()
    em_cache = _cache.get(chave)
    if em_cache and agora - em_cache[1] < CACHE_SEGUNDOS:
        return em_cache[0]

    try:
        r = _consultar_portal(chave)
        if r.get("permitido"):
            resultado = {"permitido": True, "nivel": r.get("nivel"), "nome": r.get("nome"), "motivo": None}
        else:
            resultado = {"permitido": False, "nivel": None, "nome": None, "motivo": r.get("motivo") or "sem_acesso"}
        _cache[chave] = (resultado, agora)
        return resultado
    except Exception as e:
        if em_cache and agora - em_cache[1] < TOLERANCIA_SEGUNDOS:
            print(f"[portal] indisponível, usando cache de {int(agora - em_cache[1])}s para {chave}: {e}")
            return em_cache[0]
        print(f"[portal] indisponível e sem cache utilizável para {chave}: {e}")
        return {"permitido": False, "nivel": None, "nome": None, "motivo": "portal_indisponivel"}
