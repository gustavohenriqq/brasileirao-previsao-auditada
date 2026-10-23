-- Plausibilidade: o jogo cai entre janeiro do ano da temporada e março do
-- ano seguinte (2020 terminou em fevereiro de 2021).
select jogo_id, temporada, data
from {{ ref('fct_jogos') }}
where data < make_date(temporada, 1, 1)
   or data > make_date(temporada + 1, 3, 31)
