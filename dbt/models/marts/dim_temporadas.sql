-- Uma linha = uma temporada: formato esperado (seed) e o que a base tem.
with observado as (
    select
        temporada,
        count(*) as jogos,
        min(data) as primeiro_jogo,
        max(data) as ultimo_jogo,
        max(rodada) as rodadas
    from {{ ref('fct_jogos') }}
    group by temporada
),

times as (
    select temporada, count(distinct time_id) as times
    from (
        select temporada, mandante_id as time_id from {{ ref('fct_jogos') }}
        union
        select temporada, visitante_id from {{ ref('fct_jogos') }}
    ) as t
    group by temporada
)

select
    s.temporada,
    s.times as times_esperados,
    t.times,
    s.jogos_previstos,
    s.jogos_esperados,
    o.jogos,
    o.rodadas,
    o.primeiro_jogo,
    o.ultimo_jogo,
    s.observacao
from {{ ref('temporadas') }} as s
left join observado as o on o.temporada = s.temporada
left join times as t on t.temporada = s.temporada
