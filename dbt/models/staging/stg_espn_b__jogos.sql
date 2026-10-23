-- Série B (2020 e 2021). Mesmo tratamento do modelo da Série A.
-- Uma linha = um evento da Série A na API da ESPN.
-- A data vem em UTC; a data do jogo é a de Brasília. Público 0 pode ser
-- portão fechado ou dado ausente: a Fase 1 trata isso antes de usar.
select
    id as id_na_fonte,
    temporada::integer as temporada,
    data_utc::timestamptz as inicio_utc,
    (data_utc::timestamptz at time zone 'America/Sao_Paulo')::date as data,
    status,
    status = 'STATUS_FULL_TIME' as encerrado,
    mandante as mandante_nome,
    visitante as visitante_nome,
    {{ texto_para_inteiro('placar_mandante') }} as gols_mandante,
    {{ texto_para_inteiro('placar_visitante') }} as gols_visitante,
    {{ texto_para_inteiro('publico') }} as publico,
    estadio,
    cidade,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from {{ source('raw', 'espn_b_jogos') }}
