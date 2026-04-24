"""
Router de Processos de Admissão — versão otimizada.
"""
from flask import Blueprint, request, jsonify, send_file
from database import get_db
from security import require_auth
from datetime import datetime, timezone
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload, selectinload
import models
import audit
import os

bp = Blueprint("processos", __name__, url_prefix="/api/processos")

UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", "admissao"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ETAPAS_FLUXO = [
    {"ordem": 1,  "codigo": "TRIAGEM",              "nome": "Triagem",                        "departamento": "RH",         "tipo": "APROVACAO",   "prazo_dias": 2},
    {"ordem": 2,  "codigo": "ENTREVISTA",            "nome": "Entrevista",                     "departamento": "RH",         "tipo": "ENTREVISTA",  "prazo_dias": 5},
    {"ordem": 3,  "codigo": "APROVACAO_FINAL",       "nome": "Aprovação Final",                "departamento": "RH",         "tipo": "APROVACAO",   "prazo_dias": 1},
    {"ordem": 4,  "codigo": "ASO",                   "nome": "ASO",                "departamento": "RH",         "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 5,  "codigo": "DP_EXTERNO",            "nome": "Admissão DP Externo",            "departamento": "DP_EXTERNO", "tipo": "DOCUMENTO",   "prazo_dias": 2},
    {"ordem": 6,  "codigo": "ASSINATURAS",           "nome": "Coleta de Assinaturas",          "departamento": "DP",         "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 7,  "codigo": "CADASTRO_GPM",          "nome": "Cadastro no GPM",                "departamento": "DP",         "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 8,  "codigo": "ACESSO_TI",             "nome": "Criação de Acesso TI/Sistemas",  "departamento": "TI",         "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 9,  "codigo": "BEMHOEFT",              "nome": "Inclusão Prontuário Bemhoeft",   "departamento": "DP",         "tipo": "DOCUMENTO",   "prazo_dias": 3},
    {"ordem": 10, "codigo": "EPIS_UNIFORMES",        "nome": "Fornecimento EPIs e Uniformes",  "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 11, "codigo": "FORMACAO_NRS",          "nome": "Formação e Reciclagem NRs",      "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 5},
    {"ordem": 12, "codigo": "PRONTUARIO_SEGURANCA",  "nome": "Prontuário de Segurança",        "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 13, "codigo": "CERTIFICADOS_NR",       "nome": "Verificação Certificados NRs",   "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 2},
    {"ordem": 14, "codigo": "PROVA_DEEP",            "nome": "Prova DEEP",                     "departamento": "SESMT",      "tipo": "APROVACAO",   "prazo_dias": 3},
    {"ordem": 15, "codigo": "GRAFICA_CRACHA",        "nome": "Confecção do Crachá",            "departamento": "RH",         "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 16, "codigo": "INTEGRACAO_EQUATORIAL", "nome": "Integração Equatorial",          "departamento": "RH",         "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 17, "codigo": "LIBERADO_CAMPO",        "nome": "Liberação para Campo",           "departamento": "RH",         "tipo": "APROVACAO",   "prazo_dias": 1},
]

DEPT_LABEL = {
    "RH": "Recursos Humanos",
    "DP": "Departamento Pessoal",
    "DP_EXTERNO": "DP Externo",
    "SESMT": "SESMT",
    "TI": "TI",
}


def doc_to_dict(d):
    return {
        "id":            d.id,
        "nome":          d.nome,
        "arquivo":       d.arquivo,
        "sharepointUrl": d.sharepoint_url,
        "enviadoPor":    d.enviado_por,
        "status":        d.status,
        "observacao":    d.observacao,
        "createdAt":     d.created_at.isoformat() if d.created_at else None,
    }


def etapa_to_dict(e):
    return {
        "id":           e.id,
        "ordem":        e.ordem,
        "codigo":       e.codigo,
        "nome":         e.nome,
        "departamento": e.departamento,
        "deptLabel":    DEPT_LABEL.get(e.departamento, e.departamento),
        "tipo":         e.tipo,
        "status":       e.status,
        "prazo_dias":   e.prazo_dias,
        "observacao":   e.observacao,
        "nota":         e.nota,
        "responsavel":  e.responsavel,
        "iniciadoEm":   e.iniciado_em.isoformat() if e.iniciado_em else None,
        "concluidoEm":  e.concluido_em.isoformat() if e.concluido_em else None,
        "documentos":   [doc_to_dict(d) for d in e.documentos],
    }


def _calc_progresso(etapas):
    if not etapas:
        return 0
    total     = len(etapas)
    concluidas = sum(1 for e in etapas if e.status in ("APROVADO", "NAO_APLICAVEL"))
    return round(concluidas / total * 100)


def processo_to_dict_list(p):
    """Versão leve para listagem — sem documentos, só dados essenciais."""
    c = p.candidatura
    etapas = p.etapas  # já carregadas com selectinload
    etapa_atual = next((e for e in etapas if e.status == "EM_ANDAMENTO"),
                  next((e for e in sorted(etapas, key=lambda x: x.ordem) if e.status == "PENDENTE"), None))
    return {
        "id":            p.id,
        "status":        p.status,
        "etapaAtual":    p.etapa_atual,
        "sharepointUrl": p.sharepoint_url,
        "progresso":     _calc_progresso(etapas),
        "candidatura": {
            "id":    c.id,
            "nome":  c.full_name,
            "cpf":   c.cpf,
            "cargo": c.job.position if c.job else "—",
            "local": c.job.location if c.job else "—",
        },
        "etapas": [{
            "id":           e.id,
            "nome":         e.nome,
            "departamento": e.departamento,
            "status":       e.status,
            "prazo_data":   None,
        } for e in etapas],
    }


def processo_to_dict(p):
    """Versão completa para detalhe — inclui documentos."""
    c = p.candidatura
    return {
        "id":            p.id,
        "status":        p.status,
        "etapaAtual":    p.etapa_atual,
        "sharepointUrl": p.sharepoint_url,
        "createdAt":     p.created_at.isoformat() if p.created_at else None,
        "updatedAt":     p.updated_at.isoformat() if p.updated_at else None,
        "candidatura": {
            "id":    c.id,
            "nome":  c.full_name,
            "cpf":   c.cpf,
            "email": c.email,
            "phone": c.phone,
            "cargo": c.job.position if c.job else "—",
            "local": c.job.location if c.job else "—",
        },
        "etapas":    [etapa_to_dict(e) for e in p.etapas],
        "progresso": _calc_progresso(p.etapas),
    }


def _criar_etapas(processo_id, db):
    for e in ETAPAS_FLUXO:
        db.add(models.EtapaProcesso(
            processo_id=processo_id,
            ordem=e["ordem"], codigo=e["codigo"], nome=e["nome"],
            departamento=e["departamento"], tipo=e["tipo"],
            prazo_dias=e["prazo_dias"], status="PENDENTE",
        ))


def _avancar_etapa(processo, db):
    pendentes = sorted([e for e in processo.etapas if e.status == "PENDENTE"], key=lambda x: x.ordem)
    if pendentes:
        prox = pendentes[0]
        prox.status      = "EM_ANDAMENTO"
        prox.iniciado_em = datetime.now(timezone.utc)
        processo.etapa_atual = prox.nome
    else:
        processo.status      = "CONCLUIDO"
        processo.etapa_atual = "Concluído"
    db.commit()


def criar_processo_para_candidatura(candidatura_id: int, db, tipo_admissao: str = "ADMISSAO_NOVA") -> models.ProcessoAdmissao:
    existing = db.query(models.ProcessoAdmissao).filter_by(candidatura_id=candidatura_id).first()
    if existing:
        return existing

    processo = models.ProcessoAdmissao(
        candidatura_id=candidatura_id,
        status="EM_ANDAMENTO",
        etapa_atual="Triagem",
    )
    db.add(processo)
    db.flush()
    _criar_etapas(processo.id, db)
    db.flush()

    primeira = db.query(models.EtapaProcesso)\
        .filter_by(processo_id=processo.id, ordem=1).first()
    if primeira:
        primeira.status      = "EM_ANDAMENTO"
        primeira.iniciado_em = datetime.now(timezone.utc)

    db.commit()

    try:
        cand = db.query(models.Candidatura).filter_by(id=candidatura_id).first()
        if cand:
            from sharepoint_service import criar_pasta_colaborador
            result = criar_pasta_colaborador(cand.full_name, cand.cpf)
            if result.get("url"):
                processo.sharepoint_url = result["url"]
                db.commit()
    except Exception as e:
        print(f"[SHAREPOINT] Erro ao confirmar pasta: {e}")

    return processo


# ── Listar processos — otimizado ──────────────────────────────

@bp.get("")
@require_auth
def listar():
    status_f = request.args.get("status", "").upper()
    dept_f   = request.args.get("departamento", "").upper()
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 30  # aumentado de 20 para 30

    db = get_db()
    try:
        q = db.query(models.ProcessoAdmissao)

        if status_f:
            q = q.filter(models.ProcessoAdmissao.status == status_f)

        # Filtro por dept via JOIN no banco (não Python-side)
        if dept_f:
            q = q.join(
                models.EtapaProcesso,
                (models.EtapaProcesso.processo_id == models.ProcessoAdmissao.id) &
                (models.EtapaProcesso.status == "EM_ANDAMENTO") &
                (models.EtapaProcesso.departamento == dept_f)
            )

        total = q.count()

        # Eager load: etapas sem documentos (para listagem)
        rows = (
            q.options(
                joinedload(models.ProcessoAdmissao.candidatura)
                    .joinedload(models.Candidatura.job),
                selectinload(models.ProcessoAdmissao.etapas),  # sem docs
            )
            .order_by(models.ProcessoAdmissao.updated_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return jsonify({
            "items":      [processo_to_dict_list(p) for p in rows],
            "total":      total,
            "page":       page,
            "totalPages": max(1, -(-total // per_page)),
        })
    finally:
        db.close()


@bp.get("/stats")
@require_auth
def stats():
    db = get_db()
    try:
        # 1 query com CASE ao invés de 4 separadas
        row = db.execute(
            __import__('sqlalchemy').text("""
                SELECT
                    COUNT(*)                                                AS total,
                    COUNT(*) FILTER (WHERE status = 'EM_ANDAMENTO')        AS andamento,
                    COUNT(*) FILTER (WHERE status = 'CONCLUIDO')           AS concluidos,
                    COUNT(*) FILTER (WHERE status = 'CANCELADO')           AS cancelados
                FROM processo_admissao
            """)
        ).fetchone()

        # Etapas ativas por dept — 1 query
        dept_rows = db.execute(
            __import__('sqlalchemy').text("""
                SELECT departamento, COUNT(*) AS total
                FROM etapa_processo
                WHERE status = 'EM_ANDAMENTO'
                GROUP BY departamento
            """)
        ).fetchall()

        return jsonify({
            "total":     row[0] or 0,
            "andamento": row[1] or 0,
            "concluidos":row[2] or 0,
            "cancelados":row[3] or 0,
            "porDept":   {r[0]: r[1] for r in dept_rows},
        })
    finally:
        db.close()


@bp.get("/<int:processo_id>")
@require_auth
def detalhe(processo_id):
    db = get_db()
    try:
        # Eager load completo: etapas + documentos em 1 query
        p = (
            db.query(models.ProcessoAdmissao)
            .options(
                joinedload(models.ProcessoAdmissao.candidatura)
                    .joinedload(models.Candidatura.job),
                selectinload(models.ProcessoAdmissao.etapas)
                    .selectinload(models.EtapaProcesso.documentos),
            )
            .filter_by(id=processo_id)
            .first()
        )
        if not p:
            return jsonify({"message": "Processo não encontrado"}), 404
        return jsonify(processo_to_dict(p))
    finally:
        db.close()


# ── Atualizar etapa ───────────────────────────────────────────

@bp.patch("/<int:processo_id>/etapas/<int:etapa_id>")
@require_auth
def atualizar_etapa(processo_id, etapa_id):
    data = request.get_json()
    db   = get_db()
    try:
        p = (
            db.query(models.ProcessoAdmissao)
            .options(
                joinedload(models.ProcessoAdmissao.candidatura)
                    .joinedload(models.Candidatura.job),
                selectinload(models.ProcessoAdmissao.etapas)
                    .selectinload(models.EtapaProcesso.documentos),
            )
            .filter_by(id=processo_id)
            .first()
        )
        if not p:
            return jsonify({"message": "Processo não encontrado"}), 404

        e = next((x for x in p.etapas if x.id == etapa_id), None)
        if not e:
            return jsonify({"message": "Etapa não encontrada"}), 404

        novo_status = data.get("status", "").upper()
        if novo_status not in ("APROVADO", "REPROVADO", "REENVIAR", "EM_ANDAMENTO", "NAO_APLICAVEL"):
            return jsonify({"message": "Status inválido"}), 400

        old_status = e.status
        etapa_nome = e.nome

        cand       = p.candidatura
        cand_email = cand.email
        cand_nome  = cand.full_name
        cand_cpf   = cand.cpf
        cand_cargo = cand.job.position if cand.job else "—"
        sp_url     = p.sharepoint_url

        e.status       = novo_status
        e.nota         = data.get("nota", e.nota)
        e.observacao   = data.get("observacao", e.observacao)
        e.responsavel  = request.username
        e.concluido_em = datetime.now(timezone.utc) if novo_status in ("APROVADO", "REPROVADO", "NAO_APLICAVEL") else None
        nota_texto     = e.nota

        if novo_status == "REPROVADO":
            p.status      = "CANCELADO"
            p.etapa_atual = f"Reprovado em: {etapa_nome}"
            db.commit()
        elif novo_status in ("APROVADO", "NAO_APLICAVEL"):
            _avancar_etapa(p, db)
        else:
            db.commit()

        audit.log(request.username, "ETAPA_ATUALIZADA", entity="processo",
                  entity_id=processo_id,
                  detail=f"{etapa_nome}: {old_status} → {novo_status}")

        if novo_status in ("APROVADO", "REPROVADO", "REENVIAR"):
            try:
                from email_service import notify_etapa_candidato
                class _Cand:
                    pass
                c = _Cand(); c.full_name = cand_nome; c.email = cand_email
                class _Job:
                    pass
                j = _Job(); j.position = cand_cargo; c.job = j
                notify_etapa_candidato(c, etapa_nome, novo_status, nota_texto)
            except Exception as ex:
                print(f"[EMAIL] Erro: {ex}")

        if not sp_url:
            try:
                from sharepoint_service import criar_pasta_colaborador
                result = criar_pasta_colaborador(cand_nome, cand_cpf)
                if result.get("url"):
                    db2 = get_db()
                    try:
                        proc = db2.query(models.ProcessoAdmissao).filter_by(id=processo_id).first()
                        if proc:
                            proc.sharepoint_url = result["url"]
                            db2.commit()
                    finally:
                        db2.close()
            except Exception as ex:
                print(f"[SHAREPOINT] Erro: {ex}")

        db.refresh(p)
        return jsonify(processo_to_dict(p))
    finally:
        db.close()


# ── Upload de documento ───────────────────────────────────────

@bp.post("/<int:processo_id>/etapas/<int:etapa_id>/documentos")
@require_auth
def upload_doc(processo_id, etapa_id):
    db = get_db()
    try:
        p = db.query(models.ProcessoAdmissao).filter_by(id=processo_id).first()
        if not p:
            return jsonify({"message": "Processo não encontrado"}), 404

        e = db.query(models.EtapaProcesso).filter_by(id=etapa_id, processo_id=processo_id).first()
        if not e:
            return jsonify({"message": "Etapa não encontrada"}), 404

        arquivo = request.files.get("arquivo")
        if not arquivo or not arquivo.filename:
            return jsonify({"message": "Arquivo obrigatório"}), 400

        # 1. Salva localmente imediatamente
        safe_name = arquivo.filename.replace(" ", "_")
        dest = os.path.join(UPLOAD_FOLDER, f"{processo_id}_{etapa_id}_{safe_name}")
        arquivo.save(dest)

        # 2. Registra o documento no banco SEM esperar SharePoint
        doc = models.DocumentoEtapa(
            etapa_id=etapa_id, nome=arquivo.filename, arquivo=dest,
            sharepoint_url=None,  # será atualizado em background
            enviado_por=request.username, status="PENDENTE",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id   = doc.id
        cand     = p.candidatura
        cand_nome = cand.full_name
        cand_cpf  = cand.cpf
        etapa_nome   = e.nome
        etapa_codigo = e.codigo
        sp_url_atual = p.sharepoint_url

        audit.log(request.username, "UPLOAD_DOC_ETAPA", entity="processo",
                  entity_id=processo_id, detail=f"Doc '{arquivo.filename}' na etapa '{etapa_nome}'")

        # 3. Upload SharePoint em background (não bloqueia a resposta)
        import threading
        def _upload_sp():
            try:
                from sharepoint_service import criar_pasta_colaborador, upload_documento
                cpf_c = cand_cpf.replace('.','').replace('-','')
                pasta = f"{cand_nome} - {cpf_c}"

                sp_url = None
                if not sp_url_atual:
                    result = criar_pasta_colaborador(cand_nome, cand_cpf)
                    if result.get("url"):
                        db2 = get_db()
                        try:
                            proc = db2.query(models.ProcessoAdmissao).filter_by(id=processo_id).first()
                            if proc:
                                proc.sharepoint_url = result["url"]
                                db2.commit()
                        finally:
                            db2.close()

                sp_url = upload_documento(dest, safe_name, pasta, sub_pasta=etapa_nome, codigo_etapa=etapa_codigo)
                if sp_url:
                    db3 = get_db()
                    try:
                        d = db3.query(models.DocumentoEtapa).filter_by(id=doc_id).first()
                        if d:
                            d.sharepoint_url = sp_url
                            db3.commit()
                        print(f"[SHAREPOINT] Upload concluído em background: {sp_url}")
                    finally:
                        db3.close()
            except Exception as ex:
                print(f"[SHAREPOINT] Upload background falhou: {ex}")

        threading.Thread(target=_upload_sp, daemon=True).start()

        # 4. Retorna imediatamente sem esperar SharePoint
        return jsonify(doc_to_dict(doc)), 201
    finally:
        db.close()


# ── Revisar documento ─────────────────────────────────────────

@bp.patch("/<int:processo_id>/etapas/<int:etapa_id>/documentos/<int:doc_id>")
@require_auth
def revisar_doc(processo_id, etapa_id, doc_id):
    data = request.get_json()
    db   = get_db()
    try:
        doc = db.query(models.DocumentoEtapa).filter_by(id=doc_id, etapa_id=etapa_id).first()
        if not doc:
            return jsonify({"message": "Documento não encontrado"}), 404
        novo = data.get("status", "").upper()
        if novo not in ("APROVADO", "REPROVADO", "REENVIAR"):
            return jsonify({"message": "Status inválido"}), 400
        doc.status     = novo
        doc.observacao = data.get("observacao", doc.observacao)
        db.commit()
        audit.log(request.username, "REVISAO_DOC", entity="processo",
                  entity_id=processo_id, detail=f"Doc '{doc.nome}': {novo}")
        return jsonify(doc_to_dict(doc))
    finally:
        db.close()


# ── Download de documento ─────────────────────────────────────

@bp.get("/<int:processo_id>/etapas/<int:etapa_id>/documentos/<int:doc_id>/download")
@require_auth
def download_doc(processo_id, etapa_id, doc_id):
    db = get_db()
    try:
        doc = db.query(models.DocumentoEtapa).filter_by(id=doc_id).first()
        if not doc or not doc.arquivo or not os.path.exists(doc.arquivo):
            return jsonify({"message": "Arquivo não encontrado"}), 404
        return send_file(doc.arquivo, as_attachment=True, download_name=doc.nome)
    finally:
        db.close()


# ── Diagnóstico SharePoint ─────────────────────────────────────

@bp.get("/sharepoint-test")
@require_auth
def sharepoint_test():
    try:
        from sharepoint_service import _get_token, _get_site_id, _get_drive_id, BASE_PATH
        import requests as req_lib
        token    = _get_token()
        site_id  = _get_site_id()
        drive_id = _get_drive_id(site_id)
        headers  = {"Authorization": f"Bearer {token}"}
        url      = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{BASE_PATH}"
        r        = req_lib.get(url, headers=headers, timeout=10)
        return jsonify({
            "token": "OK", "site_id": site_id[:20],
            "drive_id": drive_id[:20] if drive_id else None,
            "base_path_status": r.status_code, "base_path": BASE_PATH,
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
