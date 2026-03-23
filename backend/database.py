from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import ssl
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")


def _parse_db_url(url: str) -> str:
    """
    Converte a URL para pg8000 e resolve o @ na senha (ex: Rezende@2025).
    Usa rfind para pegar o @ real que separa credenciais do host.
    """
    if not url:
        return url

    # Força driver pg8000
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://", "postgresql+pg8000://"):
        if url.startswith(prefix):
            url = "postgresql+pg8000://" + url[len(prefix):]
            break

    # Remove querystring existente
    url = url.split("?")[0]

    # Localiza o @ mais à direita (separador real de credenciais/host)
    scheme_end = url.index("://") + 3
    at_pos = url.rfind("@")

    if at_pos > scheme_end:
        credentials = url[scheme_end:at_pos]
        hostpart    = url[at_pos + 1:]

        # URL-encode o @ dentro da senha
        colon_pos = credentials.find(":")
        if colon_pos != -1:
            user     = credentials[:colon_pos]
            password = credentials[colon_pos + 1:].replace("@", "%40")
            credentials = f"{user}:{password}"

        url = f"postgresql+pg8000://{credentials}@{hostpart}"

    return url


database_url = _parse_db_url(raw_url)

# pg8000 requer SSL como objeto de contexto, não como string
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

host = database_url.split("@")[1].split("/")[0] if "@" in database_url else "?"
print(f"[DB] Conectando em: {host}")

engine = create_engine(
    database_url,
    connect_args={"ssl_context": ssl_ctx},

    # Pool otimizado para Supabase Transaction Pooler
    pool_size=10,          # conexões mantidas abertas (era padrão 5)
    max_overflow=20,       # conexões extras sob carga
    pool_pre_ping=True,    # valida conexão antes de usar
    pool_recycle=300,      # recicla a cada 5 min (evita timeout do Supabase)
    pool_timeout=15,       # desiste de esperar conexão após 15s
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    return SessionLocal()
