-- Rodada entre 1 e o número de rodadas da temporada (2 x (times - 1)).
select f.temporada, f.rodada, f.mandante_id, f.visitante_id
from {{ ref('fct_jogos') }} as f
inner join {{ ref('temporadas') }} as s on s.temporada = f.temporada
where f.rodada not between 1 and 2 * (s.times - 1)
