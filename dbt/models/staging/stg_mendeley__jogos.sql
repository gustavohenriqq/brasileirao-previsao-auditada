-- Uma linha = um jogo do arquivo matches-2003-2019.txt (Mendeley Data).
-- Nomes vêm com a UF ("Atlético/MG"); o campo ROUND é o turno (1 ou 2), não
-- a rodada. Nenhuma temporada de 2003 a 2019 atravessou o ano.
select
    null::text as id_na_fonte,
    extract(year from to_date(data, 'DD/MM/YYYY'))::integer as temporada,
    {{ texto_para_inteiro('turno') }} as turno,
    to_date(data, 'DD/MM/YYYY') as data,
    case when hora ~ '^\d{1,2}:\d{2}$' then hora::time end as hora,
    mandante as mandante_nome,
    visitante as visitante_nome,
    {{ texto_para_inteiro("split_part(lower(placar), 'x', 1)") }} as gols_mandante,
    {{ texto_para_inteiro("split_part(lower(placar), 'x', 2)") }} as gols_visitante,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from {{ source('raw', 'mendeley_jogos') }}
