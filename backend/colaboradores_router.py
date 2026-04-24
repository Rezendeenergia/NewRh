"""
Router para busca de colaboradores e headcount.
"""
from flask import Blueprint, request, jsonify
from security import require_auth
from database import get_db
import models
from sqlalchemy import func

bp_colab = Blueprint("colaboradores", __name__, url_prefix="/api/colaboradores")


@bp_colab.get("/buscar")
@require_auth
def buscar():
    """Busca colaboradores na planilha do SharePoint (para Mudança de Função)."""
    q = request.args.get("q", "").strip()
    try:
        from colaboradores_service import buscar_colaboradores
        result = buscar_colaboradores(q, limit=15)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "items": []}), 500


@bp_colab.get("/headcount")
@require_auth
def headcount():
    """Headcount: candidatos aprovados por localidade e cargo."""
    db = get_db()
    try:
        # Por localidade
        por_local = (
            db.query(models.Job.location, func.count(models.Candidatura.id).label("total"))
            .join(models.Candidatura, models.Candidatura.job_id == models.Job.id)
            .filter(models.Candidatura.status == "APPROVED")
            .group_by(models.Job.location)
            .order_by(func.count(models.Candidatura.id).desc())
            .all()
        )

        # Por cargo
        por_cargo = (
            db.query(models.Job.position, func.count(models.Candidatura.id).label("total"))
            .join(models.Candidatura, models.Candidatura.job_id == models.Job.id)
            .filter(models.Candidatura.status == "APPROVED")
            .group_by(models.Job.position)
            .order_by(func.count(models.Candidatura.id).desc())
            .all()
        )

        # Por funil (todas as etapas)
        FUNIL = ["PENDING","TRIAGEM","TRIAGEM_OK","ENTREVISTA","ENTREVISTA_OK","APROVACAO_FINAL","APPROVED","REJECTED"]
        FUNIL_PT = {
            "PENDING":         "📥 Recebidas",
            "TRIAGEM":         "🔍 Triagem",
            "TRIAGEM_OK":      "✅ Triagem OK",
            "ENTREVISTA":      "🎤 Entrevista",
            "ENTREVISTA_OK":   "✅ Entrevista OK",
            "APROVACAO_FINAL": "🏆 Aprovação Final",
            "APPROVED":        "✅ Aprovados",
            "REJECTED":        "❌ Não Selecionados",
        }
        por_funil = (
            db.query(models.Candidatura.status, func.count(models.Candidatura.id))
            .group_by(models.Candidatura.status).all()
        )

        # NRs próximas do vencimento (candidatos com documentos de NR)
        nrs_expirando = []
        try:
            from datetime import datetime, timedelta
            limite = datetime.now() + timedelta(days=90)
            docs_nr = (
                db.query(models.CandidatoDocumento)
                .filter(models.CandidatoDocumento.tipo == "NR")
                .all()
            )
            for d in docs_nr:
                if d.enviado_em:
                    # NRs geralmente vencem em 2 anos
                    vencimento = d.enviado_em.replace(year=d.enviado_em.year + 2)
                    if vencimento <= limite:
                        cand = db.query(models.Candidatura).filter_by(id=d.candidatura_id).first()
                        if cand:
                            nrs_expirando.append({
                                "nome":       cand.full_name,
                                "documento":  d.descricao or d.nome,
                                "vencimento": vencimento.strftime("%d/%m/%Y"),
                                "diasRestantes": (vencimento - datetime.now()).days,
                            })
        except Exception as ex:
            print(f"[HEADCOUNT] NRs: {ex}")

        return jsonify({
            "porLocalidade": [{"local": r[0], "total": r[1]} for r in por_local],
            "porCargo":      [{"cargo": r[0], "total": r[1]} for r in por_cargo],
            "porFunil":      [{"etapa": FUNIL_PT.get(r[0], r[0]), "key": r[0], "total": r[1]} for r in por_funil],
            "nrsExpirando":  sorted(nrs_expirando, key=lambda x: x["diasRestantes"]),
        })
    finally:
        db.close()
