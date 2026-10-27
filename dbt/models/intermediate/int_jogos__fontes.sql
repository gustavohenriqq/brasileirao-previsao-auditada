-- Uma linha = um jogo em uma fonte. Todas as fontes no mesmo formato, já com
-- o id do time da base. É daqui que saem o fato e a conferência.
-- A base entra como fonte 'base' (adaoduque até 2025, football-data.org em
-- 2026, ver int_jogos__base). Onde o football-data.org é a base, ele não
-- entra também como conferência: seria a base conferindo a si mesma.
-- Rodada: Mendeley só tem turno e football-data.co.uk e ESPN não têm rodada.
{% set fontes = [
    ('mendeley', 'null::integer', 'true'),
    ('fdcouk', 'null::integer', 'gols_mandante is not null'),
    ('espn', 'null::integer', 'encerrado'),
    ('openfootball', 'rodada', 'gols_mandante is not null'),
    ('fdorg', 'rodada', 'encerrado'),
] %}

select
    'base'::text as fonte,
    id_na_fonte,
    temporada,
    rodada,
    data,
    mandante_nome,
    visitante_nome,
    mandante_id,
    visitante_id,
    gols_mandante,
    gols_visitante,
    true as encerrado
from {{ ref('int_jogos__base') }}
where temporada between {{ var('primeira_temporada') }} and {{ var('ultima_temporada') }}

{% for fonte, rodada, encerrado in fontes %}
union all
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
{%- if fonte == 'fdorg' %}
    and temporada not in (
        select distinct temporada from {{ ref('int_jogos__base') }} where fonte_base = 'fdorg'
    )
{%- endif %}
{% endfor %}
