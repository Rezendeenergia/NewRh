from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import ssl
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")


def _parse_db_url(url: str):
    """
    Parser manual que suporta senhas com @ (ex: Rezende@2025).
    Usa o ÚLTIMO @ como separador entre credenciais e host.
    Aceita tanto Rezende@2025 quanto Rezende%402025 no env var.
    """
    url = url.strip()

    # Remove %40 → @ para normalizar (caso o env var tenha %40)
    # O parser manual vai lidar com o @ correto
    url = url.replace("%40", "@")

    # Remove prefixo de scheme
    for scheme in ("postgresql+psycopg2://", "postgresql+pg8000://",
                   "postgres://", "postgresql://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break

    # Usa o ÚLTIMO @ para separar credenciais do host
    # (senha pode conter @ mas o host nunca tem @ antes da porta)
    at_pos = url.rfind("@")
    credentials = url[:at_pos]
    hostpath    = url[at_pos + 1:]

    # Separa usuário e senha no PRIMEIRO ":"
    colon_pos = credentials.find(":")
    username  = credentials[:colon_pos]
    password  = credentials[colon_pos + 1:]

    # Separa host:porta e dbname
    slash_pos = hostpath.find("/")
    hostport  = hostpath[:slash_pos]
    dbname    = hostpath[slash_pos + 1:].split("?")[0]  # remove querystring

    if ":" in hostport:
        host, port_str = hostport.rsplit(":", 1)
        port = int(port_str)
    else:
        host = hostport
        port = 5432

    return username, password, host, port, dbname


# Monta engine com pg8000 + SSL usando parâmetros explícitos
try:
    username, password, host, port, dbname = _parse_db_url(raw_url)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode    = ssl.CERT_NONE

    engine = create_engine(
        f"postgresql+pg8000://",
        creator=lambda: __import__("pg8000").connect(
            host=host,
            port=port,
            database=dbname,
            user=username,
            password=password,
            ssl_context=ssl_ctx,
        ),
        pool_pre_ping=True,
        pool_timeout=20,
        pool_recycle=300,
    )
    print(f"[DB] Engine criado → {host}:{port}/{dbname} (user: {username})")
except Exception as e:
    print(f"[DB] Erro ao criar engine: {e}")
    raise

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    return SessionLocal()
