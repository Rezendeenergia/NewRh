-- ============================================================
-- MIGRAÇÃO: colunas novas em cipa_candidaturas para a votação
-- da CIPA (resultado, candidato eleito e papel na gestão).
--
-- As tabelas novas (cipa_gestoes, cipa_votantes) NÃO precisam de
-- migração — o backend cria elas sozinho na subida (create_all).
-- Só essa ALTER TABLE abaixo precisa ser rodada manualmente, porque
-- cipa_candidaturas já existe em produção.
--
-- Cole no SQL Editor do Supabase (projeto NewRh).
-- ============================================================

ALTER TABLE cipa_candidaturas
    ADD COLUMN IF NOT EXISTS votos  INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS eleito BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS papel  VARCHAR(50);
