-- Todo jogo do fct_estatisticas_jogo tem exatamente dois lados: o mandante
-- (casa) e o visitante (fora), um adversário do outro.
select jogo_id, count(*) as linhas, count(distinct mando) as mandos
from {{ ref('fct_estatisticas_jogo') }}
group by jogo_id
having count(*) <> 2
    or count(distinct mando) <> 2
    or count(distinct time_id) <> 2
    or min(time_id) <> min(adversario_id)
    or max(time_id) <> max(adversario_id)
