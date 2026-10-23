-- Uma linha = um jogo em uma fonte. Todas as fontes no mesmo formato, já com
-- o id do time da base. É daqui que saem o fato e a conferência.
-- Rodada: Mendeley só tem turno e football-data.co.uk e ESPN não têm rodada.
{% set fontes = [
    ('adaoduque', 'rodada', 'true'),
    ('mendeley', 'null::integer', 'true'),
    ('fdcouk', 'null::integer', 'gols_mandante is not null'),
    ('espn', 'null::integer', 'encerrado'),
    ('openfootball', 'rodada', 'gols_mandante is not null'),
    ('fdorg', 'rodada', 'encerrado'),
] %}

{% for fonte, rodada, encerrado in fontes %}
select
    '{{ fonte }}'::text as fonte,
    id_na_fonte,
    temporada,
    {{ rodada }} as rodada,
    data,
    mandante_nome,
    visitante_nome,
    mandante_id,
    visitante_id,
    gols_mandante,
    gols_visitante,
    {{ encerrado }} as encerrado
from ({{ juntar_de_para(ref('stg_' ~ fonte ~ '__jogos'), fonte) }}) as j
where temporada between {{ var('primeira_temporada') }} and {{ var('ultima_temporada') }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
