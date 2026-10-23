-- Em pontos corridos, cada time joga 2 x (times - 1) vezes, metade em casa.
-- A folga só existe em temporada com jogo não disputado (2016: Chapecoense
-- e Atlético-MG com 37), e vale para os dois lados da conta.
with jogos as (
    select temporada, mandante_id as time_id, 1 as em_casa from {{ ref('fct_jogos') }}
    union all
    select temporada, visitante_id, 0 from {{ ref('fct_jogos') }}
),

por_time as (
    select temporada, time_id, count(*) as jogos, sum(em_casa) as em_casa
    from jogos
    group by temporada, time_id
)

select p.*, 2 * (s.times - 1) as esperado
from por_time as p
inner join {{ ref('temporadas') }} as s on s.temporada = p.temporada
where p.jogos not between 2 * (s.times - 1) - (s.jogos_previstos - s.jogos_esperados)
                      and 2 * (s.times - 1)
   or p.em_casa not between (s.times - 1) - (s.jogos_previstos - s.jogos_esperados)
                        and (s.times - 1)
