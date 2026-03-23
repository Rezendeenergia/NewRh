from datetime import datetime, timedelta, timezone
from flask import request, jsonify
from functools import wraps
from dotenv import load_dotenv
import bcrypt
import jwt
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(username: str, role: str = "ROLE_ADMIN") -> str:
    payload = {
        "sub":  username,
        "role": role,
        "exp":  datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Decodifica o JWT e retorna o payload ou None se inválido."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Token não fornecido"}), 401
        token = auth_header[7:]
        payload = decode_token(token)
        if not payload:
            return jsonify({"message": "Token inválido ou expirado"}), 401
        request.username = payload["sub"]
        request.role     = payload.get("role", "ROLE_ADMIN")
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Apenas ROLE_ADMIN e ROLE_OWNER. ROLE_VIEWER é bloqueado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Token não fornecido"}), 401
        token = auth_header[7:]
        payload = decode_token(token)
        if not payload:
            return jsonify({"message": "Token inválido ou expirado"}), 401
        role = payload.get("role", "ROLE_ADMIN")
        if role == "ROLE_VIEWER":
            return jsonify({"message": "Acesso restrito — sem permissão para esta ação"}), 403
        request.username = payload["sub"]
        request.role     = role
        return f(*args, **kwargs)
    return decorated
