-- Uma linha = um lado (casa ou fora) de um evento da ESPN com a lista de
-- estatísticas. Só tipos e nomes: o que é estatística real e o que é molde
-- zerado da ESPN se decide no mart (fct_estatisticas_jogo).
-- Cobertura por época (ver fct_estatisticas_jogo): 2006 só gols, 2007 nada,
-- 2008 e 2009 só chutes, 2010 a 2013 sem posse, 2014 em diante completo.
select
    id as id_na_fonte,
    temporada::integer as temporada,
    data_utc::timestamptz as inicio_utc,
    (data_utc::timestamptz at time zone 'America/Sao_Paulo')::date as data,
    status,
    status = 'STATUS_FULL_TIME' as encerrado,
    lado,
    case lado when 'home' then 'casa' when 'away' then 'fora' end as mando,
    time as time_nome,
    {{ texto_para_inteiro('placar') }} as gols_placar,
    {{ texto_para_decimal('possession_pct') }} as posse_pct,
    {{ texto_para_inteiro('total_shots') }} as chutes,
    {{ texto_para_inteiro('shots_on_target') }} as chutes_no_gol,
    {{ texto_para_inteiro('won_corners') }} as escanteios,
    {{ texto_para_inteiro('fouls_committed') }} as faltas,
    {{ texto_para_inteiro('shot_assists') }} as passes_para_finalizacao,
    {{ texto_para_inteiro('goal_assists') }} as assistencias,
    {{ texto_para_inteiro('appearances') }} as aparicoes,
    {{ texto_para_inteiro('total_goals') }} as gols,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from {{ source('raw', 'espn_estatisticas') }}
-- Mesmo critério de stg_espn__jogos: o adiado sai, o jogo vale pela remarcação.
where status <> 'STATUS_POSTPONED'
