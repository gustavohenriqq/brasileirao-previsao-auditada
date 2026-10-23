-- Uma linha = um jogo da Série B de 2020 e 2021, com o período de torcida e
-- o resultado do ponto de vista do mandante (mesmo formato de mando_jogos).
-- Existe só para comparar os clubes tradicionais que jogaram a Série B sem
-- torcida (Cruzeiro, Vitória, Figueirense, Ponte Preta) com eles mesmos na
-- Série A de 2015 a 2019. Base: openfootball (com rodada), público da ESPN.
with base as (
    select * from {{ ref('int_jogos_serie_b__fontes') }} where fonte = 'openfootball_b'
),

espn as (
    select * from {{ ref('int_jogos_serie_b__fontes') }} where fonte = 'espn_b'
),

jogos as (
    select
        md5('B|' || b.temporada || '|' || b.mandante_id || '|' || b.visitante_id) as jogo_id,
        b.temporada,
        b.rodada,
        b.data,
        b.mandante_id,
        b.visitante_id,
        b.gols_mandante,
        b.gols_visitante,
        case
            when b.gols_mandante > b.gols_visitante then 'M'
            when b.gols_mandante = b.gols_visitante then 'E'
            else 'V'
        end as resultado,
        e.publico as publico_espn
    from base as b
    left join espn as e
        on e.temporada = b.temporada
        and e.mandante_id = b.mandante_id
        and e.visitante_id = b.visitante_id
)

select
    j.jogo_id,
    j.temporada,
    j.rodada,
    j.data,
    p.periodo,
    p.ordem as periodo_ordem,
    j.mandante_id,
    j.visitante_id,
    j.gols_mandante,
    j.gols_visitante,
    j.resultado,
    case j.resultado when 'M' then 3 when 'E' then 1 else 0 end as pontos_mandante,
    case j.resultado when 'V' then 3 when 'E' then 1 else 0 end as pontos_visitante,
    j.gols_mandante - j.gols_visitante as saldo_mandante,
    j.publico_espn,
    -- Na Série B o público voltou antes, em algumas praças (Goiás em julho de
    -- 2021, Cruzeiro em agosto). Sem torcida aqui = período sem torcida e
    -- público zero na ESPN.
    p.periodo = 'sem_torcida' and coalesce(j.publico_espn, 0) = 0 as sem_torcida_de_fato
from jogos as j
left join {{ ref('periodos_torcida') }} as p
    on j.data between p.inicio and p.fim
