-- Uma linha = um jogo da base adaoduque.
-- O CSV (até 2024) não diz a temporada: ela vem da data. A única temporada
-- de 2003 a 2025 que atravessou o ano foi 2020, que terminou em fev/2021.
-- O JSON de 2025 traz a temporada no nome do arquivo e algumas datas sem ano.
with fonte as (
    select * from {{ source('raw', 'adaoduque_jogos') }}
),

datas as (
    select
        *,
        case
            when data ~ '^\d{2}/\d{2}/\d{4}$' then to_date(data, 'DD/MM/YYYY')
            when data ~ '^\d{2}/\d{2}/\d{2}$' then to_date(data, 'DD/MM/YY')
            when data ~ '^\d{1,2}/\d{1,2}$' and temporada_arquivo is not null
                then to_date(data || '/' || temporada_arquivo, 'DD/MM/YYYY')
        end as data_jogo
    from fonte
)

select
    id as id_na_fonte,
    case
        when temporada_arquivo is not null then temporada_arquivo::integer
        when data_jogo between date '2021-01-01' and date '2021-03-31' then 2020
        else extract(year from data_jogo)::integer
    end as temporada,
    {{ texto_para_inteiro('rodada') }} as rodada,
    data_jogo as data,
    case when hora ~ '^\d{1,2}:\d{2}$' then hora::time end as hora,
    mandante as mandante_nome,
    visitante as visitante_nome,
    {{ texto_para_inteiro('placar_mandante') }} as gols_mandante,
    {{ texto_para_inteiro('placar_visitante') }} as gols_visitante,
    nullif(trim(arena), '') as estadio,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from datas
