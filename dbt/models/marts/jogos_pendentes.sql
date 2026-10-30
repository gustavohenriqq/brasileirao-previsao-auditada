-- Uma linha = um jogo da temporada em andamento que ainda não foi encerrado
-- no football-data.org (a base de 2026), já com o id dos times do projeto
-- (mesmo de-para do int_jogos__base). Entra o adiado (POSTPONED). Somado ao
-- fct_jogos da temporada, fecha os 380 jogos (ver testes).
-- Data: jogo com horário marcado (TIMED) usa a data de Brasília, como o resto
-- do projeto. Sem horário (SCHEDULED), a fonte grava só o dia, às 00:00 UTC,
-- e converter para Brasília jogaria a data para o dia anterior: vale o dia
-- UTC. Adiado sem nova data fica com data_prevista nula (a fonte mantém a
-- data original, que fica em data_na_fonte).
with fdorg as (
    select
        *,
        case
            when status = 'TIMED' then data
            else (inicio_utc at time zone 'UTC')::date
        end as data_na_fonte
    from ({{ juntar_de_para(ref('stg_fdorg__jogos'), 'fdorg') }}) as j
)

select
    id_na_fonte as id_fdorg,
    temporada,
    rodada,
    case when status <> 'POSTPONED' then data_na_fonte end as data_prevista,
    data_na_fonte,
    status = 'TIMED' as horario_definido,
    mandante_id,
    visitante_id,
    status as status_fonte
from fdorg
where not encerrado
    and temporada = {{ var('temporada_em_andamento') }}
