-- Uma linha = um jogo da base, já com o id dos times.
-- Até 2025 a base é a adaoduque. Em 27/10/2026 ela ainda não tinha 2026, que
-- vem do football-data.org (única fonte atualizada com rodada), só com os
-- jogos encerrados: a temporada em andamento entra parcial.
with adaoduque as (
    {{ juntar_de_para(ref('stg_adaoduque__jogos'), 'adaoduque') }}
),

fdorg as (
    {{ juntar_de_para(ref('stg_fdorg__jogos'), 'fdorg') }}
)

select
    'adaoduque'::text as fonte_base,
    id_na_fonte,
    temporada,
    rodada,
    data,
    hora,
    mandante_nome,
    visitante_nome,
    mandante_id,
    visitante_id,
    gols_mandante,
    gols_visitante,
    estadio
from adaoduque

union all

select
    'fdorg'::text as fonte_base,
    id_na_fonte,
    temporada,
    rodada,
    data,
    (inicio_utc at time zone 'America/Sao_Paulo')::time as hora,
    mandante_nome,
    visitante_nome,
    mandante_id,
    visitante_id,
    gols_mandante,
    gols_visitante,
    null::text as estadio
from fdorg
where encerrado
    and temporada not in (select distinct temporada from adaoduque)
