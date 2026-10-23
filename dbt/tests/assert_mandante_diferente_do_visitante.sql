select jogo_id, mandante_id, visitante_id
from {{ ref('fct_jogos') }}
where mandante_id = visitante_id
