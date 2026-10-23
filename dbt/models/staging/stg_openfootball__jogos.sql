-- Uma linha = um jogo dos arquivos Football.TXT do openfootball/brazil.
select
    null::text as id_na_fonte,
    temporada::integer as temporada,
    {{ texto_para_inteiro('rodada') }} as rodada,
    data::date as data,
    case when hora ~ '^\d{1,2}[:.]\d{2}$' then replace(hora, '.', ':')::time end as hora,
    mandante as mandante_nome,
    visitante as visitante_nome,
    {{ texto_para_inteiro('placar_mandante') }} as gols_mandante,
    {{ texto_para_inteiro('placar_visitante') }} as gols_visitante,
    linha_original,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from {{ source('raw', 'openfootball_jogos') }}
