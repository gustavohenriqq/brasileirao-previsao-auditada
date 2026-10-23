-- Uma linha = um jogo do BRA.csv (football-data.co.uk), só 2003 a 2025.
-- Odds de fechamento: Pinnacle, máxima e média do mercado, Betfair Exchange e
-- bet365. Entram só como régua de comparação na Fase 2, nunca como dica.
select
    null::text as id_na_fonte,
    season::integer as temporada,
    to_date(date, 'DD/MM/YYYY') as data,
    case when time ~ '^\d{1,2}:\d{2}$' then time::time end as hora_reino_unido,
    home as mandante_nome,
    away as visitante_nome,
    {{ texto_para_inteiro('hg') }} as gols_mandante,
    {{ texto_para_inteiro('ag') }} as gols_visitante,
    res as resultado_fonte,
    {{ texto_para_decimal('psch') }} as odd_pinnacle_mandante,
    {{ texto_para_decimal('pscd') }} as odd_pinnacle_empate,
    {{ texto_para_decimal('psca') }} as odd_pinnacle_visitante,
    {{ texto_para_decimal('avgch') }} as odd_media_mandante,
    {{ texto_para_decimal('avgcd') }} as odd_media_empate,
    {{ texto_para_decimal('avgca') }} as odd_media_visitante,
    {{ texto_para_decimal('maxch') }} as odd_maxima_mandante,
    {{ texto_para_decimal('maxcd') }} as odd_maxima_empate,
    {{ texto_para_decimal('maxca') }} as odd_maxima_visitante,
    {{ texto_para_decimal('bfech') }} as odd_betfair_mandante,
    {{ texto_para_decimal('bfecd') }} as odd_betfair_empate,
    {{ texto_para_decimal('bfeca') }} as odd_betfair_visitante,
    {{ texto_para_decimal('b365ch') }} as odd_bet365_mandante,
    {{ texto_para_decimal('b365cd') }} as odd_bet365_empate,
    {{ texto_para_decimal('b365ca') }} as odd_bet365_visitante,
    _arquivo as arquivo,
    _carregado_em as carregado_em
from {{ source('raw', 'fdcouk_jogos') }}
where season::integer between {{ var('primeira_temporada') }} and {{ var('ultima_temporada') }}
