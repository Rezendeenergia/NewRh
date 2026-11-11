"""
Rotas para a candidatura à CIPA (Portal do Colaborador).

Públicas:
  POST /api/cipa          — candidatura (sem auth, qualquer colaborador)
                            (nome + matrícula precisam bater com a Base de
                            Colaboradores do RH, no SharePoint)
  GET  /api/cipa/cargos    — lista de cargos (p/ preencher a lista suspensa)

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


# ── Lista de cargos (p/ a lista suspensa do formulário) ──────────

@bp.get("/cargos")
def cargos():
    try:
        from colaboradores_service import listar_cargos
        return jsonify({"cargos": listar_cargos()})
    except Exception as e:
        print(f"[CIPA] Erro ao listar cargos: {e}")
        return jsonify({"cargos": []})


# ── Candidatura pública ─────────────────────────────────────────

@bp.post("")
@limiter.limit("10 per hour")
def candidatar():
    data = request.get_json() or {}

    for field in ["nome", "matricula", "cargo", "motivo"]:
        if not str(data.get(field) or "").strip():
            return jsonify({"message": f"Campo obrigatório: {field}"}), 400

    # Nome: sempre em caixa alta e precisa ser o nome completo (nome + sobrenome).
    nome = " ".join(str(data["nome"]).strip().upper().split())
    if len(nome.split(" ")) < 2:
        return jsonify({"message": "Informe o nome completo (nome e sobrenome)."}), 400

    matricula = str(data["matricula"]).strip()
    motivo    = str(data["motivo"]).strip()
    if not motivo:
        return jsonify({"message": "Conte por que você quer participar da CIPA."}), 400

    from colaboradores_service import validar_colaborador_ativo, listar_cargos, _normalizar_nome

    # Confere nome + matrícula na Base de Colaboradores do RH antes de aceitar.
    try:
        status_colab = validar_colaborador_ativo(nome, matricula)
    except Exception as e:
        print(f"[CIPA] Erro ao validar colaborador: {e}")
        status_colab = "indisponivel"

    if status_colab == "indisponivel":
        return jsonify({
            "message": "Não foi possível confirmar seus dados na base de colaboradores agora. "
                       "Tente novamente em alguns minutos."
        }), 503
    if status_colab != "ok":
        return jsonify({
            "message": "Não encontramos esse nome e matrícula juntos na nossa base de colaboradores ativos. "
                       "Confira se digitou exatamente como está no crachá/contracheque e tente novamente."
        }), 403

    # Cargo: precisa ser um dos cargos existentes na Base de Colaboradores
    # (lista suspensa no formulário) — só valida se a lista veio, pra não
    # bloquear candidaturas por uma falha momentânea ao buscar os cargos.
    cargo = str(data["cargo"]).strip()
    try:
        cargos_validos = listar_cargos()
    except Exception:
        cargos_validos = []
    if cargos_validos and not any(_normalizar_nome(c) == _normalizar_nome(cargo) for c in cargos_validos):
        return jsonify({"message": "Selecione um cargo válido da lista."}), 400

    db = get_db()
    try:
        candidatura = models.CipaCandidatura(
            nome      = nome,
            matricula = matricula,
            cargo     = cargo,
            motivo    = motivo,
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
