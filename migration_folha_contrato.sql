-- ============================================================
-- MIGRAÇÃO: renomeia a coluna "observacoes" para "contrato"
-- em folha_colaboradores (a planilha passou a chamar essa
-- coluna de "Contrato", antes era "Observações")
-- Cole no SQL Editor do Supabase (depois de migration_folha_setor.sql)
-- ============================================================

ALTER TABLE folha_colaboradores RENAME COLUMN observacoes TO contrato;
