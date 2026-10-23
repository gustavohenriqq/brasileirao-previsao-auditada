-- Uma linha = uma fonte em uma temporada: quanto da base ela confirma.
select
    fonte,
    temporada,
    count(*) filter (where situacao <> 'so_na_fonte') as jogos_base,
    count(*) filter (where situacao <> 'so_na_base') as jogos_fonte,
    count(*) filter (where situacao = 'confere') as confere,
    count(*) filter (where situacao = 'placar_diverge') as placar_diverge,
    count(*) filter (where situacao = 'so_na_base') as so_na_base,
    count(*) filter (where situacao = 'so_na_fonte') as so_na_fonte,
    count(*) filter (where situacao = 'nao_encerrado_na_fonte') as nao_encerrado_na_fonte,
    count(*) filter (where rodada_confere = false) as rodada_diverge,
    count(*) filter (where diferenca_dias > 1) as data_diverge_mais_de_1_dia,
    count(*) filter (where situacao <> 'confere' and explicacao is not null) as divergencias_explicadas
from {{ ref('conferencia_fontes') }}
group by fonte, temporada
