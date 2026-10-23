-- Uma linha = um jogo da API football-data.org (competição BSA).
select
    id as id_na_fonte,
    temporada::integer as temporada,
    {{ texto_para_inteiro('rodada') }} as rodada,
    data_utc::timestamptz as inicio_utc,
    (data_utc::timestamptz at time zone 'America/Sao_Paulo')::date as data,
    status,
    status = 'FINISHED' as encerrado,
    mandante as mandante_nome,
    visitante as visitante_nome,
    {{ texto_para_inteiro('placar_mandante') }} as gols_mandante,
    {{ texto_para_inteiro('placar_visitante') }} as gols_visitante,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from {{ source('raw', 'fdorg_jogos') }}
