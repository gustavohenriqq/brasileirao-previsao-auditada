-- Cada temporada tem o número esperado de times (20 desde 2006).
select s.temporada, s.times as esperados, count(distinct t.time_id) as times
from {{ ref('temporadas') }} as s
left join (
    select temporada, mandante_id as time_id from {{ ref('fct_jogos') }}
    union
    select temporada, visitante_id from {{ ref('fct_jogos') }}
) as t on t.temporada = s.temporada
group by s.temporada, s.times
having count(distinct t.time_id) <> s.times
