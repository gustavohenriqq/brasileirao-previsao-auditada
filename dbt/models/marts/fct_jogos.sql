-- Uma linha = um jogo da Série A de 2003 a 2026, como na base (adaoduque até
-- 2025; football-data.org em 2026, só os jogos encerrados, ver int_jogos__base).
-- Odds de fechamento vêm do football-data.co.uk (2012 em diante) e o público
-- da ESPN (2006 em diante); as duas entram por temporada + mandante + visitante.
-- A data é a da base, exceto quando duas ou mais fontes concordam numa data
-- a mais de 1 dia dela (ver int_datas__maioria); data_base guarda a original.
with base as (
    select * from {{ ref('int_jogos__base') }}
),

maioria as (
    select * from {{ ref('int_datas__maioria') }}
),

odds as (
    {{ juntar_de_para(ref('stg_fdcouk__jogos'), 'fdcouk') }}
),

espn as (
    {{ juntar_de_para(ref('stg_espn__jogos'), 'espn') }}
),

conferencia as (
    select
        temporada,
        mandante_id,
        visitante_id,
        count(*) filter (where situacao <> 'so_na_fonte') as fontes_que_cobrem,
        count(*) filter (where situacao = 'confere') as fontes_que_conferem,
        string_agg(fonte, ', ' order by fonte) filter (
            where situacao not in ('confere', 'so_na_fonte')
        ) as fontes_divergentes
    from {{ ref('conferencia_fontes') }}
    group by temporada, mandante_id, visitante_id
)

select
    md5(b.temporada || '|' || b.mandante_id || '|' || b.visitante_id) as jogo_id,
    b.temporada,
    b.rodada,
    case
        when m.fontes_apoiam >= 2 and abs(m.data_maioria - b.data) > 1 then m.data_maioria
        else b.data
    end as data,
    b.data as data_base,
    coalesce(m.fontes_apoiam >= 2 and abs(m.data_maioria - b.data) > 1, false) as data_corrigida,
    b.hora,
    b.mandante_id,
    b.visitante_id,
    b.gols_mandante,
    b.gols_visitante,
    case
        when b.gols_mandante > b.gols_visitante then 'M'
        when b.gols_mandante = b.gols_visitante then 'E'
        else 'V'
    end as resultado,
    coalesce(b.estadio, e.estadio) as estadio,
    e.publico as publico_espn,
    o.odd_pinnacle_mandante,
    o.odd_pinnacle_empate,
    o.odd_pinnacle_visitante,
    o.odd_media_mandante,
    o.odd_media_empate,
    o.odd_media_visitante,
    o.odd_maxima_mandante,
    o.odd_maxima_empate,
    o.odd_maxima_visitante,
    coalesce(c.fontes_que_cobrem, 0) as fontes_que_cobrem,
    coalesce(c.fontes_que_conferem, 0) as fontes_que_conferem,
    c.fontes_divergentes
from base as b
left join odds as o
    on o.temporada = b.temporada
    and o.mandante_id = b.mandante_id
    and o.visitante_id = b.visitante_id
left join espn as e
    on e.temporada = b.temporada
    and e.mandante_id = b.mandante_id
    and e.visitante_id = b.visitante_id
    and e.encerrado
left join maioria as m
    on m.temporada = b.temporada
    and m.mandante_id = b.mandante_id
    and m.visitante_id = b.visitante_id
left join conferencia as c
    on c.temporada = b.temporada
    and c.mandante_id = b.mandante_id
    and c.visitante_id = b.visitante_id
