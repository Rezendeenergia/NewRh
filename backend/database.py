from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")


def _parse_db_url(url: str) -> str:
    """
    Monta a URL corretamente mesmo com @ na senha (ex: Rezende@2025).
    Usa rfind para localizar o @ REAL que separa credenciais do host.
    """
    if not url:
        return url

    # Normaliza o prefixo do driver para psycopg2
    for prefix in ("postgresql+pg8000://", "postgresql+psycopg2://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break

    # Remove querystring existente
    url = url.split("?")[0]

    # Localiza o @ mais à direita — esse é o separador real de credenciais/host
    # Exemplo: postgresql://user:Rezende@2025@host:5432/db
    #                                          ^--- este é o certo (rfind)
    scheme_end = url.index("://") + 3          # após "postgresql://"
    at_pos = url.rfind("@")                    # último @

    if at_pos > scheme_end:
        credentials = url[scheme_end:at_pos]   # user:Rezende@2025
        hostpart    = url[at_pos + 1:]          # host:5432/db

        # URL-encode o @ dentro das credenciais (na parte da senha)
        colon_pos = credentials.find(":")
        if colon_pos != -1:
            user     = credentials[:colon_pos]
            password = credentials[colon_pos + 1:].replace("@", "%40")
            credentials = f"{user}:{password}"

        url = f"postgresql://{credentials}@{hostpart}"

    return url + "?sslmode=require&connect_timeout=10"


database_url = _parse_db_url(raw_url)

print(f"[DB] Conectando em: {database_url.split('@')[1] if '@' in database_url else database_url}")

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
