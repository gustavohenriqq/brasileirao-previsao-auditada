-- Uma linha = um jogo da base comparado com uma fonte que cobre aquela
-- temporada (ou um jogo que só a fonte tem). A chave é temporada + mandante +
-- visitante: em pontos corridos cada par se enfrenta uma vez com cada mando.
-- Divergência não é apagada: fica aqui, com a explicação quando já apurada.
with jogos as (
    select * from {{ ref('int_jogos__fontes') }}
),

base as (
    select * from jogos where fonte = 'base'
),

outras as (
    select * from jogos where fonte <> 'base'
),

cobertura as (
    select distinct fonte, temporada from outras
),

base_por_fonte as (
    select
        c.fonte,
        b.temporada,
        b.rodada,
        b.data,
        b.mandante_id,
        b.visitante_id,
        b.gols_mandante,
        b.gols_visitante
    from base as b
    inner join cobertura as c on c.temporada = b.temporada
),

comparado as (
    select
        coalesce(b.fonte, o.fonte) as fonte,
        coalesce(b.temporada, o.temporada) as temporada,
        coalesce(b.mandante_id, o.mandante_id) as mandante_id,
        coalesce(b.visitante_id, o.visitante_id) as visitante_id,
        b.rodada as rodada_base,
        o.rodada as rodada_fonte,
        b.data as data_base,
        o.data as data_fonte,
        b.gols_mandante as gols_mandante_base,
        b.gols_visitante as gols_visitante_base,
        o.gols_mandante as gols_mandante_fonte,
        o.gols_visitante as gols_visitante_fonte,
        o.encerrado as encerrado_na_fonte,
        case
            when b.temporada is null then 'so_na_fonte'
            when o.temporada is null then 'so_na_base'
            -- Temporada em andamento: a fonte ainda não atualizou o jogo.
            -- Muda a cada rodada e não é divergência.
            when not o.encerrado
                and b.temporada = {{ var('temporada_em_andamento') }} then 'pendente_na_fonte'
            when not o.encerrado then 'nao_encerrado_na_fonte'
            when (b.gols_mandante, b.gols_visitante)
                is distinct from (o.gols_mandante, o.gols_visitante) then 'placar_diverge'
            else 'confere'
        end as situacao
    from base_por_fonte as b
    full outer join outras as o
        on o.fonte = b.fonte
        and o.temporada = b.temporada
        and o.mandante_id = b.mandante_id
        and o.visitante_id = b.visitante_id
)

select
    c.*,
    -- Data de jogo pendente é a marcação antiga: não entra na comparação.
    case when c.situacao <> 'pendente_na_fonte' then abs(c.data_base - c.data_fonte) end
        as diferenca_dias,
    case
        when c.rodada_base is null or c.rodada_fonte is null then null
        else c.rodada_base = c.rodada_fonte
    end as rodada_confere,
    e.explicacao
from comparado as c
left join {{ ref('divergencias_explicadas') }} as e
    on e.fonte = c.fonte
    and e.temporada = c.temporada
    and e.mandante_id = c.mandante_id
    and e.visitante_id = c.visitante_id
-- Na temporada em andamento, os jogos ainda por disputar só existem nas
-- fontes: não são divergência.
where not (
    c.situacao = 'so_na_fonte'
    and not c.encerrado_na_fonte
    and c.temporada = {{ var('temporada_em_andamento') }}
)
