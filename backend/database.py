from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, quote
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")

def _build_url(url: str) -> str:
    """
    Normaliza a DATABASE_URL para psycopg2:
    - Garante o driver postgresql+psycopg2://
    - Codifica caracteres especiais na senha (ex: @, #, %)
    - Adiciona sslmode=require
    """
    if not url:
        return url

    # Troca drivers alternativos
    for prefix in ("postgresql+pg8000://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]

    # Faz parse da URL para codificar a senha corretamente
    parsed = urlparse(url)
    password = parsed.password or ""
    username = parsed.username or ""

    # Reconstrói netloc com senha codificada
    host_part = parsed.hostname or ""
    if parsed.port:
        host_part += f":{parsed.port}"
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host_part}"

    clean_url = urlunparse((
        "postgresql+psycopg2",
        netloc,
        parsed.path,
        "", "", ""
    ))

    # Adiciona sslmode
    clean_url += "?sslmode=require&connect_timeout=10"
    return clean_url


database_url = _build_url(raw_url)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_timeout=20,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    return SessionLocal()
