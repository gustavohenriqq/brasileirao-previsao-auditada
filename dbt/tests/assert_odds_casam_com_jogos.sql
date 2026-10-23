-- Todo jogo do football-data.co.uk (2012 a 2025) com placar precisa casar
-- com um jogo do fato, senão as odds somem sem aviso na Fase 2.
select o.temporada, o.mandante_nome, o.visitante_nome
from {{ ref('int_jogos__fontes') }} as o
left join {{ ref('fct_jogos') }} as f
    on f.temporada = o.temporada
    and f.mandante_id = o.mandante_id
    and f.visitante_id = o.visitante_id
where o.fonte = 'fdcouk'
  and o.gols_mandante is not null
  and f.jogo_id is null
