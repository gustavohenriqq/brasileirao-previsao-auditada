-- Uma linha = um jogo com a data mais apoiada pelas fontes de conferência.
-- Uso: corrigir a data da base quando pelo menos duas outras fontes
-- concordam entre si (até 1 dia de diferença, por causa de fuso) e a base
-- fica mais de 1 dia longe. Achado de 23/10/2026: em 2007 a 2010 a base tem
-- datas 7 ou 14 dias fora; conferido no RSSSF (2009, Atlético-MG x Náutico).
with outras as (
    select fonte, temporada, mandante_id, visitante_id, data
    from {{ ref('int_jogos__fontes') }}
    where fonte <> 'adaoduque' and data is not null and encerrado
),

candidatas as (
    select
        o1.temporada,
        o1.mandante_id,
        o1.visitante_id,
        o1.data as data_candidata,
        count(distinct o2.fonte) as fontes_apoiam,
        string_agg(distinct o2.fonte, ', ') as fontes
    from outras as o1
    inner join outras as o2
        on o2.temporada = o1.temporada
        and o2.mandante_id = o1.mandante_id
        and o2.visitante_id = o1.visitante_id
        and abs(o2.data - o1.data) <= 1
    group by o1.temporada, o1.mandante_id, o1.visitante_id, o1.data
)

select distinct on (temporada, mandante_id, visitante_id)
    temporada,
    mandante_id,
    visitante_id,
    data_candidata as data_maioria,
    fontes_apoiam,
    fontes
from candidatas
order by temporada, mandante_id, visitante_id, fontes_apoiam desc, data_candidata
