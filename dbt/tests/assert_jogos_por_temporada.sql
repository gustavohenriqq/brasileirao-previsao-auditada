-- Cada temporada tem o número esperado de jogos: 380 com 20 times, 552 em
-- 2003 e 2004 (24 times), 462 em 2005 (22 times) e 379 em 2016 (um jogo
-- não disputado). O esperado está em seeds/temporadas.csv, com o motivo.
-- Temporada em andamento (esperado vazio): só não pode passar do previsto.
select s.temporada, s.jogos_esperados, count(f.jogo_id) as jogos
from {{ ref('temporadas') }} as s
left join {{ ref('fct_jogos') }} as f on f.temporada = s.temporada
group by s.temporada, s.jogos_previstos, s.jogos_esperados
having count(f.jogo_id) <> coalesce(s.jogos_esperados, count(f.jogo_id))
    or count(f.jogo_id) > s.jogos_previstos
