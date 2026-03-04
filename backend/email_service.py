"""
Serviço de e-mail — Rezende Energia
Usa Microsoft Graph API com OAuth2 (client credentials)
Não depende de SMTP AUTH nem Security Defaults
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Configuração ─────────────────────────────────────────────
TENANT_ID     = os.getenv("MS_TENANT_ID",     "")
CLIENT_ID     = os.getenv("MS_CLIENT_ID",     "")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")
SENDER_EMAIL  = os.getenv("MS_SENDER_EMAIL",  "rh@rezendeenergia.com.br")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED",    "false").lower() == "true"

GRAPH_URL     = "https://graph.microsoft.com/v1.0"
TOKEN_URL     = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

BRAND_COLOR = "#FF6A00"


# ── Token ─────────────────────────────────────────────────────
def _get_token() -> str:
    resp = requests.post(TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── Envio ─────────────────────────────────────────────────────
def send_email(to: str, subject: str, html: str, cc: list = None) -> bool:
    if not EMAIL_ENABLED:
        print(f"[EMAIL] Desabilitado — para: {to} | assunto: {subject}")
        return False

    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        print("[EMAIL] MS_TENANT_ID, MS_CLIENT_ID ou MS_CLIENT_SECRET não configurados.")
        return False

    try:
        token = _get_token()

        message = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": to}}],
            "from": {"emailAddress": {"address": SENDER_EMAIL,
                                      "name": "Rezende Energia — RH"}},
        }
        if cc:
            message["ccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in cc if addr
            ]

        payload = {
            "message": message,
            "saveToSentItems": False,
        }

        resp = requests.post(
            f"{GRAPH_URL}/users/{SENDER_EMAIL}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=20,
        )

        if resp.status_code == 202:
            print(f"[EMAIL] Enviado → {to} | {subject}")
            return True
        else:
            print(f"[EMAIL] Erro {resp.status_code}: {resp.text}")
            return False

    except Exception as e:
        print(f"[EMAIL] Erro ao enviar para {to}: {e}")
        return False


# ── Templates ─────────────────────────────────────────────────
def _base_template(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#0B0F14;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0B0F14;padding:40px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
      <tr>
        <td style="background:linear-gradient(135deg,#141820,#1C2230);
                   border:1px solid rgba(255,106,0,0.18);
                   border-bottom:3px solid {BRAND_COLOR};
                   border-radius:16px 16px 0 0;padding:32px 36px;text-align:center;">
          <div style="font-size:28px;font-weight:900;color:#fff;letter-spacing:-1px;">⚡ Rezende Energia</div>
          <div style="font-size:11px;color:rgba(255,255,255,0.35);letter-spacing:3px;text-transform:uppercase;margin-top:4px;">Portal de Carreiras</div>
        </td>
      </tr>
      <tr>
        <td style="background:#141820;border-left:1px solid rgba(255,255,255,0.06);
                   border-right:1px solid rgba(255,255,255,0.06);padding:36px 36px 28px;">
          {content}
        </td>
      </tr>
      <tr>
        <td style="background:#0F1318;border:1px solid rgba(255,255,255,0.05);
                   border-top:none;border-radius:0 0 16px 16px;
                   padding:20px 36px;text-align:center;">
          <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.25);line-height:1.6;">
            Rezende Construção e Manutenção Ltda · Santarém, PA<br>
            Este é um e-mail automático, não responda diretamente.
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _status_badge(status: str) -> str:
    configs = {
        "APPROVED": {"bg": "#0D2E1A", "border": "#2ECC71", "color": "#2ECC71", "icon": "✅", "label": "Aprovado"},
        "REJECTED": {"bg": "#2E0D0D", "border": "#FF5252", "color": "#FF5252", "icon": "❌", "label": "Não Aprovado"},
        "PENDING":  {"bg": "#2E1E06", "border": "#FFB830", "color": "#FFB830", "icon": "⏳", "label": "Em Análise"},
    }
    c = configs.get(status, configs["PENDING"])
    return f"""<div style="display:inline-block;background:{c['bg']};
            border:1px solid {c['border']};border-radius:40px;
            padding:8px 22px;margin:20px 0;">
      <span style="color:{c['color']};font-weight:700;font-size:15px;">
        {c['icon']}&nbsp;&nbsp;{c['label']}
      </span></div>"""


# ── Status changed ─────────────────────────────────────────────
def build_status_changed_email(candidatura, job) -> tuple[str, str]:
    status = candidatura.status
    nome   = candidatura.full_name.split()[0]
    cargo  = job.position
    local  = job.location

    messages = {
        "APPROVED": {
            "subject": f"✅ Parabéns! Sua candidatura para {cargo} foi aprovada",
            "headline": f"Boa notícia, {nome}!",
            "body": f"""
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 16px;">
  Sua candidatura para <strong style="color:#fff;">{cargo}</strong> em
  <strong style="color:#fff;">{local}</strong> foi <strong style="color:#2ECC71;">aprovada</strong>.
</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0;">
  Nossa equipe de RH entrará em contato em breve para informar os próximos passos.
</p>""",
        },
        "REJECTED": {
            "subject": f"Atualização sobre sua candidatura — {cargo}",
            "headline": f"Olá, {nome}",
            "body": f"""
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 16px;">
  Agradecemos o interesse na vaga de <strong style="color:#fff;">{cargo}</strong> em
  <strong style="color:#fff;">{local}</strong>.
</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0;">
  Após análise, não daremos continuidade à sua candidatura neste momento.
  Encorajamos você a acompanhar novas oportunidades no nosso portal. 💪
</p>""",
        },
        "PENDING": {
            "subject": f"Candidatura recebida — {cargo} | Rezende Energia",
            "headline": f"Candidatura registrada, {nome}!",
            "body": f"""
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 16px;">
  Recebemos sua candidatura para <strong style="color:#fff;">{cargo}</strong>
  em <strong style="color:#fff;">{local}</strong>.
</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0;">
  Nossa equipe irá analisar seu perfil e entrará em contato se avançar no processo.
</p>""",
        },
    }

    cfg = messages.get(status, messages["PENDING"])
    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">{cfg['headline']}</h2>
<p style="margin:0 0 8px;font-size:13px;color:rgba(255,106,0,0.8);text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Atualização da sua candidatura</p>
{_status_badge(status)}
{cfg['body']}
<div style="border-top:1px solid rgba(255,255,255,0.06);margin:28px 0;"></div>
<table cellpadding="0" cellspacing="0" width="100%">
  <tr><td style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
               border-radius:12px;padding:16px 20px;">
    <p style="margin:0 0 4px;font-size:10px;color:{BRAND_COLOR};font-weight:700;text-transform:uppercase;letter-spacing:2px;">Vaga</p>
    <p style="margin:0;font-size:15px;font-weight:700;color:#fff;">{cargo}</p>
    <p style="margin:4px 0 0;font-size:13px;color:#A8A8B8;">📍 {local}</p>
  </td></tr>
</table>"""

    return cfg["subject"], _base_template(cfg["subject"], content)


def build_new_application_email(candidatura, job) -> tuple[str, str]:
    subject = f"🔔 Nova candidatura: {candidatura.full_name} → {job.position}"
    rows = "".join(f"""
  <tr>
    <td style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
               border-radius:8px;padding:10px 16px;width:40%;font-size:11px;
               color:rgba(255,106,0,0.8);font-weight:700;text-transform:uppercase;letter-spacing:1.5px;">
      {lbl}</td>
    <td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);
               border-radius:8px;padding:10px 16px;color:#F4F5F7;font-size:14px;">
      {val or "—"}</td>
  </tr>""" for lbl, val in [
        ("Vaga",        job.position),
        ("Local",       job.location),
        ("E-mail",      candidatura.email),
        ("Telefone",    candidatura.phone),
        ("Formação",    candidatura.education),
        ("Experiência", candidatura.experience),
        ("Cidade",      candidatura.cidade_atual),
    ])

    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">Nova Candidatura Recebida</h2>
<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Portal de Carreiras</p>
<div style="background:rgba(255,106,0,0.06);border:1px solid rgba(255,106,0,0.18);
            border-left:3px solid {BRAND_COLOR};border-radius:12px;padding:18px 22px;margin-bottom:20px;">
  <p style="margin:0 0 4px;font-size:11px;color:{BRAND_COLOR};font-weight:700;text-transform:uppercase;letter-spacing:2px;">Candidato</p>
  <p style="margin:0;font-size:18px;font-weight:800;color:#fff;">{candidatura.full_name}</p>
</div>
<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:separate;border-spacing:0 8px;">
  {rows}
</table>
<div style="border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;"></div>
<p style="margin:0;font-size:13px;color:#5A6478;text-align:center;">
  Acesse o painel do gestor para revisar e atualizar o status.</p>"""

    return subject, _base_template(subject, content)


def build_invite_email(username: str, email: str, token: str, base_url: str) -> tuple[str, str]:
    link = f"{base_url}/definir-senha?token={token}"
    subject = "⚡ Seu acesso ao Portal de Carreiras — Rezende Energia"
    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">Bem-vindo ao Portal de Carreiras!</h2>
<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Convite de acesso</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 14px;">
  Olá, <strong style="color:#fff;">{username}</strong>! Você foi convidado para acessar o
  <strong style="color:#fff;">Portal de Carreiras da Rezende Energia</strong> como gestor.
</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 14px;">
  Clique no botão abaixo para definir sua senha e ativar seu acesso.
</p>
<div style="text-align:center;margin:30px 0;">
  <a href="{link}"
     style="display:inline-block;background:linear-gradient(135deg,#FF8C2A,#FF6A00,#E55A00);
            color:#000;font-weight:800;font-size:15px;text-decoration:none;
            padding:14px 36px;border-radius:10px;box-shadow:0 4px 20px rgba(255,106,0,0.4);">
    ⚡ Definir minha senha
  </a>
</div>
<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-radius:10px;padding:14px 18px;margin:24px 0;">
  <p style="margin:0 0 4px;font-size:11px;color:rgba(255,106,0,0.7);font-weight:700;text-transform:uppercase;letter-spacing:2px;">
    Ou copie o link</p>
  <p style="margin:0;font-size:12px;color:#5A6478;word-break:break-all;">{link}</p>
</div>
<div style="border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;"></div>
<p style="color:#5A6478;font-size:13px;line-height:1.6;margin:0;">
  ⚠️ Link válido por <strong style="color:#A8A8B8;">24 horas</strong>.<br>
  Se você não solicitou este acesso, ignore este e-mail.
</p>"""
    return subject, _base_template(subject, content)


# ── Funções de notificação ─────────────────────────────────────
def notify_status_changed(candidatura, job):
    if not candidatura.email:
        return
    subject, html = build_status_changed_email(candidatura, job)
    send_email(candidatura.email, subject, html)


def notify_new_application(candidatura, job):
    if not job.email_resp:
        return
    subject, html = build_new_application_email(candidatura, job)
    send_email(job.email_resp, subject, html)


def notify_invite(username: str, email: str, token: str, base_url: str):
    subject, html = build_invite_email(username, email, token, base_url)
    send_email(email, subject, html)


# ── Recuperação de senha ──────────────────────────────────────

def build_reset_email(username: str, token: str, base_url: str) -> tuple[str, str]:
    link = f"{base_url}/redefinir-senha?token={token}"
    subject = "🔑 Redefinição de senha — Portal Rezende Energia"

    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">Redefinir senha</h2>
<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);
          text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Portal de Carreiras</p>

<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 14px;">
  Olá, <strong style="color:#fff;">{username}</strong>!
</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 14px;">
  Recebemos uma solicitação para redefinir a senha da sua conta no
  <strong style="color:#fff;">Portal de Carreiras da Rezende Energia</strong>.
  Clique no botão abaixo para criar uma nova senha.
</p>

<div style="text-align:center;margin:30px 0;">
  <a href="{link}"
     style="display:inline-block;
            background:linear-gradient(135deg,#FF8C2A,#FF6A00,#E55A00);
            color:#000;font-weight:800;font-size:15px;
            text-decoration:none;padding:14px 36px;
            border-radius:10px;
            box-shadow:0 4px 20px rgba(255,106,0,0.4);">
    🔑 Redefinir minha senha
  </a>
</div>

<div style="background:rgba(255,255,255,0.03);
            border:1px solid rgba(255,255,255,0.07);
            border-radius:10px;padding:14px 18px;margin:24px 0;">
  <p style="margin:0 0 4px;font-size:11px;color:rgba(255,106,0,0.7);
            font-weight:700;text-transform:uppercase;letter-spacing:2px;">
    Ou copie o link</p>
  <p style="margin:0;font-size:12px;color:#5A6478;word-break:break-all;">{link}</p>
</div>

<div style="border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;"></div>

<p style="color:#5A6478;font-size:13px;line-height:1.6;margin:0;">
  ⚠️ Este link é válido por <strong style="color:#A8A8B8;">1 hora</strong>.<br>
  Se você não solicitou a redefinição, ignore este e-mail — sua senha permanece a mesma.
</p>"""

    html = _base_template(subject, content)
    return subject, html


def notify_password_reset(username: str, email: str, token: str, base_url: str):
    subject, html = build_reset_email(username, token, base_url)
    send_email(email, subject, html)


# ── Confirmação de candidatura para o candidato ───────────────

def build_confirmation_email(candidatura, job) -> tuple[str, str]:
    nome  = candidatura.full_name.split()[0]
    cargo = job.position
    local = job.location
    subject = f"✅ Candidatura recebida — {cargo} | Rezende Energia"

    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">
  Candidatura recebida, {nome}!
</h2>
<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);
          text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Confirmação de inscrição</p>

<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 16px;">
  Recebemos sua candidatura com sucesso! Nossa equipe de RH irá analisar
  seu perfil e entrará em contato caso você avance no processo seletivo.
</p>

<div style="background:rgba(255,106,0,0.06);border:1px solid rgba(255,106,0,0.18);
            border-left:3px solid {BRAND_COLOR};border-radius:12px;
            padding:18px 22px;margin:20px 0;">
  <p style="margin:0 0 4px;font-size:11px;color:{BRAND_COLOR};font-weight:700;
            text-transform:uppercase;letter-spacing:2px;">Vaga</p>
  <p style="margin:0;font-size:17px;font-weight:800;color:#fff;">{cargo}</p>
  <p style="margin:6px 0 0;font-size:13px;color:#A8A8B8;">📍 {local}</p>
</div>

<p style="color:#A8A8B8;font-size:14px;line-height:1.7;margin:16px 0 0;">
  Você pode acompanhar o status da sua candidatura a qualquer momento em:<br>
  <a href="#" style="color:{BRAND_COLOR};text-decoration:none;font-weight:600;">
    Portal Rezende Energia → Acompanhar candidatura
  </a>
</p>

<div style="border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;"></div>
<p style="color:#5A6478;font-size:13px;line-height:1.6;margin:0;">
  Fique atento ao seu e-mail — te avisaremos sobre qualquer atualização.<br>
  Obrigado pelo interesse em fazer parte do time Rezende Energia! ⚡
</p>"""

    return subject, _base_template(subject, content)


def notify_application_confirmation(candidatura, job):
    """Envia confirmação de candidatura para o próprio candidato."""
    if not candidatura.email:
        return
    subject, html = build_confirmation_email(candidatura, job)
    send_email(candidatura.email, subject, html)


# ── Notificações do Fluxo de Admissão ─────────────────────────

def build_etapa_email(candidatura, etapa_nome: str, status: str, nota: str = None) -> tuple[str, str]:
    """E-mail enviado ao candidato quando uma etapa é aprovada, reprovada ou pede reenvio."""
    nome    = candidatura.full_name
    cargo   = candidatura.job.position if candidatura.job else "—"

    status_info = {
        "APROVADO":  ("✅ Etapa Aprovada",    "#2ECC71", "Parabéns! Você avançou para a próxima etapa do processo."),
        "REPROVADO": ("❌ Processo Encerrado", "#FF5252", "Infelizmente seu processo de admissão foi encerrado nesta etapa."),
        "REENVIAR":  ("🔄 Documentação Necessária", "#FFB830", "Precisamos que você reenvie ou corrija um documento para continuar."),
    }
    titulo, cor, mensagem = status_info.get(status, ("ℹ️ Atualização", BRAND_COLOR, "Há uma atualização no seu processo."))

    nota_html = f"""
      <div style="background:#1C2230;border-left:3px solid {cor};border-radius:8px;padding:14px 18px;margin-top:16px;">
        <p style="font-size:13px;color:#9AA3B2;margin:0 0 4px;">Observação do responsável:</p>
        <p style="font-size:14px;color:#F4F5F7;margin:0;">{nota}</p>
      </div>""" if nota else ""

    subject = f"{titulo} — {etapa_nome} | {cargo}"
    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;background:#0B0F14;padding:40px 0;">
      <div style="max-width:560px;margin:0 auto;background:#141820;border-radius:16px;overflow:hidden;border:1px solid rgba(255,255,255,0.07);">
        <div style="background:linear-gradient(135deg,#FF6A00,#E55A00);padding:28px 32px;">
          <h1 style="font-size:22px;font-weight:900;color:#fff;margin:0;">⚡ Rezende Energia</h1>
          <p style="color:rgba(255,255,255,.8);font-size:13px;margin:4px 0 0;">Portal de Admissão</p>
        </div>
        <div style="padding:32px;">
          <div style="text-align:center;margin-bottom:24px;">
            <div style="font-size:36px;margin-bottom:8px;">{titulo.split()[0]}</div>
            <h2 style="font-size:20px;font-weight:800;color:#fff;margin:0 0 6px;">{titulo[2:].strip()}</h2>
            <p style="color:#9AA3B2;font-size:14px;margin:0;">Etapa: <strong style="color:{cor};">{etapa_nome}</strong></p>
          </div>
          <p style="color:#9AA3B2;font-size:14px;margin:0 0 6px;">Olá, <strong style="color:#fff;">{nome}</strong></p>
          <p style="color:#9AA3B2;font-size:14px;margin:0 0 16px;">Vaga: <strong style="color:#fff;">{cargo}</strong></p>
          <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:16px 20px;">
            <p style="color:#F4F5F7;font-size:14px;line-height:1.7;margin:0;">{mensagem}</p>
          </div>
          {nota_html}
          {"<div style='margin-top:20px;text-align:center;'><a href='https://newrh.onrender.com/acompanhar' style='background:linear-gradient(135deg,#FF8C2A,#FF6A00);color:#000;font-weight:700;padding:12px 28px;border-radius:8px;text-decoration:none;font-size:14px;'>Acompanhar Processo</a></div>" if status != "REPROVADO" else ""}
        </div>
        <div style="padding:16px 32px;border-top:1px solid rgba(255,255,255,.06);text-align:center;">
          <p style="color:#5A6478;font-size:12px;margin:0;">© 2026 Rezende Energia · Portal de Admissão</p>
        </div>
      </div>
    </div>"""
    return subject, html


def notify_etapa_candidato(candidatura, etapa_nome: str, status: str, nota: str = None):
    """Envia e-mail ao candidato sobre atualização de etapa."""
    try:
        subject, html = build_etapa_email(candidatura, etapa_nome, status, nota)
        ok = send_email(candidatura.email, subject, html)
        if ok:
            print(f"[EMAIL] Etapa '{etapa_nome}' → {status} enviado para {candidatura.email}")
        return ok
    except Exception as e:
        print(f"[EMAIL] Erro ao notificar etapa: {e}")
        return False


# ── Solicitações de Vaga ───────────────────────────────────────

EMAIL_TI = "Ingrid.silva@rezendeenergia.com.br"
EMAIL_RH = "rh@rezendeenergia.com.br"


def notify_solicitacao_rafael(sol, rafael_email: str, base_url: str):
    """Envia pedido de aprovação ao Rafael (TO) e cópia informativa ao TI (CC: Ingrid)."""
    token   = sol.approval_token
    revisar = f"{base_url}/revisar-solicitacao?token={token}"
    link_ap = f"{base_url}/api/solicitacoes/revisar?token={token}&decision=APROVADA"
    link_rj = f"{base_url}/api/solicitacoes/revisar?token={token}&decision=REJEITADA"

    subject = f"📋 Aprovação necessária: Solicitação de Vaga — {sol.position} ({sol.location})"

    rows = "".join(f"""  <tr>
    <td style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
               border-radius:8px;padding:10px 16px;width:38%;font-size:11px;
               color:rgba(255,106,0,0.8);font-weight:700;text-transform:uppercase;letter-spacing:1.5px;">{lbl}</td>
    <td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);
               border-radius:8px;padding:10px 16px;color:#F4F5F7;font-size:14px;">{val or "—"}</td>
  </tr>""" for lbl, val in [
        ("Cargo", sol.position),
        ("Localização", sol.location),
        ("Tipo de Vaga", sol.tipo),
        ("Nº de Vagas", str(sol.num_vagas)),
        ("Justificativa", sol.justificativa),
    ])

    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">Nova Solicitação de Vaga</h2>
<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Aguardando sua aprovação</p>
<div style="background:rgba(255,106,0,0.06);border:1px solid rgba(255,106,0,0.18);
            border-left:3px solid {BRAND_COLOR};border-radius:12px;padding:18px 22px;margin-bottom:20px;">
  <p style="margin:0 0 4px;font-size:11px;color:{BRAND_COLOR};font-weight:700;text-transform:uppercase;letter-spacing:2px;">Solicitante</p>
  <p style="margin:0;font-size:17px;font-weight:800;color:#fff;">{sol.solicitante_nome}</p>
  <p style="margin:4px 0 0;font-size:13px;color:#A8A8B8;">✉️ {sol.solicitante_email}</p>
</div>
<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:separate;border-spacing:0 8px;">
  {rows}
</table>
<div style="border-top:1px solid rgba(255,255,255,0.06);margin:28px 0;"></div>
<div style="text-align:center;margin:0 0 16px;">
  <a href="{revisar}"
     style="display:inline-block;background:linear-gradient(135deg,#FF8C2A,#FF6A00,#E55A00);
            color:#000;font-weight:800;font-size:15px;text-decoration:none;
            padding:14px 36px;border-radius:10px;box-shadow:0 4px 20px rgba(255,106,0,0.4);">
    📋 Ver Detalhes e Decidir
  </a>
</div>
<table cellpadding="0" cellspacing="0" width="100%" style="margin-top:12px;">
  <tr>
    <td style="padding:0 6px 0 0;">
      <a href="{link_ap}"
         style="display:block;text-align:center;background:#0D2E1A;border:2px solid #2ECC71;
                color:#2ECC71;font-weight:700;font-size:14px;text-decoration:none;
                padding:12px;border-radius:10px;">✅ Aprovar Diretamente</a>
    </td>
    <td style="padding:0 0 0 6px;">
      <a href="{link_rj}"
         style="display:block;text-align:center;background:#2E0D0D;border:2px solid #FF5252;
                color:#FF5252;font-weight:700;font-size:14px;text-decoration:none;
                padding:12px;border-radius:10px;">❌ Rejeitar Diretamente</a>
    </td>
  </tr>
</table>
<div style="border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;"></div>
<p style="color:#5A6478;font-size:12px;text-align:center;margin:0;">
  ℹ️ TI foi copiado neste e-mail apenas para acompanhamento.</p>"""

    html = _base_template(subject, content)
    send_email(rafael_email, subject, html, cc=[EMAIL_TI])


def notify_resultado_solicitacao(sol, base_url: str):
    """Notifica o gestor sobre o resultado, com CC obrigatório para RH."""
    aprovada  = sol.status == "APROVADA"
    icon      = "✅" if aprovada else "❌"
    status_pt = "Aprovada" if aprovada else "Rejeitada"
    cor       = "#2ECC71" if aprovada else "#FF5252"
    bg_cor    = "#0D2E1A" if aprovada else "#2E0D0D"

    mensagem = (
        f"Sua solicitação para a vaga de <strong style='color:#fff;'>{sol.position}</strong> "
        f"em <strong style='color:#fff;'>{sol.location}</strong> foi "
        f"<strong style='color:{cor};'>{status_pt.lower()}</strong>. "
        + ("A vaga já está publicada no portal." if aprovada
           else "Entre em contato com Rafael para mais informações.")
    )

    motivo_html = ""
    if not aprovada and sol.motivo_rejeicao:
        motivo_html = f"""
<div style="background:#1C2230;border-left:3px solid #FF5252;border-radius:8px;padding:14px 18px;margin-top:16px;">
  <p style="font-size:12px;color:#9AA3B2;margin:0 0 4px;">Motivo informado:</p>
  <p style="font-size:14px;color:#F4F5F7;margin:0;">{sol.motivo_rejeicao}</p>
</div>"""

    subject = f"{icon} Solicitação de Vaga {status_pt} — {sol.position} ({sol.location})"
    content = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:800;color:#fff;">{icon} Solicitação {status_pt}</h2>
<p style="margin:0 0 20px;font-size:13px;color:rgba(255,106,0,0.8);text-transform:uppercase;letter-spacing:2px;font-weight:600;">
  Resultado da análise</p>
<div style="background:{bg_cor};border:1px solid {cor};border-radius:12px;padding:18px 22px;margin:20px 0;text-align:center;">
  <span style="color:{cor};font-weight:800;font-size:18px;">{icon} Solicitação {status_pt}</span>
</div>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0 0 8px;">
  Olá, <strong style="color:#fff;">{sol.solicitante_nome}</strong>!</p>
<p style="color:#A8A8B8;font-size:15px;line-height:1.7;margin:0;">{mensagem}</p>
{motivo_html}
<div style="border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;"></div>
<table cellpadding="0" cellspacing="0" width="100%">
  <tr><td style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
               border-radius:12px;padding:16px 20px;">
    <p style="margin:0 0 4px;font-size:10px;color:{BRAND_COLOR};font-weight:700;text-transform:uppercase;letter-spacing:2px;">Vaga Solicitada</p>
    <p style="margin:0;font-size:15px;font-weight:700;color:#fff;">{sol.position}</p>
    <p style="margin:4px 0 0;font-size:13px;color:#A8A8B8;">📍 {sol.location} · {sol.num_vagas} vaga(s)</p>
  </td></tr>
</table>"""

    html = _base_template(subject, content)
    send_email(sol.solicitante_email, subject, html, cc=[EMAIL_RH])
