-- Uma linha = um jogo da Série B (2020 e 2021) comparado entre as duas
-- fontes. Base: openfootball (tem rodada); conferência: ESPN.
with jogos as (
    select * from {{ ref('int_jogos_serie_b__fontes') }}
),

base as (
    select * from jogos where fonte = 'openfootball_b'
),

espn as (
    select * from jogos where fonte = 'espn_b'
)

select
    coalesce(b.temporada, e.temporada) as temporada,
    coalesce(b.mandante_id, e.mandante_id) as mandante_id,
    coalesce(b.visitante_id, e.visitante_id) as visitante_id,
    b.data as data_base,
    e.data as data_espn,
    b.gols_mandante as gols_mandante_base,
    b.gols_visitante as gols_visitante_base,
    e.gols_mandante as gols_mandante_espn,
    e.gols_visitante as gols_visitante_espn,
    case
        when b.temporada is null then 'so_na_espn'
        when e.temporada is null then 'so_na_base'
        when not e.encerrado then 'nao_encerrado_na_espn'
        when (b.gols_mandante, b.gols_visitante)
            is distinct from (e.gols_mandante, e.gols_visitante) then 'placar_diverge'
        else 'confere'
    end as situacao,
    abs(b.data - e.data) as diferenca_dias
from base as b
full outer join espn as e
    on e.temporada = b.temporada
    and e.mandante_id = b.mandante_id
    and e.visitante_id = b.visitante_id
