from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, quote
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")

def _build_url(url: str) -> str:
    if not url:
        return url

    # Normaliza prefixo
    for prefix in ("postgresql+psycopg2://", "postgresql+pg8000://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]

    # Parse para codificar senha com caracteres especiais
    parsed = urlparse(url)
    password = parsed.password or ""
    username = parsed.username or ""
    host_part = parsed.hostname or ""
    if parsed.port:
        host_part += f":{parsed.port}"

    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host_part}"

    clean_url = urlunparse((
        "postgresql+pg8000",
        netloc,
        parsed.path,
        "", "", ""
    ))

    clean_url += "?ssl_context=True"
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
