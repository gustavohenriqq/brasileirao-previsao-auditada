-- A posse dos dois lados soma 100 (tolerância de 1 ponto para arredondamento).
-- Em aviso: é a ESPN quem erra a conta, não há o que corrigir aqui.
{{ config(severity='warn') }}
select jogo_id, temporada, sum(posse_pct) as posse_soma
from {{ ref('fct_estatisticas_jogo') }}
where posse_pct is not null
group by jogo_id, temporada
having abs(sum(posse_pct) - 100) > 1
