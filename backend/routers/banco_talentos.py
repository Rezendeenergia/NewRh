"""
Rotas para o módulo Banco de Talentos (inscrição espontânea).

Públicas:
  POST /api/banco-talentos          — inscrição pública (sem auth)

Protegidas (gestores):
  GET  /api/banco-talentos          — lista todas as inscrições
  GET  /api/banco-talentos/<id>     — detalhe de uma inscrição
  GET  /api/banco-talentos/<id>/resume-url — URL do currículo no SharePoint
  GET  /api/banco-talentos/<id>/resume     — download/proxy do currículo
  PATCH /api/banco-talentos/<id>/status    — atualiza status + observações

Armazenamento de currículos:
  SharePoint → Intranet / Documentos Compartilhados /
               ADMINISTRAÇÃO/Departamento de Gestão de Pessoas/RH/BANCO DE TALENTOS
  A URL do arquivo é salva em resume_url; resume_name guarda o nome original.
  NÃO usa disco local (Render é efêmero).
"""
from flask import Blueprint, request, jsonify, send_file
from database import get_db
from security import require_auth
from extensions import limiter
import models
import os as _os

bp = Blueprint("banco_talentos", __name__, url_prefix="/api/banco-talentos")

STATUS_LABELS = {
    "PENDENTE":   "Pendente",
    "EM_ANALISE": "Em Análise",
    "APROVADO":   "Aprovado",
    "REJEITADO":  "Rejeitado",
}


def _to_dict(t):
    return {
        "id":                    t.id,
        "fullName":              t.full_name,
        "cpf":                   t.cpf,
        "dataNascimento":        t.data_nascimento.isoformat() if t.data_nascimento else None,
        "phone":                 t.phone,
        "email":                 t.email,
        "cidadeAtual":           t.cidade_atual,
        "linkedin":              t.linkedin,
        "vagaInteresse":         t.vaga_interesse,
        "education":             t.education,
        "experience":            t.experience,
        "disponibilidadeViagem": t.disponibilidade_viagem,
        "motivation":            t.motivation,
        "resumeName":            t.resume_name,
        "resumeUrl":             getattr(t, "resume_url", None),
        "hasResume":             bool(t.resume_name),
        "status":                t.status,
        "statusLabel":           STATUS_LABELS.get(t.status, t.status),
        "observacoesGestor":     t.observacoes_gestor,
        "createdAt":             t.created_at.isoformat() if t.created_at else None,
        "updatedAt":             t.updated_at.isoformat() if t.updated_at else None,
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

    db = get_db()
    try:
        # Duplicidade por CPF (inscrição ainda pendente/em análise)
        existente = db.query(models.BancoTalentos).filter_by(cpf=data["cpf"]).first()
        if existente and existente.status in ("PENDENTE", "EM_ANALISE"):
            return jsonify({
                "message": "Já existe uma inscrição em andamento com este CPF. Aguarde o contato da nossa equipe."
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
                from sharepoint_service import upload_bytes, BASE_PATH_TALENTOS
                resume_url = upload_bytes(
                    file_bytes=pdf_bytes,
                    nome_arquivo=resume_name,
                    caminho_pasta=BASE_PATH_TALENTOS,
                )
                if not resume_url:
                    print(f"[BANCO_TALENTOS] Upload SharePoint falhou — salvando sem currículo")
            except Exception as e:
                print(f"[BANCO_TALENTOS] Erro upload SharePoint: {e}")

        inscricao = models.BancoTalentos(
            full_name              = data["fullName"],
            cpf                    = data["cpf"],
            data_nascimento        = data.get("dataNascimento") or None,
            phone                  = data["phone"],
            email                  = data["email"],
            cidade_atual           = data.get("cidadeAtual") or None,
            linkedin               = data.get("linkedin") or None,
            vaga_interesse         = data.get("vagaInteresse") or None,
            education              = data.get("education") or None,
            experience             = data.get("experience") or None,
            disponibilidade_viagem = data.get("disponibilidadeViagem") or None,
            motivation             = data.get("motivation") or None,
            resume_name            = resume_name,
            resume_url             = resume_url,
            status                 = "PENDENTE",
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
                f"[NewRH] Nova inscrição Banco de Talentos — {inscricao.full_name}",
                f"""
                <h2>Nova inscrição no Banco de Talentos</h2>
                <p><b>Nome:</b> {inscricao.full_name}</p>
                <p><b>CPF:</b> {inscricao.cpf}</p>
                <p><b>Telefone:</b> {inscricao.phone}</p>
                <p><b>E-mail:</b> {inscricao.email}</p>
                <p><b>Vaga/Área de Interesse:</b> {inscricao.vaga_interesse or '—'}</p>
                <p><b>Formação:</b> {inscricao.education or '—'}</p>
                <p><b>Experiência:</b> {inscricao.experience or '—'}</p>
                {"<p><b>Currículo:</b> <a href='" + resume_url + "'>Abrir no SharePoint</a></p>" if resume_url else ""}
                <p>Acesse o portal NewRH para visualizar a inscrição completa.</p>
                """,
            )
        except Exception as e:
            print(f"[BANCO_TALENTOS] Erro e-mail: {e}")

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
        query         = db.query(models.BancoTalentos).order_by(models.BancoTalentos.created_at.desc())
        if status_filter:
            query = query.filter(models.BancoTalentos.status == status_filter)
        items = query.all()
        if q:
            items = [
                t for t in items
                if q in (t.full_name or "").lower()
                or q in (t.cpf or "").lower()
                or q in (t.vaga_interesse or "").lower()
                or q in (t.email or "").lower()
            ]
        return jsonify([_to_dict(t) for t in items])
    finally:
        db.close()


# ── Detalhe ───────────────────────────────────────────────────

@bp.get("/<int:talento_id>")
@require_auth
def detalhe(talento_id):
    db = get_db()
    try:
        t = db.query(models.BancoTalentos).filter_by(id=talento_id).first()
        if not t:
            return jsonify({"message": "Inscrição não encontrada"}), 404
        return jsonify(_to_dict(t))
    finally:
        db.close()


# ── URL do currículo (frontend abre via window.open) ───────────

@bp.get("/<int:talento_id>/resume-url")
@require_auth
def get_resume_url(talento_id):
    db = get_db()
    try:
        t = db.query(models.BancoTalentos).filter_by(id=talento_id).first()
        if not t or not t.resume_name:
            return jsonify({"message": "Currículo não encontrado"}), 404
        if not getattr(t, "resume_url", None):
            return jsonify({"message": "URL do arquivo não disponível"}), 404
        return jsonify({"url": t.resume_url, "name": t.resume_name})
    finally:
        db.close()


# ── Download proxy (baixa do SharePoint e serve ao browser) ────
# Evita CORS: o backend busca o arquivo e entrega diretamente.

@bp.get("/<int:talento_id>/resume")
@require_auth
def download_resume(talento_id):
    db = get_db()
    try:
        t = db.query(models.BancoTalentos).filter_by(id=talento_id).first()
        if not t or not t.resume_name:
            return jsonify({"message": "Currículo não encontrado"}), 404
        if not getattr(t, "resume_url", None):
            return jsonify({"message": "Arquivo não disponível"}), 404

        try:
            from sharepoint_service import _get_token
            import requests as http
            import io
            token = _get_token()
            r = http.get(
                t.resume_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
                allow_redirects=True,
            )
            if not r.ok:
                return jsonify({"message": "Não foi possível recuperar o arquivo"}), 502
            return send_file(
                io.BytesIO(r.content),
                mimetype="application/pdf",
                as_attachment=False,
                download_name=t.resume_name,
            )
        except Exception as e:
            print(f"[BANCO_TALENTOS] Erro proxy resume: {e}")
            return jsonify({"message": "Erro ao recuperar arquivo"}), 500
    finally:
        db.close()


# ── Atualizar status ────────────────────────────────────────────

@bp.patch("/<int:talento_id>/status")
@require_auth
def atualizar_status(talento_id):
    data       = request.get_json() or {}
    novo_status = data.get("status")
    if novo_status not in STATUS_LABELS:
        return jsonify({"message": f"Status inválido. Opções: {list(STATUS_LABELS.keys())}"}), 400
    db = get_db()
    try:
        t = db.query(models.BancoTalentos).filter_by(id=talento_id).first()
        if not t:
            return jsonify({"message": "Inscrição não encontrada"}), 404
        t.status = novo_status
        if "observacoesGestor" in data:
            t.observacoes_gestor = data["observacoesGestor"]
        db.commit()
        db.refresh(t)
        return jsonify(_to_dict(t))
    finally:
        db.close()
