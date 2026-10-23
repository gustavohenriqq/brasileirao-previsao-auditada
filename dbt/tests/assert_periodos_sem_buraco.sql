-- Os períodos de torcida cobrem 2003 a 2025 sem buraco nem sobreposição:
-- cada período começa no dia seguinte ao fim do anterior.
select periodo, inicio, anterior_fim
from (
    select periodo, inicio, lag(fim) over (order by inicio) as anterior_fim
    from {{ ref('periodos_torcida') }}
) as p
where anterior_fim is not null and inicio <> anterior_fim + 1
