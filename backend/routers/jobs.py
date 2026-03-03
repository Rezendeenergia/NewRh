from flask import Blueprint, request, jsonify
from database import get_db
from security import require_auth
from datetime import datetime, timezone
import models
import audit

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def job_to_dict(job):
    return {
        "id":          job.id,
        "position":    job.position,
        "location":    job.location,
        "tipo":        job.tipo,
        "numVagas":    job.num_vagas,
        "finalidade":  job.finalidade,
        "responsavel": job.responsavel,
        "emailResp":   job.email_resp,
        "status":      job.status,
        "expiresAt":   job.expires_at.isoformat() if job.expires_at else None,
        "createdAt":   job.created_at.isoformat() if job.created_at else None,
    }


def auto_close_expired(db):
    now = datetime.now(timezone.utc)
    expired = db.query(models.Job).filter(
        models.Job.status == "OPEN",
        models.Job.expires_at != None,
        models.Job.expires_at <= now,
    ).all()
    for job in expired:
        job.status = "CLOSED"
        audit.log("sistema", audit.TOGGLE_JOB, entity="job",
                  entity_id=job.id, detail=f"Vaga '{job.position}' encerrada automaticamente")
    if expired:
        db.commit()


def find_job_or_404(db, job_id):
    job = db.query(models.Job).filter_by(id=job_id).first()
    if not job:
        return None, jsonify({"message": f"Vaga não encontrada: {job_id}"}), 404
    return job, None, None


@bp.get("")
def get_open_jobs():
    db = get_db()
    try:
        auto_close_expired(db)
        jobs = db.query(models.Job).filter_by(status="OPEN") \
                 .order_by(models.Job.created_at.desc()).all()
        return jsonify([job_to_dict(job) for job in jobs])
    finally:
        db.close()


@bp.get("/all")
@require_auth
def get_all_jobs():
    db = get_db()
    try:
        auto_close_expired(db)
        jobs = db.query(models.Job).order_by(models.Job.created_at.desc()).all()
        return jsonify([job_to_dict(job) for job in jobs])
    finally:
        db.close()


@bp.post("")
@require_auth
def create_job():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Dados inválidos"}), 400

    for field in ["position", "location", "tipo", "responsavel", "emailResp"]:
        if not data.get(field):
            return jsonify({"message": f"Campo obrigatório: {field}"}), 400

    expires_at = None
    if data.get("expiresAt"):
        try:
            expires_at = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"message": "Data de encerramento inválida"}), 400

    db = get_db()
    try:
        job = models.Job(
            position=data["position"], location=data["location"],
            tipo=data.get("tipo"), num_vagas=data.get("numVagas", 1),
            finalidade=data.get("finalidade"), responsavel=data["responsavel"],
            email_resp=data["emailResp"], status="OPEN", expires_at=expires_at,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        audit.log(request.username, audit.CREATE_JOB, entity="job",
                  entity_id=job.id, detail=f"Vaga criada: {job.position} — {job.location}")
        return jsonify(job_to_dict(job)), 201
    finally:
        db.close()


@bp.put("/<int:job_id>")
@require_auth
def update_job(job_id):
    data = request.get_json()
    db = get_db()
    try:
        job, error, code = find_job_or_404(db, job_id)
        if error:
            return error, code

        old = f"{job.position} — {job.location}"
        job.position    = data.get("position",    job.position)
        job.location    = data.get("location",    job.location)
        job.tipo        = data.get("tipo",         job.tipo)
        job.num_vagas   = data.get("numVagas",     job.num_vagas)
        job.finalidade  = data.get("finalidade",   job.finalidade)
        job.responsavel = data.get("responsavel",  job.responsavel)
        job.email_resp  = data.get("emailResp",    job.email_resp)

        if "expiresAt" in data:
            if data["expiresAt"]:
                try:
                    job.expires_at = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
                except ValueError:
                    return jsonify({"message": "Data de encerramento inválida"}), 400
            else:
                job.expires_at = None

        db.commit()
        db.refresh(job)
        audit.log(request.username, audit.UPDATE_JOB, entity="job",
                  entity_id=job.id, detail=f"Vaga editada: {old} → {job.position} — {job.location}")
        return jsonify(job_to_dict(job))
    finally:
        db.close()


@bp.patch("/<int:job_id>/status")
@require_auth
def toggle_status(job_id):
    db = get_db()
    try:
        job, error, code = find_job_or_404(db, job_id)
        if error:
            return error, code

        job.status = "CLOSED" if job.status == "OPEN" else "OPEN"
        db.commit()
        db.refresh(job)
        audit.log(request.username, audit.TOGGLE_JOB, entity="job",
                  entity_id=job.id, detail=f"Status da vaga '{job.position}' → {job.status}")
        return jsonify(job_to_dict(job))
    finally:
        db.close()


@bp.delete("/<int:job_id>")
@require_auth
def delete_job(job_id):
    db = get_db()
    try:
        job, error, code = find_job_or_404(db, job_id)
        if error:
            return error, code

        name = job.position
        db.delete(job)
        db.commit()
        audit.log(request.username, audit.DELETE_JOB, entity="job",
                  entity_id=job_id, detail=f"Vaga excluída: {name}")
        return jsonify({"message": "Vaga removida"})
    finally:
        db.close()
