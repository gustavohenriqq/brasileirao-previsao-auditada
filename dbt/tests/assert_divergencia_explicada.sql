-- Toda divergência entre fontes precisa de uma linha em
-- seeds/divergencias_explicadas.csv. Em aviso: divergência nova não derruba o
-- build, mas aparece aqui até ser investigada.
{{ config(severity='warn') }}
select fonte, temporada, mandante_id, visitante_id, situacao, diferenca_dias
from {{ ref('conferencia_fontes') }}
where (situacao <> 'confere' or diferenca_dias > 1)
  and explicacao is null
