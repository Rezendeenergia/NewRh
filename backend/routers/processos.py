"""
Router de Processos de Admissão.
Gerencia o fluxo completo desde triagem até liberação para campo.
"""
from flask import Blueprint, request, jsonify, send_file
from database import get_db
from security import require_auth
from datetime import datetime, timezone
import models
import audit
import os

bp = Blueprint("processos", __name__, url_prefix="/api/processos")

UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", "admissao"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Definição das etapas do fluxo ────────────────────────────
ETAPAS_FLUXO = [
    # FASE 1 — Seleção
    {"ordem": 1,  "codigo": "TRIAGEM",              "nome": "Triagem",                        "departamento": "RH",         "tipo": "APROVACAO",   "prazo_dias": 2},
    {"ordem": 2,  "codigo": "ENTREVISTA",            "nome": "Entrevista",                     "departamento": "RH",         "tipo": "ENTREVISTA",  "prazo_dias": 5},
    {"ordem": 3,  "codigo": "APROVACAO_FINAL",       "nome": "Aprovação Final",                "departamento": "RH",         "tipo": "APROVACAO",   "prazo_dias": 1},
    # FASE 2 — Documentação e Admissão Formal
    {"ordem": 4,  "codigo": "ASO",                   "nome": "Agendamento ASO",                "departamento": "RH",         "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 5,  "codigo": "DP_EXTERNO",            "nome": "Admissão DP Externo",            "departamento": "DP_EXTERNO", "tipo": "DOCUMENTO",   "prazo_dias": 2},
    {"ordem": 6,  "codigo": "ASSINATURAS",           "nome": "Coleta de Assinaturas",          "departamento": "DP",         "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 7,  "codigo": "CADASTRO_GPM",          "nome": "Cadastro no GPM",                "departamento": "DP",         "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 8,  "codigo": "ACESSO_TI",             "nome": "Criação de Acesso TI/Sistemas",  "departamento": "TI",         "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 9,  "codigo": "BEMHOEFT",              "nome": "Inclusão Prontuário Bemhoeft",   "departamento": "DP",         "tipo": "DOCUMENTO",   "prazo_dias": 3},
    # FASE 3 — Equipamentos e Segurança
    {"ordem": 10, "codigo": "EPIS_UNIFORMES",        "nome": "Fornecimento EPIs e Uniformes",  "departamento": "SESMT",      "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 11, "codigo": "FORMACAO_NRS",          "nome": "Formação e Reciclagem NRs",      "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 5},
    {"ordem": 12, "codigo": "PRONTUARIO_SEGURANCA",  "nome": "Prontuário de Segurança",        "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 13, "codigo": "CERTIFICADOS_NR",       "nome": "Verificação Certificados NRs",   "departamento": "SESMT",      "tipo": "DOCUMENTO",   "prazo_dias": 2},
    {"ordem": 14, "codigo": "PROVA_DEEP",            "nome": "Prova DEEP",                     "departamento": "SESMT",      "tipo": "APROVACAO",   "prazo_dias": 3},
    # FASE 4 — Integração Final
    {"ordem": 15, "codigo": "GRAFICA_CRACHA",        "nome": "Confecção do Crachá",            "departamento": "RH",         "tipo": "CHECKLIST",   "prazo_dias": 1},
    {"ordem": 16, "codigo": "INTEGRACAO_EQUATORIAL", "nome": "Integração Equatorial",          "departamento": "RH",         "tipo": "DOCUMENTO",   "prazo_dias": 1},
    {"ordem": 17, "codigo": "LIBERADO_CAMPO",        "nome": "Liberação para Campo",           "departamento": "RH",         "tipo": "APROVACAO",   "prazo_dias": 1},
]

DEPT_LABEL = {
    "RH": "Recursos Humanos",
    "DP": "Departamento Pessoal",
    "DP_EXTERNO": "DP Externo",
    "SESMT": "SESMT",
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


def doc_to_dict(d):
    return {
        "id":             d.id,
        "nome":           d.nome,
        "arquivo":        d.arquivo,
        "sharepointUrl":  d.sharepoint_url,
        "enviadoPor":     d.enviado_por,
        "status":         d.status,
        "observacao":     d.observacao,
        "createdAt":      d.created_at.isoformat() if d.created_at else None,
    }


def processo_to_dict(p, include_etapas=True):
    c = p.candidatura
    return {
        "id":              p.id,
        "status":          p.status,
        "etapaAtual":      p.etapa_atual,
        "sharepointUrl":   p.sharepoint_url,
        "createdAt":       p.created_at.isoformat() if p.created_at else None,
        "updatedAt":       p.updated_at.isoformat() if p.updated_at else None,
        "candidatura": {
            "id":       c.id,
            "nome":     c.full_name,
            "cpf":      c.cpf,
            "email":    c.email,
            "phone":    c.phone,
            "cargo":    c.job.position,
            "local":    c.job.location,
        },
        "etapas": [etapa_to_dict(e) for e in p.etapas] if include_etapas else [],
        "progresso": _calc_progresso(p),
    }


def _calc_progresso(p):
    total     = len(p.etapas)
    concluidas = sum(1 for e in p.etapas if e.status == "APROVADO")
    return round(concluidas / total * 100) if total else 0


def _criar_etapas(processo_id, db):
    for e in ETAPAS_FLUXO:
        db.add(models.EtapaProcesso(
            processo_id=processo_id,
            ordem=e["ordem"], codigo=e["codigo"], nome=e["nome"],
            departamento=e["departamento"], tipo=e["tipo"],
            prazo_dias=e["prazo_dias"], status="PENDENTE",
        ))


def _avancar_etapa(processo, db):
    """Ativa a próxima etapa PENDENTE após uma aprovação."""
    pendentes = [e for e in processo.etapas if e.status == "PENDENTE"]
    if pendentes:
        prox = pendentes[0]
        prox.status      = "EM_ANDAMENTO"
        prox.iniciado_em = datetime.now(timezone.utc)
        processo.etapa_atual = prox.nome
    else:
        processo.status      = "CONCLUIDO"
        processo.etapa_atual = "Concluído"
    db.commit()


# ── Criar processo ao aprovar candidatura ─────────────────────

def criar_processo_para_candidatura(candidatura_id: int, db) -> models.ProcessoAdmissao:
    """Chamado automaticamente quando candidatura vai para APPROVED."""
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

    # Ativa a primeira etapa
    primeira = db.query(models.EtapaProcesso)\
        .filter_by(processo_id=processo.id, ordem=1).first()
    if primeira:
        primeira.status      = "EM_ANDAMENTO"
        primeira.iniciado_em = datetime.now(timezone.utc)

    db.commit()

    # Garante pasta no SharePoint (já pode existir desde a candidatura)
    try:
        cand = db.query(models.Candidatura).filter_by(id=candidatura_id).first()
        if cand:
            from sharepoint_service import criar_pasta_colaborador
            result = criar_pasta_colaborador(cand.full_name, cand.cpf)
            if result.get("url"):
                processo.sharepoint_url = result["url"]
                db.commit()
                print(f"[SHAREPOINT] Pasta confirmada: {result['url']}")
    except Exception as e:
        print(f"[SHAREPOINT] Erro ao confirmar pasta: {e}")

    return processo


# ── Listar processos ──────────────────────────────────────────

@bp.get("")
@require_auth
def listar():
    status_f = request.args.get("status", "").upper()
    dept_f   = request.args.get("departamento", "").upper()
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 20

    db = get_db()
    try:
        q = db.query(models.ProcessoAdmissao)
        if status_f:
            q = q.filter(models.ProcessoAdmissao.status == status_f)

        total = q.count()
        rows  = q.order_by(models.ProcessoAdmissao.updated_at.desc())\
                 .offset((page-1)*per_page).limit(per_page).all()

        # Filtra pela etapa ATUAL ativa do processo (não etapas futuras)
        if dept_f:
            def etapa_atual(p):
                # Pega a etapa EM_ANDAMENTO, ou se nenhuma, a primeira PENDENTE
                em_and = [e for e in p.etapas if e.status == "EM_ANDAMENTO"]
                if em_and:
                    return em_and[0]
                pendentes = sorted([e for e in p.etapas if e.status == "PENDENTE"], key=lambda e: e.ordem)
                return pendentes[0] if pendentes else None

            rows = [p for p in rows if etapa_atual(p) and etapa_atual(p).departamento == dept_f]

        return jsonify({
            "items":      [processo_to_dict(p) for p in rows],
            "total":      total,
            "page":       page,
            "totalPages": max(1, -(-total // per_page)),
        })
    finally:
        db.close()


@bp.get("/<int:processo_id>")
@require_auth
def detalhe(processo_id):
    db = get_db()
    try:
        p = db.query(models.ProcessoAdmissao).filter_by(id=processo_id).first()
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
        p = db.query(models.ProcessoAdmissao).filter_by(id=processo_id).first()
        if not p:
            return jsonify({"message": "Processo não encontrado"}), 404

        e = db.query(models.EtapaProcesso).filter_by(id=etapa_id, processo_id=processo_id).first()
        if not e:
            return jsonify({"message": "Etapa não encontrada"}), 404

        novo_status = data.get("status", "").upper()
        if novo_status not in ("APROVADO", "REPROVADO", "REENVIAR", "EM_ANDAMENTO", "NAO_APLICAVEL"):
            return jsonify({"message": "Status inválido"}), 400

        old_status   = e.status
        etapa_nome   = e.nome  # captura antes do commit

        # Captura dados do candidato ANTES do commit (evita detach)
        cand         = p.candidatura
        cand_email   = cand.email
        cand_nome    = cand.full_name
        cand_cpf     = cand.cpf
        cand_cargo   = cand.job.position if cand.job else "—"
        sp_url       = p.sharepoint_url

        e.status         = novo_status
        e.nota           = data.get("nota", e.nota)
        e.observacao     = data.get("observacao", e.observacao)
        e.responsavel    = request.username
        e.concluido_em   = datetime.now(timezone.utc) if novo_status in ("APROVADO","REPROVADO","NAO_APLICAVEL") else None
        nota_texto       = e.nota  # captura após set

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

        # Notifica candidato por e-mail
        if novo_status in ("APROVADO", "REPROVADO", "REENVIAR"):
            try:
                from email_service import notify_etapa_candidato
                # Recria objeto simples para não depender da sessão
                class _Cand:
                    pass
                c = _Cand()
                c.full_name = cand_nome
                c.email     = cand_email
                class _Job:
                    pass
                j = _Job()
                j.position  = cand_cargo
                c.job       = j
                notify_etapa_candidato(c, etapa_nome, novo_status, nota_texto)
                print(f"[EMAIL] Notificação '{etapa_nome}' → {novo_status} → {cand_email}")
            except Exception as ex:
                print(f"[EMAIL] Erro ao notificar candidato: {ex}")

        # Cria pasta SharePoint se ainda não existe
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
                            print(f"[SHAREPOINT] Pasta criada: {result['url']}")
                    finally:
                        db2.close()
                else:
                    print(f"[SHAREPOINT] Falhou: {result.get('erro')}")
            except Exception as ex:
                print(f"[SHAREPOINT] Erro ao criar pasta: {ex}")

        db.refresh(p)
        return jsonify(processo_to_dict(p))
    finally:
        db.close()


# ── Upload de documento em etapa ─────────────────────────────

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

        # Salva localmente
        safe_name = arquivo.filename.replace(" ", "_")
        dest = os.path.join(UPLOAD_FOLDER, f"{processo_id}_{etapa_id}_{safe_name}")
        arquivo.save(dest)

        # Upload para SharePoint
        sp_url = None
        try:
            from sharepoint_service import criar_pasta_colaborador, upload_documento
            cand  = p.candidatura
            cpf_c = cand.cpf.replace('.','').replace('-','')
            pasta = f"{cand.full_name} - {cpf_c}"

            # Garante que a pasta existe (cria se ainda não foi criada)
            if not p.sharepoint_url:
                print(f"[SHAREPOINT] Pasta não existe, criando agora...")
                result = criar_pasta_colaborador(cand.full_name, cand.cpf)
                if result.get("url"):
                    p.sharepoint_url = result["url"]
                    db.commit()
                    print(f"[SHAREPOINT] Pasta criada: {result['url']}")
                else:
                    print(f"[SHAREPOINT] Falha ao criar pasta: {result.get('erro')}")

            # Faz o upload mesmo que sharepoint_url ainda seja None (tenta de qualquer forma)
            sp_url = upload_documento(dest, safe_name, pasta, sub_pasta=e.nome)
            if sp_url:
                print(f"[SHAREPOINT] Upload OK: {sp_url}")
            else:
                print(f"[SHAREPOINT] Upload retornou None")
        except Exception as ex:
            print(f"[SHAREPOINT] Upload falhou: {ex}")

        doc = models.DocumentoEtapa(
            etapa_id=etapa_id,
            nome=arquivo.filename,
            arquivo=dest,
            sharepoint_url=sp_url,
            enviado_por=request.username,
            status="PENDENTE",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        audit.log(request.username, "UPLOAD_DOC_ETAPA", entity="processo",
                  entity_id=processo_id,
                  detail=f"Doc '{arquivo.filename}' na etapa '{e.nome}'")
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
                  entity_id=processo_id,
                  detail=f"Doc '{doc.nome}': {novo} — {doc.observacao or ''}")
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


# ── Stats para dashboard ──────────────────────────────────────

@bp.get("/sharepoint-test")
@require_auth
def sharepoint_test():
    """Endpoint de diagnóstico do SharePoint."""
    try:
        from sharepoint_service import _get_token, _get_site_id, _get_drive_id, BASE_PATH
        results = {}

        # Test token
        token = _get_token()
        results["token"] = "OK"

        # Test site
        site_id = _get_site_id()
        results["site_id"] = site_id[:20] + "..."

        # Test drive
        drive_id = _get_drive_id(site_id)
        results["drive_id"] = drive_id[:20] + "..." if drive_id else None

        # Test base path exists
        import requests, os
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{BASE_PATH}"
        r = requests.get(url, headers=headers, timeout=10)
        results["base_path_status"] = r.status_code
        results["base_path"] = BASE_PATH
        if r.status_code == 200:
            results["base_path_name"] = r.json().get("name")
        else:
            results["base_path_error"] = r.json()

        return jsonify(results)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@bp.get("/stats")
@require_auth
def stats():
    db = get_db()
    try:
        total       = db.query(models.ProcessoAdmissao).count()
        andamento   = db.query(models.ProcessoAdmissao).filter_by(status="EM_ANDAMENTO").count()
        concluidos  = db.query(models.ProcessoAdmissao).filter_by(status="CONCLUIDO").count()
        cancelados  = db.query(models.ProcessoAdmissao).filter_by(status="CANCELADO").count()

        # Etapas em andamento por departamento
        por_dept = {}
        etapas_ativas = db.query(models.EtapaProcesso).filter_by(status="EM_ANDAMENTO").all()
        for e in etapas_ativas:
            por_dept[e.departamento] = por_dept.get(e.departamento, 0) + 1

        return jsonify({
            "total":      total,
            "andamento":  andamento,
            "concluidos": concluidos,
            "cancelados": cancelados,
            "porDept":    por_dept,
        })
    finally:
        db.close()
