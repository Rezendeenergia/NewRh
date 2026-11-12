"""
Rotas da CIPA (Portal do Colaborador): candidatura, votação e resultado.

O processo se repete todo ano, sempre nessa ordem (campo `fase` de
CipaGestao, a gestão/ciclo atual):

  INSCRICAO_ABERTA -> INSCRICAO_FECHADA -> VOTACAO_ABERTA
  -> VOTACAO_FECHADA -> RESULTADO

Públicas (sem login):
  GET  /api/cipa/gestao            — fase atual da gestão (pra a página
                                      pública saber qual tela mostrar)
  POST /api/cipa                   — candidatura (só quando INSCRICAO_ABERTA)
  GET  /api/cipa/cargos            — lista de cargos (lista suspensa)
  GET  /api/cipa/votacao/candidatos— lista de candidatos pra votar (só
                                      quando VOTACAO_ABERTA)
  POST /api/cipa/votacao/votar     — voto secreto (só quando VOTACAO_ABERTA)
  GET  /api/cipa/resultado         — ranking (só depois de VOTACAO_FECHADA)

Protegidas (gestão da CIPA — só ROLE_ADMIN, require_role_admin):
  GET  /api/cipa                   — lista todas as candidaturas
  GET  /api/cipa/pdf               — PDF de todas as candidaturas (auditoria)
  POST /api/cipa/gestao/fase       — avança/define a fase da gestão atual
  POST /api/cipa/gestao/vagas      — define o nº de vagas (membros titulares)
  POST /api/cipa/gestao/nova       — cria uma gestão nova (próximo ano)
  POST /api/cipa/eleitos/computar  — marca os mais votados como eleitos
  POST /api/cipa/eleitos/papel     — define o papel de um eleito (presidente etc.)
"""
from flask import Blueprint, request, jsonify, send_file
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from database import get_db
from security import require_role_admin
from extensions import limiter
import models
import os as _os

bp = Blueprint("cipa", __name__, url_prefix="/api/cipa")

FASES = ["INSCRICAO_ABERTA", "INSCRICAO_FECHADA", "VOTACAO_ABERTA", "VOTACAO_FECHADA", "RESULTADO"]


def _to_dict(c):
    return {
        "id":        c.id,
        "nome":      c.nome,
        "matricula": c.matricula,
        "cargo":     c.cargo,
        "motivo":    c.motivo,
        "gestao":    c.gestao,
        "votos":     c.votos,
        "eleito":    c.eleito,
        "papel":     c.papel,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


def _gestao_para_dict(g):
    return {
        "ano":          g.ano,
        "fase":         g.fase,
        "numeroVagas":  g.numero_vagas,
    }


def _get_gestao_ativa(db):
    """Pega a gestão ativa (a mais recente); cria uma com o ano atual se
    ainda não existir nenhuma (primeira vez que o sistema roda)."""
    g = (
        db.query(models.CipaGestao)
        .filter_by(ativa=True)
        .order_by(models.CipaGestao.id.desc())
        .first()
    )
    if g:
        return g
    ano_atual = str(datetime.now(timezone.utc).year)
    g = models.CipaGestao(ano=ano_atual, fase="INSCRICAO_ABERTA", ativa=True)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


# ── Fase atual da gestão (público) ───────────────────────────────

@bp.get("/gestao")
def gestao_atual():
    db = get_db()
    try:
        g = _get_gestao_ativa(db)
        return jsonify(_gestao_para_dict(g))
    finally:
        db.close()


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

    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        if gestao.fase != "INSCRICAO_ABERTA":
            return jsonify({"message": "As inscrições para a CIPA não estão abertas no momento."}), 403

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

        from colaboradores_service import (
            validar_colaborador_ativo,
            listar_cargos,
            _normalizar_nome,
            _normalizar_matricula,
        )

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

        # Candidatura é única por pessoa em cada gestão: confere antes (mensagem
        # mais clara pro usuário) e também trava no banco (uq_cipa_candidatura_gestao_matricula)
        # pra não ter condição de corrida entre dois envios ao mesmo tempo.
        matricula_norm = _normalizar_matricula(matricula)
        ja_existe = (
            db.query(models.CipaCandidatura)
            .filter_by(gestao=gestao.ano, matricula_norm=matricula_norm)
            .first()
        )
        if ja_existe:
            return jsonify({"message": "Você já enviou uma candidatura à CIPA nesta gestão."}), 409

        candidatura = models.CipaCandidatura(
            nome           = nome,
            matricula      = matricula,
            matricula_norm = matricula_norm,
            cargo          = cargo,
            motivo         = motivo,
            gestao         = gestao.ano,
        )
        db.add(candidatura)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return jsonify({"message": "Você já enviou uma candidatura à CIPA nesta gestão."}), 409
        db.refresh(candidatura)

        try:
            from email_service import send_email
            from cipa_pdf import gerar_pdf_candidaturas
            dest = _os.getenv("RH_EMAIL", "rh@rezendeenergia.com.br")
            pdf_buffer = gerar_pdf_candidaturas([candidatura])
            send_email(
                dest,
                f"[NewRH] Nova candidatura à CIPA — {candidatura.nome}",
                f"""
                <h2>Nova candidatura à CIPA (gestão {candidatura.gestao})</h2>
                <p><b>Nome:</b> {candidatura.nome}</p>
                <p><b>Matrícula:</b> {candidatura.matricula}</p>
                <p><b>Cargo:</b> {candidatura.cargo}</p>
                <p><b>Por que quer participar:</b><br>{candidatura.motivo}</p>
                <p>O comprovante desta candidatura está em anexo (PDF).</p>
                """,
                attachments=[{
                    "name": f"comprovante-cipa-{candidatura.id}.pdf",
                    "content": pdf_buffer.getvalue(),
                    "content_type": "application/pdf",
                }],
            )
        except Exception as e:
            print(f"[CIPA] Erro e-mail: {e}")

        return jsonify(_to_dict(candidatura)), 201
    finally:
        db.close()


# ── Votação pública ──────────────────────────────────────────────

@bp.get("/votacao/candidatos")
def votacao_candidatos():
    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        if gestao.fase != "VOTACAO_ABERTA":
            return jsonify({"message": "A votação da CIPA não está aberta no momento.", "candidatos": []}), 403
        itens = (
            db.query(models.CipaCandidatura)
            .filter_by(gestao=gestao.ano)
            .order_by(models.CipaCandidatura.nome)
            .all()
        )
        return jsonify({"candidatos": [{"id": c.id, "nome": c.nome, "cargo": c.cargo} for c in itens]})
    finally:
        db.close()


@bp.post("/votacao/votar")
@limiter.limit("10 per hour")
def votacao_votar():
    data = request.get_json() or {}

    for field in ["nome", "matricula", "candidaturaId"]:
        if not data.get(field) and data.get(field) != 0:
            return jsonify({"message": f"Campo obrigatório: {field}"}), 400

    nome      = " ".join(str(data["nome"]).strip().upper().split())
    matricula = str(data["matricula"]).strip()

    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        if gestao.fase != "VOTACAO_ABERTA":
            return jsonify({"message": "A votação da CIPA não está aberta no momento."}), 403

        candidatura = (
            db.query(models.CipaCandidatura)
            .filter_by(id=data["candidaturaId"], gestao=gestao.ano)
            .first()
        )
        if not candidatura:
            return jsonify({"message": "Candidato inválido."}), 400

        from colaboradores_service import validar_colaborador_ativo, _normalizar_matricula

        try:
            status_colab = validar_colaborador_ativo(nome, matricula)
        except Exception as e:
            print(f"[CIPA] Erro ao validar colaborador (voto): {e}")
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

        # Voto secreto (NR-5): só guarda que essa matrícula já votou nessa
        # gestão, sem nenhuma ligação com o candidato escolhido.
        votante = models.CipaVotante(
            gestao         = gestao.ano,
            matricula_norm = _normalizar_matricula(matricula),
        )
        db.add(votante)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return jsonify({"message": "Você já votou nessa gestão da CIPA."}), 409

        db.query(models.CipaCandidatura).filter_by(id=candidatura.id).update(
            {"votos": models.CipaCandidatura.votos + 1}
        )
        db.commit()

        return jsonify({"message": "Voto registrado com sucesso."}), 201
    finally:
        db.close()


# ── Resultado / ranking (público depois que a votação fecha) ────

@bp.get("/resultado")
def resultado():
    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        if gestao.fase not in ("VOTACAO_FECHADA", "RESULTADO"):
            return jsonify({"message": "O resultado ainda não foi divulgado.", "ranking": []}), 403
        itens = (
            db.query(models.CipaCandidatura)
            .filter_by(gestao=gestao.ano)
            .order_by(models.CipaCandidatura.votos.desc(), models.CipaCandidatura.id.asc())
            .all()
        )
        ranking = [
            {
                "posicao": i + 1,
                "nome":    c.nome,
                "cargo":   c.cargo,
                "votos":   c.votos,
                "eleito":  c.eleito,
                "papel":   c.papel,
            }
            for i, c in enumerate(itens)
        ]
        return jsonify({
            "fase":        gestao.fase,
            "numeroVagas": gestao.numero_vagas,
            "ranking":     ranking,
        })
    finally:
        db.close()


# ── Listagem (gestores) ──────────────────────────────────────────

@bp.get("")
@require_role_admin
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


# ── PDF de todas as candidaturas (auditoria) ─────────────────────

@bp.get("/pdf")
@require_role_admin
def exportar_pdf():
    gestao_filtro = request.args.get("gestao", "").strip()
    db = get_db()
    try:
        query = db.query(models.CipaCandidatura)
        if gestao_filtro:
            query = query.filter_by(gestao=gestao_filtro)
        itens = query.order_by(models.CipaCandidatura.created_at.asc()).all()

        from cipa_pdf import gerar_pdf_candidaturas
        buffer = gerar_pdf_candidaturas(itens)

        nome_arquivo = f"candidaturas-cipa-{gestao_filtro or 'todas'}.pdf"
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=nome_arquivo,
        )
    finally:
        db.close()


# ── Administração da gestão (fase, vagas, nova gestão) ───────────

@bp.post("/gestao/fase")
@require_role_admin
def gestao_definir_fase():
    data = request.get_json() or {}
    fase = str(data.get("fase") or "").strip().upper()
    if fase not in FASES:
        return jsonify({"message": f"Fase inválida. Use uma de: {', '.join(FASES)}"}), 400

    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        gestao.fase = fase
        db.commit()
        return jsonify(_gestao_para_dict(gestao))
    finally:
        db.close()


@bp.post("/gestao/vagas")
@require_role_admin
def gestao_definir_vagas():
    data = request.get_json() or {}
    try:
        numero_vagas = int(data.get("numeroVagas"))
        if numero_vagas < 1:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"message": "Informe um número de vagas válido (maior que zero)."}), 400

    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        gestao.numero_vagas = numero_vagas
        db.commit()
        return jsonify(_gestao_para_dict(gestao))
    finally:
        db.close()


@bp.post("/gestao/nova")
@require_role_admin
def gestao_nova():
    data = request.get_json() or {}
    ano = str(data.get("ano") or "").strip()
    if not ano:
        return jsonify({"message": "Informe o ano da nova gestão."}), 400

    db = get_db()
    try:
        existente = db.query(models.CipaGestao).filter_by(ano=ano).first()
        if existente:
            return jsonify({"message": f"Já existe uma gestão {ano}."}), 400

        db.query(models.CipaGestao).filter_by(ativa=True).update({"ativa": False})
        nova = models.CipaGestao(ano=ano, fase="INSCRICAO_ABERTA", ativa=True)
        db.add(nova)
        db.commit()
        db.refresh(nova)
        return jsonify(_gestao_para_dict(nova)), 201
    finally:
        db.close()


# ── Eleitos: computar ranking e definir papéis ───────────────────

@bp.post("/eleitos/computar")
@require_role_admin
def eleitos_computar():
    db = get_db()
    try:
        gestao = _get_gestao_ativa(db)
        if gestao.fase not in ("VOTACAO_FECHADA", "RESULTADO"):
            return jsonify({"message": "Feche a votação antes de computar os eleitos."}), 400
        if not gestao.numero_vagas:
            return jsonify({"message": "Defina o número de vagas da gestão antes de computar os eleitos."}), 400

        itens = (
            db.query(models.CipaCandidatura)
            .filter_by(gestao=gestao.ano)
            .order_by(models.CipaCandidatura.votos.desc(), models.CipaCandidatura.id.asc())
            .all()
        )
        for i, c in enumerate(itens):
            c.eleito = i < gestao.numero_vagas
        db.commit()

        return jsonify({"message": f"{min(gestao.numero_vagas, len(itens))} candidato(s) marcado(s) como eleito(s)."})
    finally:
        db.close()


@bp.post("/eleitos/papel")
@require_role_admin
def eleitos_definir_papel():
    data = request.get_json() or {}
    candidatura_id = data.get("candidaturaId")
    papel = str(data.get("papel") or "").strip() or None

    db = get_db()
    try:
        candidatura = db.query(models.CipaCandidatura).filter_by(id=candidatura_id).first()
        if not candidatura:
            return jsonify({"message": "Candidatura não encontrada."}), 404
        if not candidatura.eleito:
            return jsonify({"message": "Só é possível definir papel para um candidato eleito."}), 400

        candidatura.papel = papel
        db.commit()
        return jsonify(_to_dict(candidatura))
    finally:
        db.close()
