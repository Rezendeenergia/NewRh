"""
Serviço de alertas automáticos — Rezende Energia
Roda diariamente às 08:00 (horário de Santarém/Manaus, UTC-4).
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import os

BRASILIA    = ZoneInfo("America/Manaus")
LIMITE_DIAS = int(os.getenv("ALERTA_DIAS_PARADO", "3"))
EMAIL_TI  = "ti@rezendeenergia.com.br"
EMAIL_RH  = os.getenv("MS_SENDER_EMAIL", "rh@rezendeenergia.com.br")
EMAIL_GRP = [
    "RezendeRH@rezendeenergia.com.br",
    "RezendeDP@rezendeenergia.com.br",
    "rh@rezendeenergia.com.br",
]


def verificar_candidatos_parados():
    print(f"[ALERTA] Verificando candidatos parados há mais de {LIMITE_DIAS} dias...")
    try:
        from database import get_db
        import models

        db = get_db()
        try:
            agora = datetime.utcnow()

            candidatos = (
                db.query(models.Candidatura)
                .filter(models.Candidatura.status == "PENDING")
                .all()
            )

            parados = []
            for c in candidatos:
                ultimo_hist = (
                    db.query(models.StatusHistory)
                    .filter(models.StatusHistory.candidatura_id == c.id)
                    .order_by(models.StatusHistory.changed_at.desc())
                    .first()
                )
                ultima_mov = ultimo_hist.changed_at if ultimo_hist else c.applied_at
                if not ultima_mov:
                    continue
                if ultima_mov.tzinfo:
                    ultima_mov = ultima_mov.replace(tzinfo=None)
                dias_parado = (agora - ultima_mov).days
                if dias_parado >= LIMITE_DIAS:
                    job = db.query(models.Job).filter(models.Job.id == c.job_id).first()
                    parados.append({
                        "nome":       c.full_name,
                        "vaga":       job.position if job else "—",
                        "local":      job.location if job else "—",
                        "dias":       dias_parado,
                        "ultima_mov": ultima_mov.strftime("%d/%m/%Y %H:%M"),
                        "etapa":      c.funnel_stage or c.status,
                    })

            print(f"[ALERTA] {len(parados)} candidato(s) parado(s) encontrado(s).")
            if parados:
                _enviar_alerta_rh(parados)
        finally:
            db.close()
    except Exception as e:
        import traceback
        print(f"[ALERTA] Erro: {e}")
        traceback.print_exc()


def _enviar_alerta_rh(parados):
    try:
        from email_service import send_email, _base_template, BRAND_COLOR

        total    = len(parados)
        criticos = [p for p in parados if p["dias"] >= 7]
        atencao  = [p for p in parados if 3 <= p["dias"] < 7]

        ETAPA_PT = {
            "PENDING": "Triagem", "TRIAGEM": "Triagem", "TRIAGEM_OK": "Triagem OK",
            "ENTREVISTA": "Entrevista", "ENTREVISTA_OK": "Entrevista OK",
            "APROVACAO_FINAL": "Aprovação Final",
        }

        def cor(d):
            return "#FF5252" if d >= 7 else ("#FF8C42" if d >= 5 else "#FFB830")

        linhas = ""
        for p in sorted(parados, key=lambda x: x["dias"], reverse=True):
            c = cor(p["dias"])
            linhas += (
                "<tr style=\"border-bottom:1px solid rgba(255,255,255,.05);\">"
                "<td style=\"padding:10px 16px;color:#fff;font-weight:600;\">" + p["nome"] + "</td>"
                "<td style=\"padding:10px 16px;color:#A8A8B8;\">" + p["vaga"] + " — " + p["local"] + "</td>"
                "<td style=\"padding:10px 16px;color:#9AA3B2;\">" + ETAPA_PT.get(p["etapa"], p["etapa"]) + "</td>"
                "<td style=\"padding:10px 16px;color:#9AA3B2;font-size:12px;\">" + p["ultima_mov"] + "</td>"
                "<td style=\"padding:10px 16px;text-align:center;\">"
                "<span style=\"background:" + c + "18;border:1px solid " + c + "55;color:" + c + ";"
                "border-radius:20px;padding:3px 12px;font-size:13px;font-weight:800;\">" + str(p["dias"]) + "d</span>"
                "</td></tr>"
            )

        resumo = ""
        if criticos:
            resumo += ("<div style=\"background:rgba(255,82,82,0.08);border-left:3px solid #FF5252;"
                       "border-radius:10px;padding:12px 18px;margin-bottom:10px;\">"
                       "<strong style=\"color:#FF5252;\">🚨 " + str(len(criticos)) + " crítico(s)</strong>"
                       "<span style=\"color:#9AA3B2;margin-left:8px;\">7+ dias parado(s)</span></div>")
        if atencao:
            resumo += ("<div style=\"background:rgba(255,184,48,0.08);border-left:3px solid #FFB830;"
                       "border-radius:10px;padding:12px 18px;margin-bottom:20px;\">"
                       "<strong style=\"color:#FFB830;\">⚠️ " + str(len(atencao)) + " em atenção</strong>"
                       "<span style=\"color:#9AA3B2;margin-left:8px;\">3–6 dias parado(s)</span></div>")

        agora_str = datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")
        subject   = f"⚠️ Alerta RH — {total} candidato(s) parado(s) há +{LIMITE_DIAS} dias"
        content   = (
            "<h2 style=\"margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;\">⚠️ Candidatos Sem Movimentação</h2>"
            "<p style=\"margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);font-weight:600;\">Alerta automático — " + agora_str + "</p>"
            + resumo +
            "<p style=\"color:#A8A8B8;font-size:14px;margin:0 0 16px;\">Candidatos parados há <strong style=\"color:#fff;\">" + str(LIMITE_DIAS) + "+ dias</strong>:</p>"
            "<table cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"border-collapse:collapse;font-size:13px;\">"
            "<thead><tr style=\"border-bottom:2px solid rgba(255,106,0,0.3);\">"
            "<th style=\"padding:10px 16px;text-align:left;color:" + BRAND_COLOR + ";font-size:11px;\">Candidato</th>"
            "<th style=\"padding:10px 16px;text-align:left;color:" + BRAND_COLOR + ";font-size:11px;\">Vaga</th>"
            "<th style=\"padding:10px 16px;text-align:left;color:" + BRAND_COLOR + ";font-size:11px;\">Etapa</th>"
            "<th style=\"padding:10px 16px;text-align:left;color:" + BRAND_COLOR + ";font-size:11px;\">Última Mov.</th>"
            "<th style=\"padding:10px 16px;text-align:center;color:" + BRAND_COLOR + ";font-size:11px;\">Parado</th>"
            "</tr></thead><tbody>" + linhas + "</tbody></table>"
        )
        html = _base_template(subject, content)
        ok   = send_email(EMAIL_TI, subject, html, cc=EMAIL_GRP)
        print(f"[ALERTA] E-mail {'enviado' if ok else 'FALHOU'} → {EMAIL_RH}")
    except Exception as e:
        import traceback
        print(f"[ALERTA] Erro ao enviar e-mail: {e}")
        traceback.print_exc()


_scheduler = None


def iniciar_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="America/Manaus")
    _scheduler.add_job(
        verificar_candidatos_parados,
        trigger=CronTrigger(hour=8, minute=0, timezone="America/Manaus"),
        id="alerta_candidatos_parados",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    print("[ALERTA] Scheduler iniciado — verificação diária às 08:00 (Santarém).")
