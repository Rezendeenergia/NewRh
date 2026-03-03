from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime


# ── Auth ─────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    username: str
    role: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "ROLE_ADMIN"


# ── Job ──────────────────────────────────────────────────────

class JobRequest(BaseModel):
    position:    str
    location:    str
    tipo:        Optional[str] = None
    numVagas:    int = 1
    finalidade:  Optional[str] = None
    responsavel: str
    emailResp:   EmailStr

class JobResponse(BaseModel):
    id:          int
    position:    str
    location:    str
    tipo:        Optional[str]
    numVagas:    int
    finalidade:  Optional[str]
    responsavel: str
    emailResp:   str
    status:      str
    createdAt:   datetime

    model_config = {"from_attributes": True}


# ── Candidatura ───────────────────────────────────────────────

class CandidaturaRequest(BaseModel):
    jobId:                 int
    fullName:              str
    cpf:                   str
    rg:                    str
    dataNascimento:        Optional[date]   = None
    tipoSanguineo:         Optional[str]    = None
    nomeMae:               Optional[str]    = None
    cidadeNatal:           Optional[str]    = None
    cidadeAtual:           Optional[str]    = None
    phone:                 str
    email:                 EmailStr
    linkedin:              Optional[str]    = None
    education:             Optional[str]    = None
    experience:            Optional[str]    = None
    disponibilidadeViagem: Optional[str]    = None
    tamanhoCalca:          Optional[str]    = None
    tamanhoCamisa:         Optional[str]    = None
    tamanhoBota:           Optional[str]    = None
    carteira:              Optional[list[str]] = None
    nrs:                   Optional[list[str]] = None
    escolas:               Optional[list[str]] = None
    motivation:            Optional[str]    = None
    resumeName:            Optional[str]    = None

class JobSummary(BaseModel):
    id:       int
    position: str
    location: str

    model_config = {"from_attributes": True}

class CandidaturaResponse(BaseModel):
    id:                    int
    job:                   JobSummary
    fullName:              str
    cpf:                   str
    rg:                    str
    dataNascimento:        Optional[date]
    tipoSanguineo:         Optional[str]
    nomeMae:               Optional[str]
    cidadeNatal:           Optional[str]
    cidadeAtual:           Optional[str]
    phone:                 str
    email:                 str
    linkedin:              Optional[str]
    education:             Optional[str]
    experience:            Optional[str]
    disponibilidadeViagem: Optional[str]
    tamanhoCalca:          Optional[str]
    tamanhoCamisa:         Optional[str]
    tamanhoBota:           Optional[str]
    carteira:              Optional[list[str]]
    nrs:                   Optional[list[str]]
    escolas:               Optional[list[str]]
    motivation:            Optional[str]
    resumeName:            Optional[str]
    status:                str
    appliedAt:             datetime

    model_config = {"from_attributes": True}

class StatusUpdateRequest(BaseModel):
    status: str

class StatsResponse(BaseModel):
    total:    int
    pending:  int
    approved: int
    rejected: int
