-- Uma linha = um clube que disputou a Série A entre 2003 e 2025.
with jogos_por_time as (
    select mandante_id as time_id, temporada from {{ ref('fct_jogos') }}
    union
    select visitante_id, temporada from {{ ref('fct_jogos') }}
)

select
    t.time_id,
    t.nome,
    t.uf,
    min(j.temporada) as primeira_temporada,
    max(j.temporada) as ultima_temporada,
    count(distinct j.temporada) as temporadas_na_serie_a
from {{ ref('times') }} as t
left join jogos_por_time as j on j.time_id = t.time_id
group by t.time_id, t.nome, t.uf
