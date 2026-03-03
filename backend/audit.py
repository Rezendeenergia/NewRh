"""
Serviço de auditoria — registra todas as ações relevantes do sistema.
"""
from flask import request as flask_request
from database import get_db
import models


def log(username: str, action: str, entity: str = None,
        entity_id: int = None, detail: str = None):
    """
    Registra uma ação no audit log.
    Não lança exceção — falha silenciosamente para não travar o fluxo principal.
    """
    try:
        ip = (
            flask_request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or flask_request.remote_addr
            or "unknown"
        )
        db = get_db()
        try:
            entry = models.AuditLog(
                username=username,
                action=action,
                entity=entity,
                entity_id=entity_id,
                detail=detail,
                ip=ip,
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[AUDIT] Erro ao registrar log: {e}")


# Ações padronizadas
LOGIN             = "LOGIN"
LOGOUT            = "LOGOUT"
CREATE_JOB        = "CREATE_JOB"
UPDATE_JOB        = "UPDATE_JOB"
DELETE_JOB        = "DELETE_JOB"
TOGGLE_JOB        = "TOGGLE_JOB"
UPDATE_STATUS     = "UPDATE_STATUS"
INVITE_USER       = "INVITE_USER"
ACTIVATE_USER     = "ACTIVATE_USER"
RESET_PASSWORD    = "RESET_PASSWORD"
DOWNLOAD_RESUME   = "DOWNLOAD_RESUME"
EXPORT_CSV        = "EXPORT_CSV"
NEW_APPLICATION   = "NEW_APPLICATION"
