-- ============================================================
-- MIGRAÇÃO: Dashboard de Folha Salarial (CLT + PJ)
-- Cole no SQL Editor do Supabase
-- ============================================================

-- Cada upload de planilha de folha vira um registro aqui (uma "competência")
CREATE TABLE IF NOT EXISTS folha_importacoes (
  id                  SERIAL PRIMARY KEY,
  competencia_mes     SMALLINT     NOT NULL,                 -- 1-12
  competencia_ano     SMALLINT     NOT NULL,
  arquivo_nome        VARCHAR(255),
  importado_por       VARCHAR(150) NOT NULL,                 -- e-mail de quem importou
  total_clt           NUMERIC(14,2) NOT NULL DEFAULT 0,       -- soma do total líquido CLT
  total_pj            NUMERIC(14,2) NOT NULL DEFAULT 0,       -- soma do valor PJ
  total_geral         NUMERIC(14,2) NOT NULL DEFAULT 0,       -- total_clt + total_pj
  qtd_clt             INTEGER      NOT NULL DEFAULT 0,
  qtd_pj              INTEGER      NOT NULL DEFAULT 0,
  created_at          TIMESTAMP    DEFAULT NOW(),

  -- uma importação por competência (reimportar substitui, não duplica)
  UNIQUE (competencia_mes, competencia_ano)
);

-- Colaboradores CLT da competência (vem da aba "Detalhado Relatorio")
CREATE TABLE IF NOT EXISTS folha_colaboradores (
  id                        SERIAL PRIMARY KEY,
  importacao_id             INTEGER NOT NULL REFERENCES folha_importacoes(id) ON DELETE CASCADE,

  nome                      VARCHAR(150) NOT NULL,
  funcao                    VARCHAR(150),
  data_admissao             DATE,
  regional                  VARCHAR(60),                      -- ex.: NORDESTE, OESTE
  classificacao             VARCHAR(10),                       -- MOD (operacional) ou MOI (administrativo)

  salario_base              NUMERIC(12,2) DEFAULT 0,
  periculosidade            NUMERIC(12,2) DEFAULT 0,
  gratificacao              NUMERIC(12,2) DEFAULT 0,
  ferias                    NUMERIC(12,2) DEFAULT 0,
  salario_familia           NUMERIC(12,2) DEFAULT 0,
  cesta_basica               NUMERIC(12,2) DEFAULT 0,
  plano_saude                NUMERIC(12,2) DEFAULT 0,
  desconto_coparticipacao    NUMERIC(12,2) DEFAULT 0,
  desconto_consignado        NUMERIC(12,2) DEFAULT 0,
  adiantamento                NUMERIC(12,2) DEFAULT 0,
  desconto_falta              NUMERIC(12,2) DEFAULT 0,
  desconto_odr                 NUMERIC(12,2) DEFAULT 0,
  desconto_antecipacao_ferias  NUMERIC(12,2) DEFAULT 0,
  inss                        NUMERIC(12,2) DEFAULT 0,
  irpf                        NUMERIC(12,2) DEFAULT 0,
  fgts                        NUMERIC(12,2) DEFAULT 0,
  ajuda_custo                 NUMERIC(12,2) DEFAULT 0,
  total_liquido                NUMERIC(12,2) DEFAULT 0,
  perspectiva_salarial          NUMERIC(12,2) DEFAULT 0,
  observacoes                   TEXT
);

CREATE INDEX IF NOT EXISTS idx_folha_colab_importacao ON folha_colaboradores (importacao_id);
CREATE INDEX IF NOT EXISTS idx_folha_colab_regional    ON folha_colaboradores (regional);
CREATE INDEX IF NOT EXISTS idx_folha_colab_class        ON folha_colaboradores (classificacao);

-- Prestadores PJ da competência (vem da aba "PJ")
CREATE TABLE IF NOT EXISTS folha_pj (
  id             SERIAL PRIMARY KEY,
  importacao_id  INTEGER NOT NULL REFERENCES folha_importacoes(id) ON DELETE CASCADE,
  fornecedor     VARCHAR(150) NOT NULL,
  valor          NUMERIC(12,2) DEFAULT 0,
  descricao      VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_folha_pj_importacao ON folha_pj (importacao_id);

-- Dados de folha são financeiros/sensíveis: RLS ligado e sem política pública
-- (o backend acessa direto via DATABASE_URL, fora do PostgREST/anon key).
ALTER TABLE folha_importacoes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE folha_colaboradores ENABLE ROW LEVEL SECURITY;
ALTER TABLE folha_pj            ENABLE ROW LEVEL SECURITY;
