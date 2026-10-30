-- Uma linha = um time em um jogo da Série A (jogo_id, time_id), com as
-- estatísticas da ESPN. O jogo da ESPN casa com o fct_jogos pelo mesmo
-- caminho que o fct_jogos usa para o público: de-para dos nomes da ESPN e
-- temporada + mandante + visitante, só eventos encerrados.
--
-- Jogo sem estatística não tem linha (nunca zero no lugar de ausente). A ESPN
-- publica a lista mesmo quando não tem o dado, e o vazio vem de três jeitos:
--   1. molde zerado: posse, chutes, escanteios e faltas iguais a zero. Se um
--      dos lados vem assim (às vezes só um), o jogo inteiro sai: posse e
--      chutes cedidos dependem do outro lado;
--   2. chutes copiados dos gols: em 2008 e 2009 (e em parte de 2010 a 2012)
--      chutes = chutes no gol = gols da lista nos dois lados, sem escanteio
--      nem falta. Não é chute medido: chutes e chutes no gol viram nulos;
--   3. campo que soma zero nos dois lados não foi coletado naquele jogo e
--      vira nulo (posse até 2013, escanteios e faltas em parte de 2010).
-- Sobra jogo só se algum campo real ficar de pé e os dois lados tiverem a lista.
-- Cobertura por época: 2006 a 2009 nada; 2010 a 2013 chutes, escanteios e
-- faltas; 2014 em diante tudo.
with espn as (
    {{ juntar_de_para(ref('stg_espn__jogos'), 'espn') }}
),

jogos as (
    select
        f.jogo_id,
        f.temporada,
        f.data,
        f.mandante_id,
        f.visitante_id,
        f.gols_mandante,
        f.gols_visitante,
        e.id_na_fonte as id_espn
    from {{ ref('fct_jogos') }} as f
    inner join espn as e
        on e.temporada = f.temporada
        and e.mandante_id = f.mandante_id
        and e.visitante_id = f.visitante_id
        and e.encerrado
),

lados as (
    select
        *,
        posse_pct + chutes + escanteios + faltas = 0 as lado_vazio,
        chutes = chutes_no_gol and chutes = gols as chutes_iguais_gols
    from {{ ref('stg_espn__estatisticas') }}
    where encerrado
),

por_jogo as (
    select
        id_na_fonte,
        count(*) as lados,
        bool_or(lado_vazio) as algum_lado_vazio,
        sum(posse_pct) > 0 as tem_posse,
        sum(chutes) > 0 and not bool_and(chutes_iguais_gols) as tem_chutes,
        sum(escanteios) > 0 as tem_escanteios,
        sum(faltas) > 0 as tem_faltas
    from lados
    group by id_na_fonte
),

validos as (
    select *
    from por_jogo
    where lados = 2
        and not algum_lado_vazio
        and (tem_posse or tem_chutes or tem_escanteios or tem_faltas)
)

select
    j.jogo_id,
    j.id_espn,
    j.temporada,
    j.data,
    case l.mando when 'casa' then j.mandante_id else j.visitante_id end as time_id,
    case l.mando when 'casa' then j.visitante_id else j.mandante_id end as adversario_id,
    l.mando,
    case when v.tem_posse then l.posse_pct end as posse_pct,
    case when v.tem_chutes then l.chutes end as chutes,
    case when v.tem_chutes then l.chutes_no_gol end as chutes_no_gol,
    case when v.tem_escanteios then l.escanteios end as escanteios,
    case when v.tem_faltas then l.faltas end as faltas,
    case l.mando when 'casa' then j.gols_mandante else j.gols_visitante end as gols,
    l.gols as gols_espn
from jogos as j
inner join validos as v on v.id_na_fonte = j.id_espn
inner join lados as l on l.id_na_fonte = j.id_espn
