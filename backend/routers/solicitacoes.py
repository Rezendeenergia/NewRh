"""
Router — Solicitações de Abertura de Vaga
Fluxo: Gestor solicita → Rafael aprova (e-mail/portal) → Vaga criada automaticamente
Notificações: Rafael recebe e-mail com CC para TI (Ingrid)
              Gestor recebe resultado com CC obrigatório para RH
"""
import secrets
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app, render_template_string
from sqlalchemy.orm import Session

from database import SessionLocal
from models import SolicitacaoVaga, Job, User
from security import decode_token
import audit
from email_service import notify_solicitacao_rafael, notify_resultado_solicitacao, notify_solicitacao_gestor

bp = Blueprint("solicitacoes", __name__, url_prefix="/api/solicitacoes")

RAFAEL_EMAIL = "rafael@rezendeenergia.com.br"


# ── Helpers ───────────────────────────────────────────────────
def _db() -> Session:
    return SessionLocal()


def _current_user(req):
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = decode_token(auth.split(" ", 1)[1])
    return payload  # {"sub": username, "role": role}


def _base_url():
    return current_app.config.get("BASE_URL", request.host_url.rstrip("/"))


# ── POST /api/solicitacoes — Criar solicitação ─────────────────
@bp.route("", methods=["POST"])
def criar_solicitacao():
    user = _current_user(request)
    if not user:
        return jsonify({"message": "Não autorizado"}), 401

    data = request.get_json(force=True) or {}

    position      = (data.get("position") or "").strip()
    location      = (data.get("location") or "").strip()
    tipo          = (data.get("tipo") or "").strip()
    justificativa = (data.get("justificativa") or "").strip()
    nome          = (data.get("responsavel") or "").strip()
    email         = (data.get("emailResp") or "").strip()

    if not all([position, location, tipo, justificativa, nome, email]):
        return jsonify({"message": "Preencha todos os campos obrigatórios"}), 400

    token = secrets.token_urlsafe(32)

    db = _db()
    try:
        sol = SolicitacaoVaga(
            position          = position,
            location          = location,
            tipo              = tipo,
            num_vagas         = int(data.get("numVagas") or 1),
            finalidade        = data.get("finalidade") or None,
            justificativa     = justificativa,
            solicitante_nome  = nome,
            solicitante_email = email,
            solicitante_user  = user["sub"],
            status            = "PENDENTE",
            approval_token    = token,
        )
        db.add(sol)
        db.commit()
        db.refresh(sol)

        audit.log(user["sub"], "CREATE_SOLICITACAO", "solicitacao_vaga", sol.id, f"{position} — {location}")

        # Notifica Rafael (CC: TI)
        try:
            notify_solicitacao_rafael(sol, RAFAEL_EMAIL, _base_url())
        except Exception as e:
            print(f"[EMAIL] Erro ao notificar Rafael: {e}")

        # Confirma para o gestor que a solicitação foi recebida (CC: RH)
        try:
            notify_solicitacao_gestor(sol, _base_url())
        except Exception as e:
            print(f"[EMAIL] Erro ao notificar gestor (confirmação): {e}")

        return jsonify({"id": sol.id, "status": sol.status}), 201
    finally:
        db.close()


# ── GET /api/solicitacoes — Listar ─────────────────────────────
@bp.route("", methods=["GET"])
def listar_solicitacoes():
    user = _current_user(request)
    if not user:
        return jsonify({"message": "Não autorizado"}), 401

    db = _db()
    try:
        q = db.query(SolicitacaoVaga)
        # Dono vê tudo; demais veem só as próprias
        if user.get("role") != "ROLE_OWNER":
            q = q.filter(SolicitacaoVaga.solicitante_user == user["sub"])

        items = q.order_by(SolicitacaoVaga.created_at.desc()).all()

        result = []
        for s in items:
            try:
                result.append({
                    "id":               s.id,
                    "position":         s.position,
                    "location":         s.location,
                    "tipo":             s.tipo,
                    "numVagas":         s.num_vagas,
                    "justificativa":    s.justificativa,
                    "solicitanteNome":  s.solicitante_nome,
                    "solicitanteEmail": s.solicitante_email,
                    "status":           s.status,
                    "motivoRejeicao":   s.motivo_rejeicao,
                    "jobId":            s.job_id,
                    "decididoEm":       s.decidido_em.isoformat() if s.decidido_em else None,
                    "createdAt":        s.created_at.isoformat() if s.created_at else None,
                })
            except Exception as ex:
                print(f"[SOL] Erro ao serializar solicitacao {s.id}: {ex}")

        return jsonify(result)
    except Exception as e:
        print(f"[SOL] Erro ao listar solicitacoes: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()


# ── GET /api/solicitacoes/pending-count — Badge ────────────────
@bp.route("/pending-count", methods=["GET"])
def pending_count():
    user = _current_user(request)
    if not user:
        return jsonify({"count": 0})

    db = _db()
    try:
        count = db.query(SolicitacaoVaga).filter(
            SolicitacaoVaga.status == "PENDENTE"
        ).count()
        return jsonify({"count": count})
    finally:
        db.close()


# ── POST /api/solicitacoes/<id>/decide — Aprovar/Rejeitar (portal) ─
@bp.route("/<int:sol_id>/decide", methods=["POST"])
def decidir_portal(sol_id):
    user = _current_user(request)
    if not user or user.get("role") != "ROLE_OWNER":
        return jsonify({"message": "Acesso restrito ao dono da empresa"}), 403

    data     = request.get_json(force=True) or {}
    decision = (data.get("decision") or "").upper()  # APROVADA | REJEITADA
    motivo   = (data.get("motivo") or "").strip() or None

    if decision not in ("APROVADA", "REJEITADA"):
        return jsonify({"message": "Decisão inválida"}), 400

    db = _db()
    try:
        sol = db.query(SolicitacaoVaga).filter(SolicitacaoVaga.id == sol_id).first()
        if not sol:
            return jsonify({"message": "Solicitação não encontrada"}), 404
        if sol.status != "PENDENTE":
            return jsonify({"message": "Solicitação já decidida"}), 409

        return _processar_decisao(db, sol, decision, motivo, user["sub"])
    finally:
        db.close()


# ── GET /api/solicitacoes/by-token — Dados para página de revisão ─
@bp.route("/by-token", methods=["GET"])
def by_token():
    token = request.args.get("token", "")
    if not token:
        return jsonify({"message": "Token ausente"}), 400

    db = _db()
    try:
        sol = db.query(SolicitacaoVaga).filter(
            SolicitacaoVaga.approval_token == token
        ).first()
        if not sol:
            return jsonify({"message": "Não encontrado"}), 404
        return jsonify({
            "id":               sol.id,
            "position":         sol.position,
            "location":         sol.location,
            "tipo":             sol.tipo,
            "numVagas":         sol.num_vagas,
            "finalidade":       sol.finalidade,
            "justificativa":    sol.justificativa,
            "solicitanteNome":  sol.solicitante_nome,
            "solicitanteEmail": sol.solicitante_email,
            "status":           sol.status,
        })
    finally:
        db.close()


# ── POST /api/solicitacoes/revisar-portal — Decisão via página HTML ─
@bp.route("/revisar-portal", methods=["POST"])
def revisar_portal():
    token    = request.args.get("token", "")
    data     = request.get_json(force=True) or {}
    decision = (data.get("decision") or "").upper()
    motivo   = (data.get("motivo") or "").strip() or None

    if not token or decision not in ("APROVADA", "REJEITADA"):
        return jsonify({"message": "Parâmetros inválidos"}), 400

    db = _db()
    try:
        sol = db.query(SolicitacaoVaga).filter(
            SolicitacaoVaga.approval_token == token
        ).first()
        if not sol:
            return jsonify({"message": "Solicitação não encontrada"}), 404
        if sol.status != "PENDENTE":
            return jsonify({"message": "Solicitação já decidida"}), 409
        return _processar_decisao(db, sol, decision, motivo, "rafael")
    finally:
        db.close()




# ── GET /api/solicitacoes/revisar — Aprovação por link de e-mail ─
@bp.route("/revisar", methods=["GET"])
def revisar_por_email():
    token    = request.args.get("token", "")
    decision = (request.args.get("decision") or "").upper()

    if not token:
        return _html_resultado("Token inválido", False)

    # Se chegou com decision no link → processa direto
    if decision in ("APROVADA", "REJEITADA"):
        db = _db()
        try:
            sol = db.query(SolicitacaoVaga).filter(
                SolicitacaoVaga.approval_token == token
            ).first()
            if not sol:
                return _html_resultado("Solicitação não encontrada", False)
            if sol.status != "PENDENTE":
                return _html_resultado(
                    f"Esta solicitação já foi <strong>{sol.status}</strong> anteriormente.", True
                )
            resp = _processar_decisao(db, sol, decision, None, "rafael")
            msg = "✅ Vaga aprovada e publicada!" if decision == "APROVADA" else "❌ Solicitação rejeitada."
            return _html_resultado(msg, decision == "APROVADA")
        finally:
            db.close()

    # Sem decision → serve a página HTML de revisão
    return current_app.send_static_file("revisar-solicitacao.html")


# ── Helpers internos ──────────────────────────────────────────
def _processar_decisao(db, sol, decision: str, motivo: str, decidido_por: str):
    """Aplica a decisão, cria vaga se aprovada, notifica gestor (CC: RH)."""
    sol.status      = decision
    sol.aprovado_por = decidido_por
    sol.motivo_rejeicao = motivo if decision == "REJEITADA" else None
    sol.decidido_em = datetime.now(timezone.utc)
    sol.approval_token = None   # invalida token após uso

    job_id = None
    if decision == "APROVADA":
        job = Job(
            position   = sol.position,
            location   = sol.location,
            tipo       = sol.tipo,
            num_vagas  = sol.num_vagas,
            finalidade = sol.finalidade,
            responsavel = sol.solicitante_nome,
            email_resp  = sol.solicitante_email,
            status      = "OPEN",
        )
        db.add(job)
        db.flush()
        sol.job_id = job.id
        job_id = job.id

    db.commit()
    db.refresh(sol)

    audit.log(decidido_por, f"SOLICITACAO_{decision}", "solicitacao_vaga", sol.id, f"{sol.position} — {sol.location}")

    # Notifica gestor (CC: RH)
    try:
        notify_resultado_solicitacao(sol, _base_url())
    except Exception as e:
        print(f"[EMAIL] Erro ao notificar gestor: {e}")

    # Notifica candidatos anteriores da mesma vaga que há nova oportunidade
    if decision == "APROVADA" and job_id:
        try:
            _notificar_candidatos_nova_vaga(sol, db)
        except Exception as e:
            print(f"[EMAIL] Erro ao notificar candidatos: {e}")

    return jsonify({
        "status": decision,
        "jobId": job_id,
        "message": "Vaga criada com sucesso!" if decision == "APROVADA" else "Solicitação rejeitada.",
    })


def _notificar_candidatos_nova_vaga(sol, db):
    """Notifica candidatos anteriores quando uma vaga do mesmo cargo é publicada."""
    import models
    from email_service import send_email, _base_template
    BASE_URL = os.getenv("BASE_URL", "https://newrh.onrender.com")

    # Busca candidatos anteriores para o mesmo cargo (não aprovados nem rejeitados)
    from database import get_db as _get_db
    db2 = _get_db()
    try:
        candidatos = (
            db2.query(models.Candidatura)
            .join(models.Job, models.Candidatura.job_id == models.Job.id)
            .filter(
                models.Job.position == sol.position,
                models.Candidatura.status.in_(["PENDING", "REJECTED"]),
            )
            .limit(100).all()
        )
        emails_notificados = set()
        for c in candidatos:
            if c.email in emails_notificados:
                continue
            emails_notificados.add(c.email)
            nome = c.full_name.split()[0]
            subject = f"🎯 Nova vaga disponível: {sol.position} — Rezende Energia"
            content_html = (
                f'<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">'
                f'Olá, {nome}! 👋</h2>'
                f'<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);font-weight:600;'
                f'text-transform:uppercase;letter-spacing:2px;">Nova Oportunidade</p>'
                f'<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 16px;">'
                f'Uma nova vaga de <strong style="color:#fff;">{sol.position}</strong> '
                f'em <strong style="color:#fff;">{sol.location}</strong> acaba de ser publicada '
                f'no nosso portal de carreiras!</p>'
                f'<div style="text-align:center;margin:0 0 24px;">'
                f'<a href="{BASE_URL}" style="display:inline-block;background:linear-gradient(135deg,#FF8C2A,#FF6A00);'
                f'color:#000;font-weight:800;font-size:15px;text-decoration:none;'
                f'padding:14px 36px;border-radius:10px;">🚀 Ver Vaga</a></div>'
                f'<p style="color:#5A6478;font-size:12px;text-align:center;margin:0;">'
                f'Rezende Energia · Portal de Carreiras</p>'
            )
            send_email(c.email, subject, _base_template(subject, content_html))
            print(f"[EMAIL] Nova vaga notificada para {c.email}")
    finally:
        db2.close()


def _html_resultado(mensagem: str, sucesso: bool) -> str:
    cor  = "#2ECC71" if sucesso else "#FF5252"
    icon = "✅" if sucesso else "❌"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Resultado — Rezende Energia</title>
<style>body{{margin:0;background:#0B0F14;font-family:'Segoe UI',Arial,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh;}}
.box{{background:#141820;border:1px solid rgba(255,255,255,.08);border-top:3px solid {cor};
border-radius:16px;padding:48px 40px;max-width:440px;text-align:center;}}
h1{{color:#fff;font-size:20px;font-weight:800;margin:16px 0 8px;}}
p{{color:#9AA3B2;font-size:14px;line-height:1.6;}}
</style></head>
<body><div class="box">
<div style="font-size:48px">{icon}</div>
<h1>Rezende Energia — Portal de Vagas</h1>
<p>{mensagem}</p>
<p style="margin-top:24px;font-size:12px;color:#5A6478;">Você pode fechar esta janela.</p>
</div></body></html>""", 200
