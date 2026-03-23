"""
Portal do Candidato — Autenticação e consulta de candidaturas
Login: CPF + data de nascimento
"""
import os
import jwt
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from database import get_db
import models

bp_cand = Blueprint("candidato_auth", __name__)

SECRET_KEY = os.getenv("SECRET_KEY", "changeme")


def _create_candidato_token(cpf: str) -> str:
    payload = {
        "sub":  cpf,
        "type": "candidato",
        "exp":  datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode_candidato_token(token: str):
    try:
        p = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if p.get("type") != "candidato":
            return None
        return p
    except Exception:
        return None


def require_candidato(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"message": "Token não fornecido"}), 401
        payload = _decode_candidato_token(auth[7:])
        if not payload:
            return jsonify({"message": "Token inválido ou expirado"}), 401
        request.candidato_cpf = payload["sub"]
        return f(*args, **kwargs)
    return decorated


@bp_cand.post("/login")
def candidato_login():
    """Login do candidato via CPF + data de nascimento."""
    data            = request.get_json(force=True)
    cpf             = (data.get("cpf") or "").strip()
    data_nascimento = (data.get("dataNascimento") or "").strip()

    if not cpf or not data_nascimento:
        return jsonify({"message": "CPF e data de nascimento são obrigatórios"}), 400

    # Normaliza CPF (remove pontos e traço)
    cpf_limpo = cpf.replace(".", "").replace("-", "").strip()

    db = get_db()
    try:
        # Busca qualquer candidatura com esse CPF e data de nascimento
        cand = db.query(models.Candidatura).filter(
            models.Candidatura.cpf.in_([cpf, cpf_limpo])
        ).first()

        if not cand:
            return jsonify({"message": "CPF não encontrado. Verifique se já se candidatou."}), 404

        # Valida data de nascimento
        try:
            dtn_input = datetime.strptime(data_nascimento, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Data de nascimento inválida"}), 400

        if cand.data_nascimento != dtn_input:
            return jsonify({"message": "Data de nascimento não confere"}), 401

        token = _create_candidato_token(cpf_limpo if cpf_limpo in (cand.cpf or "") else cpf)
        return jsonify({
            "token": token,
            "nome":  cand.full_name.split()[0],  # primeiro nome
        })
    finally:
        db.close()


@bp_cand.get("/minhas-candidaturas")
@require_candidato
def minhas_candidaturas():
    """Retorna todas as candidaturas do candidato logado."""
    cpf = request.candidato_cpf
    db  = get_db()
    try:
        candidaturas = db.query(models.Candidatura).filter(
            models.Candidatura.cpf.in_([cpf, cpf.replace(".", "").replace("-", "")])
        ).order_by(models.Candidatura.applied_at.desc()).all()

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

        result = []
        for c in candidaturas:
            job = db.query(models.Job).filter(models.Job.id == c.job_id).first()
            etapa = c.funnel_stage or c.status
            result.append({
                "id":          c.id,
                "vaga":        job.position if job else "—",
                "local":       job.location if job else "—",
                "status":      STATUS_PT.get(etapa, etapa),
                "statusKey":   etapa,
                "appliedAt":   c.applied_at.strftime("%d/%m/%Y") if c.applied_at else "—",
                "nome":        c.full_name,
                "lgpdConsent": getattr(c, "lgpd_consent", True),
            })

        return jsonify(result)
    finally:
        db.close()


@bp_cand.get("/meu-perfil")
@require_candidato
def meu_perfil():
    """Retorna dados pessoais do candidato (somente leitura)."""
    cpf = request.candidato_cpf
    db  = get_db()
    try:
        c = db.query(models.Candidatura).filter(
            models.Candidatura.cpf.in_([cpf, cpf.replace(".", "").replace("-", "")])
        ).order_by(models.Candidatura.applied_at.desc()).first()

        if not c:
            return jsonify({"message": "Candidato não encontrado"}), 404

        return jsonify({
            "nome":           c.full_name,
            "cpf":            c.cpf,
            "email":          c.email,
            "telefone":       c.phone,
            "cidadeAtual":    c.cidade_atual,
            "formacao":       c.education,
            "experiencia":    c.experience,
        })
    finally:
        db.close()
