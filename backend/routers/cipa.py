"""
Rotas para a candidatura à CIPA (Portal do Colaborador).

Públicas:
  POST /api/cipa          — candidatura (sem auth, qualquer colaborador)

Protegidas (gestores RH):
  GET  /api/cipa          — lista todas as candidaturas
"""
from flask import Blueprint, request, jsonify
from database import get_db
from security import require_auth
from extensions import limiter
import models
import os as _os

bp = Blueprint("cipa", __name__, url_prefix="/api/cipa")


def _to_dict(c):
    return {
        "id":        c.id,
        "nome":      c.nome,
        "matricula": c.matricula,
        "cargo":     c.cargo,
        "motivo":    c.motivo,
        "gestao":    c.gestao,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


# ── Candidatura pública ─────────────────────────────────────────

@bp.post("")
@limiter.limit("10 per hour")
def candidatar():
    data = request.get_json() or {}

    for field in ["nome", "matricula", "cargo", "motivo"]:
        if not str(data.get(field) or "").strip():
            return jsonify({"message": f"Campo obrigatório: {field}"}), 400

    db = get_db()
    try:
        candidatura = models.CipaCandidatura(
            nome      = data["nome"].strip(),
            matricula = data["matricula"].strip(),
            cargo     = data["cargo"].strip(),
            motivo    = data["motivo"].strip(),
        )
        db.add(candidatura)
        db.commit()
        db.refresh(candidatura)

        try:
            from email_service import send_email
            dest = _os.getenv("RH_EMAIL", "rh@rezendeenergia.com.br")
            send_email(
                dest,
                f"[NewRH] Nova candidatura à CIPA — {candidatura.nome}",
                f"""
                <h2>Nova candidatura à CIPA (gestão {candidatura.gestao})</h2>
                <p><b>Nome:</b> {candidatura.nome}</p>
                <p><b>Matrícula:</b> {candidatura.matricula}</p>
                <p><b>Cargo:</b> {candidatura.cargo}</p>
                <p><b>Por que quer participar:</b><br>{candidatura.motivo}</p>
                """,
            )
        except Exception as e:
            print(f"[CIPA] Erro e-mail: {e}")

        return jsonify(_to_dict(candidatura)), 201
    finally:
        db.close()


# ── Listagem (gestores) ──────────────────────────────────────────

@bp.get("")
@require_auth
def listar():
    db = get_db()
    try:
        itens = (
            db.query(models.CipaCandidatura)
            .order_by(models.CipaCandidatura.created_at.desc())
            .all()
        )
        return jsonify([_to_dict(c) for c in itens])
    finally:
        db.close()
