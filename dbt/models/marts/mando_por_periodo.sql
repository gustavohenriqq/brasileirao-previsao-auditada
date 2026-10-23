-- Uma linha = um período de torcida. Denominador de todas as taxas: jogos
-- disputados no período. É a segunda conta dos números da análise em Python
-- (analise/fase1_mando.py confere contra esta tabela antes de escrever).
select
    periodo,
    periodo_ordem,
    count(*) as jogos,
    min(data) as primeiro_jogo,
    max(data) as ultimo_jogo,
    avg((resultado = 'M')::int) as taxa_vitoria_mandante,
    avg((resultado = 'E')::int) as taxa_empate,
    avg((resultado = 'V')::int) as taxa_vitoria_visitante,
    avg(pontos_mandante) as pontos_por_jogo_mandante,
    avg(pontos_visitante) as pontos_por_jogo_visitante,
    avg(pontos_mandante - pontos_visitante) as vantagem_pontos,
    avg(saldo_mandante) as saldo_medio_mandante,
    avg(gols_mandante) as gols_mandante,
    avg(gols_visitante) as gols_visitante
from {{ ref('mando_jogos') }}
group by periodo, periodo_ordem
