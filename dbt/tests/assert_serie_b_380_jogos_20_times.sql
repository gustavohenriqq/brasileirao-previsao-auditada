-- Série B de 2020 e 2021: 380 jogos e 20 times por temporada.
select temporada, count(*) as jogos,
       count(distinct mandante_id) as times
from {{ ref('mando_jogos_serie_b') }}
group by temporada
having count(*) <> 380 or count(distinct mandante_id) <> 20
