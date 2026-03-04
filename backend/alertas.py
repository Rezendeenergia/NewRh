"""
Serviço de alertas automáticos — Rezende Energia
Roda diariamente às 08:00 (horário de Brasília).

Verifica candidatos parados na mesma etapa por mais de 3 dias
e envia e-mail de alerta para o RH.
"""
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import os

BRASILIA = pytz.timezone("America/Manaus")   # UTC-4 (Santarém não usa horário de verão)
LIMITE_DIAS = int(os.getenv("ALERTA_DIAS_PARADO", "3"))
EMAIL_RH    = os.getenv("MS_SENDER_EMAIL", "rh@rezendeenergia.com.br")


# ─────────────────────────────────────────────────────────────
# Lógica de verificação
# ─────────────────────────────────────────────────────────────

def verificar_candidatos_parados():
    """Busca candidatos PENDING parados há mais de LIMITE_DIAS sem movimentação."""
    print(f"[ALERTA] Verificando candidatos parados há mais de {LIMITE_DIAS} dias...")

    try:
        from database import SessionLocal
        import models

        db = SessionLocal()
        try:
            agora = datetime.now(timezone.utc).replace(tzinfo=None)
            limite = agora - timedelta(days=LIMITE_DIAS)

            # Candidatos PENDING (excluindo APPROVED e REJECTED) sem historico novo
            candidatos = (
                db.query(models.Candidatura)
                .filter(models.Candidatura.status == "PENDING")
                .all()
            )

            parados = []
            for c in candidatos:
                # Data da última movimentação (último status_history ou applied_at)
                ultimo_hist = (
                    db.query(models.StatusHistory)
                    .filter(models.StatusHistory.candidatura_id == c.id)
                    .order_by(models.StatusHistory.changed_at.desc())
                    .first()
                )

                if ultimo_hist:
                    ultima_mov = ultimo_hist.changed_at
                else:
                    ultima_mov = c.applied_at

                if not ultima_mov:
                    continue

                ultima_mov = ultima_mov.replace(tzinfo=None) if hasattr(ultima_mov, 'tzinfo') and ultima_mov.tzinfo else ultima_mov
                dias_parado = (agora - ultima_mov).days

                if dias_parado >= LIMITE_DIAS:
                    # Busca nome da vaga
                    job = db.query(models.Job).filter(models.Job.id == c.job_id).first()
                    parados.append({
                        "id":          c.id,
                        "nome":        c.full_name,
                        "email":       c.email,
                        "vaga":        job.position if job else "—",
                        "local":       job.location if job else "—",
                        "dias":        dias_parado,
                        "ultima_mov":  ultima_mov.strftime("%d/%m/%Y %H:%M"),
                        "etapa":       c.funnel_stage or c.status,
                        "email_resp":  job.email_resp if job else None,
                    })

            print(f"[ALERTA] {len(parados)} candidato(s) parado(s) encontrado(s).")

            if parados:
                _enviar_alerta_rh(parados)

        finally:
            db.close()

    except Exception as e:
        print(f"[ALERTA] Erro na verificação: {e}")
        import traceback
        traceback.print_exc()


def _enviar_alerta_rh(parados: list):
    """Envia e-mail de alerta ao RH com a lista de candidatos parados."""
    try:
        from email_service import send_email, _base_template, BRAND_COLOR

        total = len(parados)
        criticos = [p for p in parados if p["dias"] >= 7]   # vermelho
        atencao  = [p for p in parados if 3 <= p["dias"] < 7]  # amarelo

        def cor(dias):
            if dias >= 7:  return "#FF5252"
            if dias >= 5:  return "#FF8C42"
            return "#FFB830"

        linhas = ""
        for p in sorted(parados, key=lambda x: x["dias"], reverse=True):
            c = cor(p["dias"])
            etapa_pt = {
                "PENDING":        "Triagem",
                "TRIAGEM":        "Triagem",
                "TRIAGEM_OK":     "Triagem OK",
                "ENTREVISTA":     "Entrevista",
                "ENTREVISTA_OK":  "Entrevista OK",
                "APROVACAO_FINAL":"Aprovação Final",
            }.get(p["etapa"], p["etapa"])

            linhas += f"""
<tr style="border-bottom:1px solid rgba(255,255,255,.05);">
  <td style="padding:10px 16px;color:#fff;font-weight:600;">{p['nome']}</td>
  <td style="padding:10px 16px;color:#A8A8B8;">{p['vaga']} — {p['local']}</td>
  <td style="padding:10px 16px;color:#9AA3B2;font-size:13px;">{etapa_pt}</td>
  <td style="padding:10px 16px;color:#9AA3B2;font-size:12px;">{p['ultima_mov']}</td>
  <td style="padding:10px 16px;text-align:center;">
    <span style="background:{c}18;border:1px solid {c}55;color:{c};border-radius:20px;
                 padding:3px 12px;font-size:13px;font-weight:800;">{p['dias']}d</span>
  </td>
</tr>"""

        resumo_html = ""
        if criticos:
            resumo_html += (
                f'<div style="background:rgba(255,82,82,0.08);border:1px solid rgba(255,82,82,0.25);'
                f'border-left:3px solid #FF5252;border-radius:10px;padding:12px 18px;margin-bottom:10px;">'
                f'<strong style="color:#FF5252;">🚨 {len(criticos)} candidato(s) crítico(s)</strong>'
                f'<span style="color:#9AA3B2;font-size:13px;margin-left:8px;">parado(s) há 7 dias ou mais</span>'
                f'</div>'
            )
        if atencao:
            resumo_html += (
                f'<div style="background:rgba(255,184,48,0.08);border:1px solid rgba(255,184,48,0.25);'
                f'border-left:3px solid #FFB830;border-radius:10px;padding:12px 18px;margin-bottom:20px;">'
                f'<strong style="color:#FFB830;">⚠️ {len(atencao)} candidato(s) em atenção</strong>'
                f'<span style="color:#9AA3B2;font-size:13px;margin-left:8px;">parado(s) entre 3 e 6 dias</span>'
                f'</div>'
            )

        subject = f"⚠️ Alerta RH — {total} candidato(s) parado(s) há +{LIMITE_DIAS} dias"
        content = (
            f'<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">'
            f'⚠️ Candidatos Sem Movimentação</h2>'
            f'<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);'
            f'text-transform:uppercase;letter-spacing:2px;font-weight:600;">'
            f'Alerta automático diário — {datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")}</p>'
            + resumo_html +
            f'<p style="color:#A8A8B8;font-size:14px;margin:0 0 16px;">'
            f'Os seguintes candidatos estão parados na mesma etapa há <strong style="color:#fff;">'
            f'{LIMITE_DIAS}+ dias</strong> sem nenhuma movimentação:</p>'
            f'<div style="overflow-x:auto;">'
            f'<table cellpadding="0" cellspacing="0" width="100%" '
            f'style="border-collapse:collapse;font-size:13px;">'
            f'<thead><tr style="border-bottom:2px solid rgba(255,106,0,0.3);">'
            f'<th style="padding:10px 16px;text-align:left;color:{BRAND_COLOR};font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px;">Candidato</th>'
            f'<th style="padding:10px 16px;text-align:left;color:{BRAND_COLOR};font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px;">Vaga</th>'
            f'<th style="padding:10px 16px;text-align:left;color:{BRAND_COLOR};font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px;">Etapa</th>'
            f'<th style="padding:10px 16px;text-align:left;color:{BRAND_COLOR};font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px;">Última Mov.</th>'
            f'<th style="padding:10px 16px;text-align:center;color:{BRAND_COLOR};font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px;">Parado</th>'
            f'</tr></thead>'
            f'<tbody>' + linhas + f'</tbody>'
            f'</table></div>'
            f'<div style="border-top:1px solid rgba(255,255,255,.06);margin:24px 0;"></div>'
            f'<p style="color:#5A6478;font-size:12px;text-align:center;margin:0;">'
            f'Este e-mail é gerado automaticamente todo dia às 08h. '
            f'Acesse o portal para tomar as ações necessárias.</p>'
        )

        html = _base_template(subject, content)
        ok = send_email(EMAIL_RH, subject, html)
        if ok:
            print(f"[ALERTA] E-mail enviado para {EMAIL_RH} com {total} candidato(s).")
        else:
            print(f"[ALERTA] Falha ao enviar e-mail.")

    except Exception as e:
        print(f"[ALERTA] Erro ao enviar e-mail de alerta: {e}")
        import traceback
        traceback.print_exc()


# ─────────────────────────────────────────────────────────────
# Inicialização do scheduler
# ─────────────────────────────────────────────────────────────

_scheduler = None


def iniciar_scheduler():
    """Inicia o scheduler em background. Chamar uma vez no startup do app."""
    global _scheduler

    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone=BRASILIA)

    # Roda todos os dias às 08:00 horário de Manaus/Santarém (UTC-4)
    _scheduler.add_job(
        verificar_candidatos_parados,
        trigger=CronTrigger(hour=8, minute=0, timezone=BRASILIA),
        id="alerta_candidatos_parados",
        replace_existing=True,
        misfire_grace_time=3600,   # tolerância de 1h se o server estiver offline
    )

    _scheduler.start()
    print("[ALERTA] Scheduler iniciado — verificação diária às 08:00 (Santarém).")
