from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
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

host = database_url.split("@")[1].split("/")[0] if "@" in database_url else "?"
print(f"[DB] Conectando em: {host}")

# pg8000 com gevent: passa ssl como string "require" em vez de objeto ssl.SSLContext
# O objeto ssl.SSLContext quebra com gevent monkey-patching
engine = create_engine(
    database_url,
    connect_args={"ssl_context": True},  # True = ssl requerido sem verificação de cert

    pool_size=15,
    max_overflow=25,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,
    pool_use_lifo=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    return SessionLocal()
