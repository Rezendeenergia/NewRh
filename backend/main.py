from flask import Flask, jsonify, send_from_directory, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
import time
from database import engine, SessionLocal, Base
from security import hash_password
from extensions import limiter
import models
import os
import webbrowser
import threading

load_dotenv()

# ── Cache helper ──────────────────────────────────────────────
def cache_for(seconds):
    """Adiciona Cache-Control aos endpoints mais chamados."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            resp = make_response(f(*args, **kwargs))
            resp.headers["Cache-Control"] = f"public, max-age={seconds}"
            return resp
        return decorated
    return decorator

# Inicia scheduler de alertas automáticos (lazy — não bloqueia startup)
def _start_scheduler():
    try:
        from alertas import iniciar_scheduler
        iniciar_scheduler()
    except Exception as e:
        print(f"[ALERTA] Falha ao iniciar scheduler: {e}")

import threading as _threading
_threading.Thread(target=_start_scheduler, daemon=True).start()

# Inicializa o DB de forma lazy (não bloqueia o startup)
_db_initialized = False

def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        try:
            Base.metadata.create_all(bind=engine)
            create_default_user()
            _db_initialized = True
        except Exception as e:
            print(f"[DB] Erro na inicialização: {e}")

# Caminho para a pasta frontend (um nível acima de backend/)
FRONTEND_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_FOLDER, static_url_path="")
CORS(app)

@app.after_request
def no_cache_js_html(response):
    """Força browser a sempre buscar JS e HTML atualizados."""
    if response.content_type and any(t in response.content_type for t in
            ['javascript', 'text/html']):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Compressão gzip automática em todas as respostas (reduz ~70% no tamanho)
from flask_compress import Compress
Compress(app)
app.config["COMPRESS_MIMETYPES"] = [
    "application/json", "text/html", "text/css",
    "application/javascript", "text/javascript",
]
app.config["COMPRESS_LEVEL"] = 6
app.config["COMPRESS_MIN_SIZE"] = 500

@app.before_request
def init_db_once():
    ensure_db_initialized()

@app.route("/health")
def health():
    return "ok", 200

# Serve o index.html na raiz
@app.route("/")
def index():
    return send_from_directory(FRONTEND_FOLDER, "index.html")

# Serve a página de ativação de conta
@app.route("/definir-senha")
def ativar():
    return send_from_directory(FRONTEND_FOLDER, "ativar.html")

# Serve a página de redefinição de senha
@app.route("/redefinir-senha")
def redefinir_senha():
    return send_from_directory(FRONTEND_FOLDER, "redefinir-senha.html")

# Serve a página de admissão
@app.route("/admissao")
def admissao():
    return send_from_directory(FRONTEND_FOLDER, "admissao.html")

@app.route("/admissoes")
def admissoes():
    return send_from_directory(FRONTEND_FOLDER, "admissoes.html")

# Serve a página de acompanhamento de candidatura
@app.route("/acompanhar")
def acompanhar():
    return send_from_directory(FRONTEND_FOLDER, "acompanhar.html")


# Inicializa o limiter com o app
limiter.init_app(app)

@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify({
        "message": "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
    }), 429


@app.route("/api/alertas/testar")
def testar_alerta():
    """Dispara a verificação de candidatos parados imediatamente (para teste)."""
    from alertas import verificar_candidatos_parados
    verificar_candidatos_parados()
    return jsonify({"message": "Verificação executada — veja os logs do servidor."})


@app.route("/api/email-test")
def email_test():
    """Diagnóstico — verifica configuração de e-mail sem enviar nada."""
    import email_service as es
    return jsonify({
        "email_enabled":    es.EMAIL_ENABLED,
        "sender":           es.SENDER_EMAIL,
        "tenant_id_ok":     bool(es.TENANT_ID),
        "client_id_ok":     bool(es.CLIENT_ID),
        "client_secret_ok": bool(es.CLIENT_SECRET),
        "token_url":        es.TOKEN_URL,
    })


@app.route("/api/email-test-send")
def email_test_send():
    """Diagnóstico — tenta buscar token OAuth e envia e-mail real de teste."""
    import email_service as es

    result = {
        "email_enabled":    es.EMAIL_ENABLED,
        "sender":           es.SENDER_EMAIL,
        "token_status":     None,
        "token_error":      None,
        "send_status":      None,
        "send_error":       None,
    }

    if not es.EMAIL_ENABLED:
        result["send_error"] = "EMAIL_ENABLED=false"
        return jsonify(result)

    try:
        token = es._get_token()
        result["token_status"] = "OK"
    except Exception as e:
        result["token_status"] = "ERRO"
        result["token_error"]  = str(e)
        return jsonify(result)

    try:
        ok = es.send_email(
            es.SENDER_EMAIL,
            "Teste de E-mail — NewRH Rezende Energia",
            "<h2>E-mail de teste funcionando!</h2>"
        )
        result["send_status"] = "OK" if ok else "FALHOU (status != 202)"
    except Exception as e:
        result["send_status"] = "ERRO"
        result["send_error"]  = str(e)

    return jsonify(result)

from routers import auth, jobs, candidaturas, processos, solicitacoes
app.register_blueprint(auth.bp)

# Microsoft SSO
from auth_microsoft import bp_ms
app.register_blueprint(bp_ms, url_prefix="/api/auth/microsoft")

# Portal do Candidato
from candidato_auth import bp_cand
app.register_blueprint(bp_cand, url_prefix="/api/candidato")
app.register_blueprint(jobs.bp)
app.register_blueprint(candidaturas.bp)
app.register_blueprint(processos.bp)
app.register_blueprint(solicitacoes.bp)

@app.route("/revisar-solicitacao")
def revisar_solicitacao():
    return send_from_directory(FRONTEND_FOLDER, "revisar-solicitacao.html")


def create_default_user():
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add(models.User(
                username="admin",
                password=hash_password("1234"),
                role="ROLE_ADMIN",
            ))
            db.commit()
            print("Usuário padrão criado → admin / 1234")
    finally:
        db.close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"Servidor rodando em http://localhost:{port}")

    # Abre o navegador automaticamente (só na primeira inicialização)
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        def open_browser():
            webbrowser.open(f"http://localhost:{port}")
        threading.Timer(1.2, open_browser).start()

    app.run(host="0.0.0.0", port=port, debug=True)


# ── Pasta Digital do Colaborador ──────────────────────────────
@app.route("/candidato/definir-senha")
def candidato_definir_senha():
    """Página para o candidato definir sua senha via token do e-mail."""
    return send_from_directory(FRONTEND_FOLDER, "definir-senha-candidato.html")


@app.route("/pasta-colaborador")
def pasta_colaborador_page():
    return send_from_directory(FRONTEND_FOLDER, "pasta-colaborador.html")


@app.route("/api/pasta-colaborador/estrutura")
def pasta_estrutura():
    """Retorna a estrutura oficial de pastas do colaborador."""
    from pasta_colaborador import ESTRUTURA_PASTA_COLABORADOR
    return jsonify(ESTRUTURA_PASTA_COLABORADOR)


@app.route("/api/pasta-colaborador/flat")
def pasta_flat():
    """Retorna lista plana para uso em checklist de UI."""
    from pasta_colaborador import get_estrutura_flat
    return jsonify(get_estrutura_flat())
