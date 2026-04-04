"""
Portal do Candidato — Autenticação por e-mail e senha.
- Primeiro acesso: cadastra senha via e-mail
- Login: e-mail + senha
- Recuperação de senha via e-mail
"""
import os, secrets, hashlib
import jwt
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from database import get_db
import models

bp_cand = Blueprint("candidato_auth", __name__)

SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
BASE_URL    = os.getenv("BASE_URL", "https://newrh.onrender.com")


# ── JWT ────────────────────────────────────────────────────────

def _create_token(email: str) -> str:
    return jwt.encode({
        "sub":  email,
        "type": "candidato",
        "exp":  datetime.now(timezone.utc) + timedelta(hours=24),
    }, SECRET_KEY, algorithm="HS256")


def _decode_token(token: str):
    try:
        p = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return p if p.get("type") == "candidato" else None
    except Exception:
        return None


def require_candidato(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"message": "Token não fornecido"}), 401
        payload = _decode_token(auth[7:])
        if not payload:
            return jsonify({"message": "Token inválido ou expirado"}), 401
        request.candidato_email = payload["sub"]
        return f(*args, **kwargs)
    return decorated


# ── Helpers ────────────────────────────────────────────────────

def _hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _get_conta(db, email: str):
    """Busca conta do candidato pelo e-mail."""
    return db.query(models.CandidatoConta).filter_by(email=email.lower()).first()


def _get_candidaturas(db, email: str):
    return db.query(models.Candidatura).filter(
        models.Candidatura.email.ilike(email)
    ).order_by(models.Candidatura.applied_at.desc()).all()


# ── Rotas ──────────────────────────────────────────────────────

@bp_cand.post("/login")
def login():
    """Login com e-mail + senha."""
    data  = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    senha = (data.get("senha") or "").strip()

    if not email or not senha:
        return jsonify({"message": "E-mail e senha são obrigatórios"}), 400

    db = get_db()
    try:
        conta = _get_conta(db, email)

        if not conta:
            # Verifica se existe candidatura com esse e-mail
            cands = _get_candidaturas(db, email)
            if not cands:
                return jsonify({"message": "E-mail não encontrado. Verifique se este é o e-mail que usou na candidatura."}), 404
            return jsonify({
                "message": "Você ainda não criou uma senha. Verifique seu e-mail ou clique em 'Primeiro Acesso'.",
                "primeiroAcesso": True,
            }), 401

        if not conta.senha_hash:
            return jsonify({
                "message": "Senha não definida. Clique em 'Primeiro Acesso' para criar sua senha.",
                "primeiroAcesso": True,
            }), 401

        if conta.senha_hash != _hash_senha(senha):
            return jsonify({"message": "Senha incorreta."}), 401

        # Atualiza último acesso
        conta.ultimo_acesso = datetime.now()
        db.commit()

        cands = _get_candidaturas(db, email)
        nome  = cands[0].full_name.split()[0] if cands else email.split("@")[0]

        return jsonify({
            "token": _create_token(email),
            "nome":  nome,
        })
    finally:
        db.close()


@bp_cand.post("/primeiro-acesso")
def primeiro_acesso():
    """Envia e-mail com link para criar senha (primeiro acesso)."""
    data  = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"message": "E-mail obrigatório"}), 400

    db = get_db()
    try:
        # Verifica se existe candidatura com esse e-mail
        cands = _get_candidaturas(db, email)
        if not cands:
            return jsonify({"message": "E-mail não encontrado. Use o mesmo e-mail informado na candidatura."}), 404

        # Cria ou atualiza conta
        conta = _get_conta(db, email)
        if not conta:
            conta = models.CandidatoConta(email=email)
            db.add(conta)

        # Gera token de definição de senha (válido 2h)
        token = secrets.token_urlsafe(32)
        conta.reset_token    = token
        conta.reset_expiry   = datetime.now() + timedelta(hours=2)  # naive, sem timezone
        db.commit()

        # Envia e-mail
        link = f"{BASE_URL}/candidato/definir-senha?token={token}"
        nome = cands[0].full_name.split()[0]
        try:
            from email_service import send_email, _base_template, BRAND_COLOR
            subject = "🔑 Crie sua senha — Portal de Carreiras Rezende Energia"
            content = (
                f'<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">Olá, {nome}! 👋</h2>'
                f'<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);font-weight:600;text-transform:uppercase;letter-spacing:2px;">Crie sua senha de acesso</p>'
                f'<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 24px;">'
                f'Clique no botão abaixo para criar sua senha e acessar o Portal de Carreiras da Rezende Energia. '
                f'O link é válido por <strong style="color:#fff;">2 horas</strong>.</p>'
                f'<div style="text-align:center;margin:0 0 24px;">'
                f'<a href="{link}" style="display:inline-block;background:linear-gradient(135deg,#FF8C2A,#FF6A00);'
                f'color:#000;font-weight:800;font-size:15px;text-decoration:none;'
                f'padding:14px 36px;border-radius:10px;">🔑 Criar Minha Senha</a></div>'
                f'<p style="color:#5A6478;font-size:12px;text-align:center;margin:0;">'
                f'Se não solicitou isso, ignore este e-mail.</p>'
            )
            send_email(email, subject, _base_template(subject, content))
            print(f"[CANDIDATO] E-mail de definição de senha enviado para {email}")
        except Exception as ex:
            print(f"[CANDIDATO] Falha ao enviar e-mail: {ex}")

        return jsonify({"message": "E-mail enviado! Verifique sua caixa de entrada."})
    finally:
        db.close()


@bp_cand.post("/definir-senha")
def definir_senha():
    """Define a senha usando o token recebido por e-mail."""
    data  = request.get_json(force=True)
    token = (data.get("token") or "").strip()
    senha = (data.get("senha") or "").strip()

    if not token or not senha:
        return jsonify({"message": "Token e senha são obrigatórios"}), 400
    if len(senha) < 6:
        return jsonify({"message": "A senha deve ter pelo menos 6 caracteres"}), 400

    db = get_db()
    try:
        conta = db.query(models.CandidatoConta).filter_by(reset_token=token).first()
        if not conta:
            return jsonify({"message": "Link inválido."}), 400
        if conta.reset_expiry and conta.reset_expiry.replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None):
            return jsonify({"message": "Link expirado. Solicite um novo."}), 400

        conta.senha_hash   = _hash_senha(senha)
        conta.reset_token  = None
        conta.reset_expiry = None
        conta.ultimo_acesso = datetime.now()
        db.commit()

        cands = _get_candidaturas(db, conta.email)
        nome  = cands[0].full_name.split()[0] if cands else "candidato"

        return jsonify({
            "message": "Senha criada com sucesso!",
            "token":   _create_token(conta.email),
            "nome":    nome,
        })
    finally:
        db.close()


@bp_cand.post("/recuperar-senha")
def recuperar_senha():
    """Reenvia link para redefinir senha."""
    return primeiro_acesso()  # mesma lógica


@bp_cand.get("/minhas-candidaturas")
@require_candidato
def minhas_candidaturas():
    email = request.candidato_email
    db    = get_db()
    try:
        STATUS_PT = {
            "PENDING":         "Em Análise",
            "TRIAGEM":         "Triagem",
            "TRIAGEM_OK":      "Triagem Aprovada",
            "ENTREVISTA":      "Entrevista",
            "ENTREVISTA_OK":   "Entrevista Aprovada",
            "APROVACAO_FINAL": "Aprovação Final",
            "APPROVED":        "Aprovado ✅",
            "REJECTED":        "Não Selecionado",
        }

        cands = _get_candidaturas(db, email)
        result = []
        for c in cands:
            job   = db.query(models.Job).filter_by(id=c.job_id).first()
            etapa = c.funnel_stage or c.status
            result.append({
                "id":        c.id,
                "vaga":      job.position if job else "—",
                "local":     job.location if job else "—",
                "status":    STATUS_PT.get(etapa, etapa),
                "statusKey": etapa,
                "appliedAt": c.applied_at.strftime("%d/%m/%Y") if c.applied_at else "—",
                "nome":      c.full_name,
            })
        return jsonify(result)
    finally:
        db.close()


@bp_cand.get("/meu-perfil")
@require_candidato
def meu_perfil():
    email = request.candidato_email
    db    = get_db()
    try:
        c = _get_candidaturas(db, email)
        if not c:
            return jsonify({"message": "Candidato não encontrado"}), 404
        c = c[0]
        return jsonify({
            "nome":        c.full_name,
            "email":       c.email,
            "telefone":    c.phone,
            "cidadeAtual": c.cidade_atual,
            "formacao":    c.education,
        })
    finally:
        db.close()
