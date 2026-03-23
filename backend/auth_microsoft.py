"""
Rota de autenticação via Microsoft OAuth2 (Azure AD)
Fluxo: Authorization Code Flow
- GET  /api/auth/microsoft/login    → redireciona para Microsoft
- GET  /api/auth/microsoft/callback → recebe código, troca por token, cria sessão JWT
"""
import os
import requests
from flask import Blueprint, redirect, request, jsonify, url_for
from security import create_token
from database import get_db
import models
import audit

bp_ms = Blueprint("auth_microsoft", __name__)

TENANT_ID     = os.getenv("MS_TENANT_ID", "")
CLIENT_ID     = os.getenv("MS_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")
BASE_URL      = os.getenv("BASE_URL", "https://newrh.onrender.com")

# ── Lista de acesso autorizado ────────────────────────────────
# ROLE_OWNER  → Rafael (aprovação de vagas)
# ROLE_ADMIN  → Gestores de RH (controle total)
# ROLE_VIEWER → Equipe DP/RH (acompanha e move candidatos, sem aprovar vagas)

GESTORES = {
    "leonardo@rezendeenergia.com.br":           "ROLE_ADMIN",
    "gabrielle.lira@rezendeenergia.com.br":     "ROLE_ADMIN",
    "pedrohueb@rezendeenergia.com.br":           "ROLE_ADMIN",
    "pamella.macambira@rezendeenergia.com.br":   "ROLE_ADMIN",
    "bruno@rezendeenergia.com.br":               "ROLE_ADMIN",
    "rafael@rezendeenergia.com.br":              "ROLE_OWNER",
}

EQUIPE_DP_RH = {
    "mariane.froz@rezendeenergia.com.br":     "ROLE_VIEWER",
    "kailany.castanha@rezendeenergia.com.br": "ROLE_VIEWER",
    "andreiaazevedo@rezendeenergia.com.br":   "ROLE_VIEWER",
    "davyd.reis@rezendeenergia.com.br":        "ROLE_VIEWER",
    "ana.tapajos@rezendeenergia.com.br":       "ROLE_VIEWER",
}

EQUIPE_TI = {
    "ti@rezendeenergia.com.br": "ROLE_ADMIN",
}

USUARIOS_AUTORIZADOS = {**GESTORES, **EQUIPE_DP_RH, **EQUIPE_TI}

REDIRECT_URI   = f"{BASE_URL}/api/auth/microsoft/callback"
AUTH_URL       = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
TOKEN_URL      = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_ME_URL   = "https://graph.microsoft.com/v1.0/me"


@bp_ms.get("/login")
def ms_login():
    """Redireciona para o login Microsoft."""
    params = {
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "response_mode": "query",
        "scope":         "openid profile email User.Read",
        "prompt":        "select_account",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(f"{AUTH_URL}?{qs}")


@bp_ms.get("/callback")
def ms_callback():
    """Recebe o código do Microsoft, troca por token, valida domínio e cria sessão."""
    code  = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        desc = request.args.get("error_description", "Acesso negado")
        return redirect(f"/#ms-error={desc.replace(' ', '+')}")

    # Troca código por token
    resp = requests.post(TOKEN_URL, data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }, timeout=15)

    if resp.status_code != 200:
        return redirect("/#ms-error=Falha+ao+obter+token+Microsoft")

    access_token = resp.json().get("access_token")

    # Busca dados do usuário no Graph
    me = requests.get(GRAPH_ME_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if me.status_code != 200:
        return redirect("/#ms-error=Falha+ao+obter+dados+do+usuário")

    me_data     = me.json()
    email       = me_data.get("mail") or me_data.get("userPrincipalName", "")
    display_name = me_data.get("displayName", email.split("@")[0])

    # Valida se o e-mail está na lista autorizada
    email_lower = email.lower()
    if email_lower not in USUARIOS_AUTORIZADOS:
        print(f"[MS_AUTH] Bloqueado: {email_lower} não está na whitelist")
        return redirect("/#ms-error=Acesso+não+autorizado.+Email+não+está+na+lista+de+permissões.+Fale+com+o+TI.")

    role_correto = USUARIOS_AUTORIZADOS[email_lower]

    # Verifica/cria usuário no banco
    db = get_db()
    try:
        username = email_lower.split("@")[0].replace(".", "_")
        user = db.query(models.User).filter(
            (models.User.email == email_lower) | (models.User.username == username)
        ).first()

        if not user:
            from security import hash_password
            import secrets
            user = models.User(
                username=username,
                email=email_lower,
                password_hash=hash_password(secrets.token_hex(32)),
                role=role_correto,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[MS_AUTH] Usuário criado via SSO: {email_lower} ({role_correto})")
        else:
            # Atualiza role se necessário
            if user.role != role_correto:
                user.role = role_correto
                db.commit()

        if not user.is_active:
            return redirect("/#ms-error=Conta+desativada.+Fale+com+o+TI.")

        # Gera JWT interno
        token = create_token(user.username, user.role)
        audit.log(user.username, "LOGIN_MS", detail=f"SSO Microsoft — {email}")

        # Redireciona para o frontend com token na URL (capturado pelo JS)
        return redirect(f"/#ms-token={token}&ms-user={user.username}&ms-role={user.role}&ms-name={display_name}")

    finally:
        db.close()
