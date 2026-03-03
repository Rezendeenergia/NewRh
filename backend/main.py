from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from database import engine, SessionLocal, Base
from security import hash_password
from extensions import limiter
import models
import os
import webbrowser
import threading

load_dotenv()

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

from routers import auth, jobs, candidaturas, processos, solicitacoes
app.register_blueprint(auth.bp)
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
