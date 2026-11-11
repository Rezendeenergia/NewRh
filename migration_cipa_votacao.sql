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

-- ============================================================
-- Candidatura única: a mesma pessoa não pode se candidatar duas
-- vezes na mesma gestão. Guarda a matrícula "normalizada" (sem
-- espaço/traço/zero à esquerda) só pra essa checagem.
-- ============================================================

ALTER TABLE cipa_candidaturas
    ADD COLUMN IF NOT EXISTS matricula_norm VARCHAR(30);

-- Preenche a coluna nova pras candidaturas que já existem (testes de hoje),
-- com a mesma regra de normalização usada no backend (_normalizar_matricula):
-- tira tudo que não é letra/número, deixa em caixa alta e, se só sobrar
-- número, tira os zeros à esquerda.
UPDATE cipa_candidaturas
SET matricula_norm = (
    CASE
        WHEN regexp_replace(UPPER(matricula), '[^A-Z0-9]', '', 'g') ~ '^[0-9]+$'
            THEN COALESCE(NULLIF(LTRIM(regexp_replace(UPPER(matricula), '[^A-Z0-9]', '', 'g'), '0'), ''), '0')
        ELSE regexp_replace(UPPER(matricula), '[^A-Z0-9]', '', 'g')
    END
)
WHERE matricula_norm IS NULL;

ALTER TABLE cipa_candidaturas
    ALTER COLUMN matricula_norm SET NOT NULL;

-- Se já existir candidatura duplicada de teste (mesma gestão + matrícula),
-- o comando abaixo falha — rode esta consulta antes e apague/ajuste as
-- duplicadas manualmente se aparecer alguma linha:
--
--   SELECT gestao, matricula_norm, COUNT(*)
--   FROM cipa_candidaturas
--   GROUP BY gestao, matricula_norm
--   HAVING COUNT(*) > 1;

ALTER TABLE cipa_candidaturas
    ADD CONSTRAINT uq_cipa_candidatura_gestao_matricula UNIQUE (gestao, matricula_norm);
