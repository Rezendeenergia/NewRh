-- ============================================================
-- MIGRAÇÃO: Solicitações de Abertura de Vaga
-- Cole no SQL Editor do Supabase
-- ============================================================

CREATE TABLE IF NOT EXISTS solicitacoes_vaga (
  id                SERIAL PRIMARY KEY,
  position          VARCHAR(100) NOT NULL,
  location          VARCHAR(100) NOT NULL,
  tipo              VARCHAR(80),
  num_vagas         INTEGER      NOT NULL DEFAULT 1,
  finalidade        TEXT,
  justificativa     TEXT         NOT NULL,
  solicitante_nome  VARCHAR(100) NOT NULL,
  solicitante_email VARCHAR(150) NOT NULL,
  solicitante_user  VARCHAR(50),
  status            VARCHAR(20)  NOT NULL DEFAULT 'PENDENTE',
  approval_token    VARCHAR(100) UNIQUE,
  aprovado_por      VARCHAR(100),
  motivo_rejeicao   TEXT,
  decidido_em       TIMESTAMP,
  job_id            INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
  created_at        TIMESTAMP    DEFAULT NOW(),
  updated_at        TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sol_status ON solicitacoes_vaga (status);
CREATE INDEX IF NOT EXISTS idx_sol_token  ON solicitacoes_vaga (approval_token);
CREATE INDEX IF NOT EXISTS idx_sol_user   ON solicitacoes_vaga (solicitante_user);

-- Também registre o usuário do Rafael como ROLE_OWNER no banco:
-- (rode só se o Rafael ainda não tiver conta)
-- INSERT INTO users (username, email, role, is_active)
-- VALUES ('rafael', 'rafael@rezendeenergia.com.br', 'ROLE_OWNER', true)
-- ON CONFLICT (username) DO UPDATE SET role = 'ROLE_OWNER', is_active = true;

-- Ou se a conta já existe, só atualize o role:
-- UPDATE users SET role = 'ROLE_OWNER' WHERE username = 'rafael';
