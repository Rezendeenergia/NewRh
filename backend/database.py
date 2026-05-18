from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import ssl
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")


def _parse_db_url(url: str) -> str:
    if not url:
        return url

    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://", "postgresql+pg8000://"):
        if url.startswith(prefix):
            url = "postgresql+pg8000://" + url[len(prefix):]
            break

    url = url.split("?")[0]

    scheme_end = url.index("://") + 3
    at_pos = url.rfind("@")

    if at_pos > scheme_end:
        credentials = url[scheme_end:at_pos]
        hostpart    = url[at_pos + 1:]

        colon_pos = credentials.find(":")
        if colon_pos != -1:
            user     = credentials[:colon_pos]
            password = credentials[colon_pos + 1:].replace("@", "%40")
            credentials = f"{user}:{password}"

        url = f"postgresql+pg8000://{credentials}@{hostpart}"

    return url


database_url = _parse_db_url(raw_url)

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

host = database_url.split("@")[1].split("/")[0] if "@" in database_url else "?"
print(f"[DB] Conectando em: {host}")

engine = create_engine(
    database_url,
    connect_args={"ssl_context": ssl_ctx},

    # Pool dimensionado para 2 workers gevent com alta concorrência
    # Supabase Transaction Pooler aguenta bem até ~50 conexões simultâneas
    pool_size=15,           # conexões base mantidas abertas
    max_overflow=25,        # conexões extras sob pico (total: 40)
    pool_pre_ping=True,     # valida conexão antes de usar (evita "connection closed")
    pool_recycle=300,       # recicla a cada 5 min (evita timeout do Supabase)
    pool_timeout=10,        # desiste de esperar conexão após 10s (falha rápida)
    pool_use_lifo=True,     # reutiliza conexões recentes (mais quentes, mais rápidas)
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    return SessionLocal()
