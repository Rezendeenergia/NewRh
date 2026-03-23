import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from database import get_db
from security import hash_password, verify_password, create_token, require_auth
import models
import audit

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

CORPORATE_DOMAIN = "rezendeenergia.com.br"


@bp.post("/login")
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"message": "Usuário e senha obrigatórios"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(username=data["username"]).first()
        if not user or not verify_password(data["password"], user.password or ""):
            audit.log(data["username"], "LOGIN_FAILED", detail="Senha incorreta")
            return jsonify({"message": "Usuário ou senha incorretos"}), 401

        if not user.is_active:
            return jsonify({"message": "Conta não ativada. Verifique seu e-mail corporativo."}), 403

        audit.log(user.username, audit.LOGIN, entity="user", entity_id=user.id,
                  detail=f"Login bem-sucedido")
        return jsonify({
            "token":    create_token(user.username, user.role),
            "username": user.username,
            "role":     user.role,
        })
    finally:
        db.close()


@bp.post("/invite")
@require_admin
def invite():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    email    = (data.get("email")    or "").strip().lower()

    if not username or not email:
        return jsonify({"message": "Username e e-mail obrigatórios"}), 400

    if not email.endswith(f"@{CORPORATE_DOMAIN}"):
        return jsonify({"message": f"Apenas e-mails @{CORPORATE_DOMAIN} são permitidos."}), 400

    db = get_db()
    try:
        if db.query(models.User).filter_by(username=username).first():
            return jsonify({"message": f"Usuário '{username}' já existe"}), 409
        if db.query(models.User).filter_by(email=email).first():
            return jsonify({"message": f"E-mail '{email}' já cadastrado"}), 409

        token   = secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc) + timedelta(hours=24)

        user = models.User(
            username=username, email=email, password=None,
            role=data.get("role", "ROLE_ADMIN"), is_active=False,
            invite_token=token, invite_expires=expires,
        )
        db.add(user)
        db.commit()

        audit.log(request.username, audit.INVITE_USER, entity="user",
                  detail=f"Convite enviado para {email} ({username})")

        base_url = request.host_url.rstrip("/")
        from email_service import notify_invite
        notify_invite(username, email, token, base_url)

        return jsonify({"message": f"Convite enviado para {email}", "username": username}), 201
    finally:
        db.close()


@bp.get("/invite/verify")
def verify_invite():
    token = request.args.get("token", "")
    if not token:
        return jsonify({"valid": False, "message": "Token não informado"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(invite_token=token).first()
        if not user:
            return jsonify({"valid": False, "message": "Link inválido"}), 404
        if user.invite_expires and datetime.now(timezone.utc) > user.invite_expires.replace(tzinfo=timezone.utc):
            return jsonify({"valid": False, "message": "Link expirado. Solicite um novo convite."}), 410
        if user.is_active:
            return jsonify({"valid": False, "message": "Conta já ativada. Faça login."}), 409
        return jsonify({"valid": True, "username": user.username, "email": user.email})
    finally:
        db.close()


@bp.post("/invite/activate")
def activate():
    data  = request.get_json()
    token = (data.get("token")    or "").strip()
    pwd   = (data.get("password") or "").strip()

    if not token or not pwd:
        return jsonify({"message": "Token e senha obrigatórios"}), 400
    if len(pwd) < 6:
        return jsonify({"message": "Senha deve ter ao menos 6 caracteres"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(invite_token=token).first()
        if not user:
            return jsonify({"message": "Link inválido"}), 404
        if user.invite_expires and datetime.now(timezone.utc) > user.invite_expires.replace(tzinfo=timezone.utc):
            return jsonify({"message": "Link expirado. Solicite um novo convite."}), 410
        if user.is_active:
            return jsonify({"message": "Conta já ativada. Faça login."}), 409

        user.password = hash_password(pwd)
        user.is_active = True
        user.invite_token = None
        user.invite_expires = None
        db.commit()

        audit.log(user.username, audit.ACTIVATE_USER, entity="user",
                  entity_id=user.id, detail="Conta ativada via convite")
        return jsonify({"message": "Senha definida com sucesso! Você já pode fazer login."})
    finally:
        db.close()


@bp.post("/invite/resend")
@require_auth
def resend_invite():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"message": "Username obrigatório"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            return jsonify({"message": "Usuário não encontrado"}), 404
        if user.is_active:
            return jsonify({"message": "Conta já ativada"}), 409

        token   = secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        user.invite_token   = token
        user.invite_expires = expires
        db.commit()

        base_url = request.host_url.rstrip("/")
        from email_service import notify_invite
        notify_invite(user.username, user.email, token, base_url)
        return jsonify({"message": f"Convite reenviado para {user.email}"})
    finally:
        db.close()


@bp.post("/forgot-password")
def forgot_password():
    data  = request.get_json()
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"message": "E-mail obrigatório"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(email=email, is_active=True).first()
        if user:
            token   = secrets.token_urlsafe(48)
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            user.reset_token   = token
            user.reset_expires = expires
            db.commit()

            base_url = request.host_url.rstrip("/")
            from email_service import notify_password_reset
            notify_password_reset(user.username, user.email, token, base_url)
            audit.log(user.username, "FORGOT_PASSWORD", entity="user",
                      entity_id=user.id, detail="Solicitação de redefinição de senha")

        return jsonify({"message": "Se o e-mail estiver cadastrado, você receberá as instruções."})
    finally:
        db.close()


@bp.get("/reset/verify")
def verify_reset():
    token = request.args.get("token", "")
    if not token:
        return jsonify({"valid": False, "message": "Token não informado"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(reset_token=token).first()
        if not user:
            return jsonify({"valid": False, "message": "Link inválido"}), 404
        if user.reset_expires and datetime.now(timezone.utc) > user.reset_expires.replace(tzinfo=timezone.utc):
            return jsonify({"valid": False, "message": "Link expirado. Solicite um novo."}), 410
        return jsonify({"valid": True, "username": user.username})
    finally:
        db.close()


@bp.post("/reset/confirm")
def reset_confirm():
    data  = request.get_json()
    token = (data.get("token")    or "").strip()
    pwd   = (data.get("password") or "").strip()

    if not token or not pwd:
        return jsonify({"message": "Token e senha obrigatórios"}), 400
    if len(pwd) < 6:
        return jsonify({"message": "Senha deve ter ao menos 6 caracteres"}), 400

    db = get_db()
    try:
        user = db.query(models.User).filter_by(reset_token=token).first()
        if not user:
            return jsonify({"message": "Link inválido"}), 404
        if user.reset_expires and datetime.now(timezone.utc) > user.reset_expires.replace(tzinfo=timezone.utc):
            return jsonify({"message": "Link expirado. Solicite um novo."}), 410

        user.password      = hash_password(pwd)
        user.reset_token   = None
        user.reset_expires = None
        db.commit()

        audit.log(user.username, audit.RESET_PASSWORD, entity="user",
                  entity_id=user.id, detail="Senha redefinida via e-mail")
        return jsonify({"message": "Senha redefinida com sucesso! Você já pode fazer login."})
    finally:
        db.close()


@bp.get("/audit")
@require_auth
def get_audit():
    """Retorna o log de auditoria para o painel do gestor."""
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 50
    action_f = request.args.get("action", "").strip()
    user_f   = request.args.get("username", "").strip()

    db = get_db()
    try:
        q = db.query(models.AuditLog)
        if action_f:
            q = q.filter(models.AuditLog.action == action_f)
        if user_f:
            q = q.filter(models.AuditLog.username.ilike(f"%{user_f}%"))

        total = q.count()
        rows  = q.order_by(models.AuditLog.created_at.desc()) \
                 .offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "items": [{
                "id":        r.id,
                "username":  r.username,
                "action":    r.action,
                "entity":    r.entity,
                "entityId":  r.entity_id,
                "detail":    r.detail,
                "ip":        r.ip,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            } for r in rows],
            "total":      total,
            "page":       page,
            "totalPages": max(1, -(-total // per_page)),
        })
    finally:
        db.close()


@bp.get("/test-email")
@require_auth
def test_email():
    from email_service import send_email, EMAIL_ENABLED
    test_to = request.args.get("to")
    if not test_to:
        return jsonify({"message": "Parâmetro ?to=email obrigatório"}), 400

    subject = "✅ Teste de E-mail — Rezende Energia"
    html = """<div style="font-family:Arial;background:#0B0F14;color:#fff;padding:40px;border-radius:12px;">
        <h2 style="color:#FF6A00;">⚡ E-mail de Teste</h2>
        <p>Se você recebeu este e-mail, as configurações SMTP estão funcionando!</p>
    </div>"""

    if not EMAIL_ENABLED:
        return jsonify({"message": "EMAIL_ENABLED=false — ative no .env para testar.", "enabled": False})

    ok = send_email(test_to, subject, html)
    if ok:
        return jsonify({"message": f"E-mail enviado para {test_to}!", "enabled": True})
    return jsonify({"message": "Falha. Verifique as credenciais.", "enabled": True}), 500
