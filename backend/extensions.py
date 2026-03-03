"""
Instância compartilhada do Flask-Limiter.
Importar aqui evita importações circulares entre main.py e os blueprints.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)
