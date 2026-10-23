{# Acrescenta mandante_id e visitante_id a uma relação de staging, usando o
   de-para de nomes. temporada_de/temporada_ate vazios valem para todas as
   temporadas (caso da ESPN, que chama de "Gremio Barueri" o clube que a base
   separa em Barueri, 2009, e Gremio Prudente, 2010). #}
{% macro juntar_de_para(relacao, fonte) %}
select
    r.*,
    dm.time_id as mandante_id,
    dv.time_id as visitante_id
from {{ relacao }} as r
left join {{ ref('de_para_times') }} as dm
    on dm.fonte = '{{ fonte }}'
    and dm.nome_na_fonte = r.mandante_nome
    and r.temporada between coalesce(dm.temporada_de, 0) and coalesce(dm.temporada_ate, 9999)
left join {{ ref('de_para_times') }} as dv
    on dv.fonte = '{{ fonte }}'
    and dv.nome_na_fonte = r.visitante_nome
    and r.temporada between coalesce(dv.temporada_de, 0) and coalesce(dv.temporada_ate, 9999)
{% endmacro %}
