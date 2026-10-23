-- Uma linha = um jogo, com o período de torcida e o resultado do ponto de
-- vista do mandante. Base da análise da Fase 1 (docs/fase1-mando-de-campo.md).
-- O período sai da data do jogo (já corrigida na Fase 0), não da temporada:
-- 2021 tem jogos sem torcida e jogos com a volta parcial do público.
select
    f.jogo_id,
    f.temporada,
    f.rodada,
    f.data,
    p.periodo,
    p.ordem as periodo_ordem,
    f.mandante_id,
    f.visitante_id,
    f.gols_mandante,
    f.gols_visitante,
    f.resultado,
    case f.resultado when 'M' then 3 when 'E' then 1 else 0 end as pontos_mandante,
    case f.resultado when 'V' then 3 when 'E' then 1 else 0 end as pontos_visitante,
    f.gols_mandante - f.gols_visitante as saldo_mandante,
    f.publico_espn
from {{ ref('fct_jogos') }} as f
left join {{ ref('periodos_torcida') }} as p
    on f.data between p.inicio and p.fim
