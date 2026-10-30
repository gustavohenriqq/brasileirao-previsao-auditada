-- Temporada em andamento: jogados (fct_jogos) + pendentes (jogos_pendentes)
-- fecham o turno e returno. Devolve uma linha por problema:
--   * total diferente de jogos_previstos (380);
--   * número de times diferente do seed (20);
--   * par mandante x visitante repetido entre jogados e pendentes;
--   * time pendente que não está entre os que já jogaram a temporada.
with todos as (
    select temporada, mandante_id, visitante_id, 'jogado' as origem
    from {{ ref('fct_jogos') }}
    where temporada = {{ var('temporada_em_andamento') }}
    union all
    select temporada, mandante_id, visitante_id, 'pendente'
    from {{ ref('jogos_pendentes') }}
),

times as (
    select temporada, mandante_id as time_id, origem from todos
    union
    select temporada, visitante_id, origem from todos
),

s as (
    select * from {{ ref('temporadas') }}
    where temporada = {{ var('temporada_em_andamento') }}
)

select 'total_de_jogos' as problema, s.temporada, null as mandante_id, null as visitante_id,
       count(t.*)::text as valor
from s left join todos as t on t.temporada = s.temporada
group by s.temporada, s.jogos_previstos
having count(t.*) <> s.jogos_previstos

union all

select 'numero_de_times', s.temporada, null, null, count(distinct tm.time_id)::text
from s left join times as tm on tm.temporada = s.temporada
group by s.temporada, s.times
having count(distinct tm.time_id) <> s.times

union all

select 'par_repetido', temporada, mandante_id, visitante_id, string_agg(origem, ', ')
from todos
group by temporada, mandante_id, visitante_id
having count(*) > 1

union all

select 'time_pendente_sem_jogo', p.temporada, p.time_id, null, null
from times as p
where p.origem = 'pendente'
    and not exists (
        select 1 from times as j
        where j.origem = 'jogado' and j.temporada = p.temporada and j.time_id = p.time_id
    )
