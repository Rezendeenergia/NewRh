"""
Rotas para o módulo Menor Aprendiz.

P�blicas:
  POST /api/menor-aprendiz          — inscrição pública (sem auth)

Protegidas (gestores):
  GET  /api/menor-aprendiz          — lista todas as inscrições
  GET  /api/menor-aprendiz/<id>     — detalhe de uma inscrição
  GET  /api/menor-aprendiz/<id>/resume — download/redirect do currículo
  PATCH /api/menor-aprendiz/<id>/status — atualiza status + observações

Armazenamento de currículos:
  SharePoint → Intranet / Documentos Compartilhados /
               ADMINISTRAÇÃO/Departamento de Gestão de Pessoas/RH/MENOR APRENDIZ
  A URL do arquivo é salva em resume_url; resume_name guarda o nome original.
  NÃO usa disco local (Render é efêmero).
"""
from flask import Blueprint, request, jsonify, redirect
from database import get_db
from security import require_auth
from extensions import limiter
from datetime import date
import models
import os as _os

bp = Blueprint("menor_aprendiz", __name__, url_prefix="/api/menor-aprendiz")

STATUS_LABELS = {
    "PENDENTE":   "Pendente",
    "EM_ANALISE": "Em Análise",
    "APROVADO":   "Aprovado",
    "REJEITADO":  "Rejeitado",
}


def _to_dict(a):
    return {
        "id":                a.id,
        "fullName":          a.full_name,
        "cpf":               a.cpf,
        "dataNascimento":    a.data_nascimento.isoformat() if a.data_nascimento else None,
        "nomeResponsavel":   a.nome_responsavel,
        "phone":             a.phone,
        "email":             a.email,
        "cidadeAtual":       a.cidade_atual,
        "escolaAtual":       a.escola_atual,
        "periodoEscolar":    a.periodo_escolar,
        "turnoEscolar":      a.turno_escolar,
        "areaInteresse":     a.area_interesse,
        "motivation":        a.motivation,
        "resumeName":        a.resume_name,
        "resumeUrl":         getattr(a, "resume_url", None),
        "hasResume":         bool(a.resume_name),
        "status":            a.status,
        "statusLabel":       STATUS_LABELS.get(a.status, a.status),
        "observacoesGestor": a.observacoes_gestor,
        "createdAt":         a.created_at.isoformat() if a.created_at else None,
        "updatedAt":         a.updated_at.isoformat() if a.updated_at else None,
    }


# ── Inscrição pública ─────────────────────────────────────────

@bp.post("")
@limiter.limit("5 per hour")
def inscrever():
    multipart = request.content_type and "multipart/form-data" in request.content_type
    data      = request.form if multipart else (request.get_json() or {})
    pdf_file  = request.files.get("resume") if multipart else None

    for field in ["fullName", "cpf", "phone", "email"]:
        if not data.get(field):
            return jsonify({"message": f"Campo obrigatório: {field}"}), 400

    # Validação de idade (14–18 anos)
    if data.get("dataNascimento"):
        try:
            dn    = date.fromisoformat(data["dataNascimento"])
            hoje  = date.today()
            idade = hoje.year - dn.year - ((hoje.month, hoje.day) < (dn.month, dn.day))
            if idade < 14 or idade > 18:
                return jsonify({
                    "message": "O Programa Menor Aprendiz é destinado a jovens com idade entre 14 e 18 anos."
                }), 400
        except ValueError:
            pass

    db = get_db()
    try:
        # Duplicidade por CPF
        if db.query(models.MenorAprendiz).filter_by(cpf=data["cpf"]).first():
            return jsonify({
                "message": "Já existe uma inscrição com este CPF. Aguarde o contato da nossa equipe."
            }), 409

        resume_name = None
        resume_url  = None

        if pdf_file and pdf_file.filename:
            if not pdf_file.filename.lower().endswith(".pdf"):
                return jsonify({"message": "Apenas PDFs são aceitos"}), 400
            pdf_bytes = pdf_file.read()
            if len(pdf_bytes) > 5 * 1024 * 1024:
                return jsonify({"message": "Arquivo muito grande (máx. 5 MB)"}), 400

            cpf_clean   = data["cpf"].replace(".", "").replace("-", "")
            nome_clean  = data["fullName"].replace(" ", "_").upper()
            resume_name = f"{nome_clean}_{cpf_clean}_curriculo.pdf"

            try:
                from sharepoint_service import upload_bytes, BASE_PATH_APRENDIZ
                resume_url = upload_bytes(
                    file_bytes=pdf_bytes,
                    nome_arquivo=resume_name,
                    caminho_pasta=BASE_PATH_APRENDIZ,
                )
                if not resume_url:
                    print(f"[MENOR_APRENDIZ] Upload SharePoint falhou — salvando sem currículo")
            except Exception as e:
                print(f"[MENOR_APRENDIZ] Erro upload SharePoint: {e}")

        inscricao = models.MenorAprendiz(
            full_name        = data["fullName"],
            cpf              = data["cpf"],
            data_nascimento  = data.get("dataNascimento") or None,
            nome_responsavel = data.get("nomeResponsavel") or None,
            phone            = data["phone"],
            email            = data["email"],
            cidade_atual     = data.get("cidadeAtual") or None,
            escola_atual     = data.get("escolaAtual") or None,
            periodo_escolar  = data.get("periodoEscolar") or None,
            turno_escolar    = data.get("turnoEscolar") or None,
            area_interesse   = data.get("areaInteresse") or None,
            motivation       = data.get("motivation") or None,
            resume_name      = resume_name,
            resume_url       = resume_url,
            status           = "PENDENTE",
        )
        db.add(inscricao)
        db.commit()
        db.refresh(inscricao)

        # Notificação por e-mail
        try:
            from email_service import send_email
            dest = _os.getenv("RH_EMAIL", "rh@rezendeenergia.com.br")
            send_email(
                dest,
                f"[NewRH] Nova inscrição Menor Aprendiz — {inscricao.full_name}",
                f"""
                <h2>Nova inscrição de Menor Aprendiz</h2>
                <p><b>Nome:</b> {inscricao.full_name}</p>
                <p><b>CPF:</b> {inscricao.cpf}</p>
                <p><b>Telefone:</b> {inscricao.phone}</p>
                <p><b>E-mail:</b> {inscricao.email}</p>
                <p><b>Escola:</b> {inscricao.escola_atual or '—'}</p>
                <p><b>Área de Interesse:</b> {inscricao.area_interesse or '—'}</p>
                {"<p><b>Currículo:</b> <a href='" + resume_url + "'>Abrir no SharePoint</a></p>" if resume_url else ""}
                <p>Acesse o portal NewRH para visualizar a inscrição completa.</p>
                """,
            )
        except Exception as e:
            print(f"[MENOR_APRENDIZ] Erro e-mail: {e}")

        return jsonify(_to_dict(inscricao)), 201
    finally:
        db.close()


# ── Listagem (gestores) ───────────────────────────────────────

@bp.get("")
@require_auth
def listar():
    db = get_db()
    try:
        status_filter = request.args.get("status")
        q             = request.args.get("q", "").strip().lower()
        query         = db.query(models.MenorAprendiz).order_by(models.MenorAprendiz.created_at.desc())
        if status_filter:
            query = query.filter(models.MenorAprendiz.status == status_filter)
        items = query.all()
        if q:
            items = [
                a for a in items
                if q in (a.full_name or "").lower()
                or q in (a.cpf or "").lower()
                or q in (a.escola_atual or "").lower()
                or q in (a.area_interesse or "").lower()
            ]
        return jsonify([_to_dict(a) for a in items])
    finally:
        db.close()


# ── Detalhe ───────────────────────────────────────────────────

@bp.get("/<int:aprendiz_id>")
@require_auth
def detalhe(aprendiz_id):
    db = get_db()
    try:
        a = db.query(models.MenorAprendiz).filter_by(id=aprendiz_id).first()
        if not a:
            return jsonify({"message": "Inscrição não encontrada"}), 404
        return jsonify(_to_dict(a))
    finally:
        db.close()


# ── Abrir currículo (redireciona para SharePoint) ─────────────

@bp.get("/<int:aprendiz_id>/resume")
@require_auth
def download_resume(aprendiz_id):
    db = get_db()
    try:
        a = db.query(models.MenorAprendiz).filter_by(id=aprendiz_id).first()
        if not a or not a.resume_name:
            return jsonify({"message": "Currículo não encontrado"}), 404

        # Se tiver URL salva, redireciona direto para o SharePoint
        if getattr(a, "resume_url", None):
            return redirect(a.resume_url)

        return jsonify({"message": "Arquivo não disponível"}), 404
    finally:
        db.close()


# ── Atualizar status ──────────────────────────────────────────

@bp.patch("/<int:aprendiz_id>/status")
@require_auth
def atualizar_status(aprendiz_id):
    data       = request.get_json() or {}
    novo_status = data.get("status")
    if novo_status not in STATUS_LABELS:
        return jsonify({"message": f"Status inválido. Opções: {list(STATUS_LABELS.keys())}"}), 400
    db = get_db()
    try:
        a = db.query(models.MenorAprendiz).filter_by(id=aprendiz_id).first()
        if not a:
            return jsonify({"message": "Inscrição não encontrada"}), 404
        a.status = novo_status
        if "observacoesGestor" in data:
            a.observacoes_gestor = data["observacoesGestor"]
        db.commit()
        db.refresh(a)
        return jsonify(_to_dict(a))
    finally:
        db.close()
