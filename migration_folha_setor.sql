-- ============================================================
-- MIGRAÇÃO: Setor nos prestadores PJ da Folha Salarial
-- Cole no SQL Editor do Supabase (depois de migration_folha.sql)
-- ============================================================

ALTER TABLE folha_pj ADD COLUMN IF NOT EXISTS setor VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_folha_pj_setor ON folha_pj (setor);
