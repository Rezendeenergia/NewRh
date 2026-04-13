from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50),  unique=True, nullable=False)
    email           = Column(String(150), unique=True, nullable=False)
    password        = Column(String(255), nullable=True)
    role            = Column(String(30),  nullable=False, default="ROLE_ADMIN")
    is_active       = Column(Boolean,     nullable=False, default=False)
    invite_token    = Column(String(100), nullable=True, unique=True)
    invite_expires  = Column(DateTime,    nullable=True)
    reset_token     = Column(String(100), nullable=True, unique=True)
    reset_expires   = Column(DateTime,    nullable=True)
    created_at      = Column(DateTime,    server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id          = Column(Integer, primary_key=True, index=True)
    position    = Column(String(100), nullable=False)
    location    = Column(String(100), nullable=False)
    tipo        = Column(String(80))
    num_vagas   = Column(Integer, nullable=False, default=1)
    finalidade  = Column(Text)
    responsavel = Column(String(100))
    email_resp  = Column(String(150))
    status      = Column(String(10), nullable=False, default="OPEN")
    expires_at  = Column(DateTime,   nullable=True)   # encerramento automático
    created_at  = Column(DateTime,   server_default=func.now())

    candidaturas = relationship("Candidatura", back_populates="job", cascade="all, delete")


class Candidatura(Base):
    __tablename__ = "candidaturas"

    id                     = Column(Integer, primary_key=True, index=True)
    job_id                 = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)

    full_name              = Column(String(150), nullable=False)
    cpf                    = Column(String(14),  nullable=False)
    rg                     = Column(String(20),  nullable=False)
    data_nascimento        = Column(Date)
    tipo_sanguineo         = Column(String(20))
    nome_mae               = Column(String(150))
    cidade_natal           = Column(String(100))
    cidade_atual           = Column(String(100))

    phone                  = Column(String(20),  nullable=False)
    email                  = Column(String(150), nullable=False)
    linkedin               = Column(String(200))

    education              = Column(String(80))
    experience             = Column(String(30))
    disponibilidade_viagem = Column(String(10))

    tamanho_calca          = Column(String(5))
    tamanho_camisa         = Column(String(5))
    tamanho_bota           = Column(String(5))

    carteira_motorista     = Column(Text)
    nrs                    = Column(Text)
    escolas                = Column(Text)

    motivation             = Column(Text)
    observacoes            = Column(Text)
    resume_name            = Column(String(200))
    status                 = Column(String(30), nullable=False, default="PENDING")
    # Funil: PENDING → TRIAGEM → TRIAGEM_OK → ENTREVISTA → ENTREVISTA_OK → APROVACAO_FINAL → APPROVED / REJECTED
    funnel_stage           = Column(String(30), nullable=True)
    interview_date         = Column(DateTime,   nullable=True)
    interview_notes        = Column(Text,        nullable=True)
    applied_at             = Column(DateTime, server_default=func.now())

    job     = relationship("Job", back_populates="candidaturas")
    history = relationship("StatusHistory", back_populates="candidatura",
                           cascade="all, delete", order_by="StatusHistory.changed_at")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id               = Column(Integer, primary_key=True, index=True)
    candidatura_id   = Column(Integer, ForeignKey("candidaturas.id", ondelete="CASCADE"), nullable=False)
    old_status       = Column(String(10))
    new_status       = Column(String(10), nullable=False)
    changed_by       = Column(String(50), nullable=False)
    changed_at       = Column(DateTime,   server_default=func.now())
    note             = Column(Text)

    candidatura = relationship("Candidatura", back_populates="history")


class AuditLog(Base):
    """Registro imutável de todas as ações no sistema."""
    __tablename__ = "audit_log"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String(50),  nullable=False)          # quem fez
    action     = Column(String(50),  nullable=False)          # LOGIN, LOGOUT, CREATE_JOB, UPDATE_STATUS...
    entity     = Column(String(30),  nullable=True)           # job, candidatura, user
    entity_id  = Column(Integer,     nullable=True)           # ID do objeto afetado
    detail     = Column(Text,        nullable=True)           # detalhe legível
    ip         = Column(String(45),  nullable=True)           # IPv4/IPv6
    created_at = Column(DateTime,    server_default=func.now())


# ── Módulo de Admissão ────────────────────────────────────────

ADMISSION_STEPS = [
    # RH
    {"key": "aso",             "label": "Agendar ASO",                          "dept": "RH",         "type": "check"},
    # DP Externo
    {"key": "dp_admissao",     "label": "Realizar admissão (DP Externo)",        "dept": "DP_EXTERNO", "type": "check"},
    {"key": "dp_encaminhar",   "label": "Encaminhar documentação à Rezende",     "dept": "DP_EXTERNO", "type": "upload"},
    # DP Pessoal
    {"key": "gpm_cadastro",    "label": "Cadastrar no GPM",                      "dept": "DP_PESSOAL", "type": "check"},
    {"key": "assinaturas",     "label": "Coletar assinaturas (Gerência + colab.)","dept": "DP_PESSOAL", "type": "upload"},
    # RH
    {"key": "bemhoeft",        "label": "Incluir prontuário no Bemhoeft",        "dept": "RH",         "type": "upload"},
    {"key": "aprovacao_colab", "label": "Aprovação do colaborador",              "dept": "RH",         "type": "approve"},
    {"key": "cracha",          "label": "Enviar para gráfica do crachá",         "dept": "RH",         "type": "check"},
    {"key": "equatorial",      "label": "Integração Equatorial",                 "dept": "RH",         "type": "approve"},
    # SESMT
    {"key": "nr_formacao",     "label": "Formação/reciclagem NRs",               "dept": "SESMT",      "type": "upload"},
    {"key": "pop_seguranca",   "label": "Mapear treinamento POP Segurança",      "dept": "SESMT",      "type": "check"},
    {"key": "prontuario_seg",  "label": "Prontuário de Segurança",               "dept": "SESMT",      "type": "upload"},
    {"key": "certificados_nr", "label": "Verificar certificados NRs",            "dept": "SESMT",      "type": "upload"},
    {"key": "deep_prova",      "label": "Prova DEEP",                            "dept": "SESMT",      "type": "approve"},
    # Final
    {"key": "liberado_campo",  "label": "Liberado para Campo",                   "dept": "RH",         "type": "check"},
]


class Admission(Base):
    """Processo de admissão de um colaborador."""
    __tablename__ = "admissions"

    id              = Column(Integer,     primary_key=True, index=True)
    candidatura_id  = Column(Integer,     ForeignKey("candidaturas.id", ondelete="SET NULL"), nullable=True)
    full_name       = Column(String(150), nullable=False)
    cpf             = Column(String(14),  nullable=False)
    cargo           = Column(String(100), nullable=False)
    email           = Column(String(150), nullable=True)
    phone           = Column(String(20),  nullable=True)
    status          = Column(String(20),  nullable=False, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, CANCELLED
    current_step    = Column(String(50),  nullable=False, default="aso")
    sharepoint_url  = Column(Text,        nullable=True)   # URL da pasta no SharePoint
    notes           = Column(Text,        nullable=True)
    created_by      = Column(String(50),  nullable=False)
    created_at      = Column(DateTime,    server_default=func.now())
    updated_at      = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    steps     = relationship("AdmissionStep",     back_populates="admission", cascade="all, delete")
    documents = relationship("AdmissionDocument", back_populates="admission", cascade="all, delete")


class AdmissionStep(Base):
    """Status de cada etapa do fluxo de admissão."""
    __tablename__ = "admission_steps"

    id           = Column(Integer,     primary_key=True, index=True)
    admission_id = Column(Integer,     ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False)
    step_key     = Column(String(50),  nullable=False)
    status       = Column(String(20),  nullable=False, default="PENDING")  # PENDING, DONE, APPROVED, REJECTED, SKIPPED
    done_by      = Column(String(50),  nullable=True)
    done_at      = Column(DateTime,    nullable=True)
    note         = Column(Text,        nullable=True)
    result       = Column(String(20),  nullable=True)  # para tipo approve: APPROVED/REJECTED

    admission = relationship("Admission", back_populates="steps")


class AdmissionDocument(Base):
    """Documento anexado em uma etapa da admissão."""
    __tablename__ = "admission_documents"

    id             = Column(Integer,     primary_key=True, index=True)
    admission_id   = Column(Integer,     ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False)
    step_key       = Column(String(50),  nullable=False)
    filename       = Column(String(200), nullable=False)
    original_name  = Column(String(200), nullable=False)
    sharepoint_url = Column(Text,        nullable=True)
    uploaded_by    = Column(String(50),  nullable=False)
    uploaded_at    = Column(DateTime,    server_default=func.now())

    admission = relationship("Admission", back_populates="documents")


# ── Fluxo de Admissão ─────────────────────────────────────────

class ProcessoAdmissao(Base):
    __tablename__ = "processo_admissao"

    id               = Column(Integer, primary_key=True, index=True)
    candidatura_id   = Column(Integer, ForeignKey("candidaturas.id", ondelete="CASCADE"), unique=True)
    status           = Column(String(20), nullable=False, default="EM_ANDAMENTO")
    # status: EM_ANDAMENTO | CONCLUIDO | CANCELADO
    tipo_admissao    = Column(String(30), nullable=True, default="ADMISSAO_NOVA")
    # tipo_admissao: ADMISSAO_NOVA | MUDANCA_FUNCAO | REINTEGRACAO | MOBILIZACAO
    etapa_atual      = Column(String(50), nullable=True)
    sharepoint_url   = Column(Text, nullable=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    candidatura = relationship("Candidatura", backref="processo")
    etapas      = relationship("EtapaProcesso", back_populates="processo",
                               order_by="EtapaProcesso.ordem", cascade="all, delete-orphan")


class EtapaProcesso(Base):
    __tablename__ = "etapa_processo"

    id           = Column(Integer, primary_key=True, index=True)
    processo_id  = Column(Integer, ForeignKey("processo_admissao.id", ondelete="CASCADE"))
    ordem        = Column(Integer, nullable=False)
    codigo       = Column(String(50), nullable=False)   # ex: TRIAGEM, ASO, GPM...
    nome         = Column(String(100), nullable=False)
    departamento = Column(String(50), nullable=False)   # RH, DP, SESMT, DP_EXTERNO
    status       = Column(String(20), nullable=False, default="PENDENTE")
    # status: PENDENTE | EM_ANDAMENTO | APROVADO | REPROVADO | REENVIAR
    tipo         = Column(String(20), nullable=False, default="APROVACAO")
    # tipo: APROVACAO | DOCUMENTO | CHECKLIST | ENTREVISTA
    prazo_dias   = Column(Integer, nullable=True)
    observacao   = Column(Text, nullable=True)
    nota         = Column(Text, nullable=True)          # nota interna do gestor
    responsavel  = Column(String(100), nullable=True)   # username do gestor
    iniciado_em  = Column(DateTime, nullable=True)
    concluido_em = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, server_default=func.now())

    processo    = relationship("ProcessoAdmissao", back_populates="etapas")
    documentos  = relationship("DocumentoEtapa", back_populates="etapa",
                               cascade="all, delete-orphan")


class DocumentoEtapa(Base):
    __tablename__ = "documento_etapa"

    id           = Column(Integer, primary_key=True, index=True)
    etapa_id     = Column(Integer, ForeignKey("etapa_processo.id", ondelete="CASCADE"))
    nome         = Column(String(200), nullable=False)
    arquivo      = Column(String(300), nullable=True)   # path local
    sharepoint_url = Column(Text, nullable=True)        # URL no SharePoint
    enviado_por  = Column(String(100), nullable=True)   # username
    status       = Column(String(20), nullable=False, default="PENDENTE")
    # status: PENDENTE | APROVADO | REPROVADO | REENVIAR
    observacao   = Column(Text, nullable=True)
    created_at   = Column(DateTime, server_default=func.now())

    etapa = relationship("EtapaProcesso", back_populates="documentos")


# ── Solicitação de abertura de vaga ────────────────────────────
class SolicitacaoVaga(Base):
    __tablename__ = "solicitacoes_vaga"

    id                = Column(Integer, primary_key=True, index=True)
    # Dados da vaga solicitada
    position          = Column(String(100), nullable=False)
    location          = Column(String(100), nullable=False)
    tipo              = Column(String(80), nullable=True)
    num_vagas         = Column(Integer, nullable=False, default=1)
    finalidade        = Column(Text, nullable=True)
    justificativa     = Column(Text, nullable=False)   # obrigatória
    # Quem pediu
    solicitante_nome  = Column(String(100), nullable=False)
    solicitante_email = Column(String(150), nullable=False)
    solicitante_user  = Column(String(50), nullable=True)
    # Aprovação
    status            = Column(String(20), nullable=False, default="PENDENTE")
    # PENDENTE | APROVADA | REJEITADA
    approval_token    = Column(String(100), unique=True, nullable=True)
    aprovado_por      = Column(String(100), nullable=True)
    motivo_rejeicao   = Column(Text, nullable=True)
    decidido_em       = Column(DateTime, nullable=True)
    # Vaga criada após aprovação
    job_id            = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    # Datas
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())

    job = relationship("Job", foreign_keys=[job_id])


# ── Conta do Candidato (login e-mail + senha) ────────────────
class CandidatoConta(Base):
    __tablename__ = "candidato_contas"

    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String(150), unique=True, nullable=False, index=True)
    senha_hash     = Column(String(64), nullable=True)
    reset_token    = Column(String(100), nullable=True)
    reset_expiry   = Column(DateTime(timezone=True), nullable=True)
    ultimo_acesso  = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())


# ── Documentos adicionais do Candidato ───────────────────────
class CandidatoDocumento(Base):
    __tablename__ = "candidato_documentos"

    id             = Column(Integer, primary_key=True, index=True)
    candidatura_id = Column(Integer, ForeignKey("candidaturas.id", ondelete="CASCADE"), nullable=False)
    nome           = Column(String(200), nullable=False)   # nome original do arquivo
    arquivo        = Column(String(300), nullable=True)    # path local
    sharepoint_url = Column(Text, nullable=True)
    tipo           = Column(String(50), nullable=True)     # NR, DIPLOMA, CERTIFICADO, OUTRO
    descricao      = Column(String(200), nullable=True)
    enviado_em     = Column(DateTime, server_default=func.now())

    candidatura = relationship("Candidatura", backref="documentos_extras")
