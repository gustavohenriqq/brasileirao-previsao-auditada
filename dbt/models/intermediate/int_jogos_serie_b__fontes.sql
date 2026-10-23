-- Uma linha = um jogo da Série B (2020 e 2021) em uma fonte, com o id do
-- time. As duas fontes usam os mesmos nomes que já usam na Série A, então o
-- de-para é o mesmo (fonte espn e openfootball).
select
    'espn_b'::text as fonte,
    id_na_fonte,
    temporada,
    null::integer as rodada,
    data,
    mandante_nome,
    visitante_nome,
    mandante_id,
    visitante_id,
    gols_mandante,
    gols_visitante,
    encerrado,
    publico
from ({{ juntar_de_para(ref('stg_espn_b__jogos'), 'espn') }}) as e

union all

select
    'openfootball_b'::text,
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
    gols_mandante is not null,
    null::integer
from ({{ juntar_de_para(ref('stg_openfootball_b__jogos'), 'openfootball') }}) as o
