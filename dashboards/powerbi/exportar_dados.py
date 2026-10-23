"""Exporta as marts para os CSVs que o Power BI lê (pasta dados/, fora do Git).

Por que CSV e não conexão direta no Postgres: o relatório abre em qualquer
máquina sem login de banco, e o print do post não depende do Docker ligado.

Grão de jogos_time.csv: um time em um jogo. Cada jogo vira duas linhas (casa e
fora), o que deixa o filtro de time funcionar em todos os visuais.

Uso: python dashboards/powerbi/exportar_dados.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ingestao.comum import conectar  # noqa: E402

PASTA = Path(__file__).resolve().parent / "dados"

JOGOS_TIME = """
with j as (
    select m.*,
        case
            when m.periodo = 'com_torcida_antes' and m.temporada >= 2015 then 'Com torcida 2015-2019'
            when m.periodo = 'sem_torcida' then 'Sem torcida 2020-2021'
            when m.periodo = 'com_torcida_depois' then 'Torcida voltou 2022-2025'
        end as periodo_painel,
        case
            when m.periodo = 'com_torcida_antes' and m.temporada >= 2015 then 1
            when m.periodo = 'sem_torcida' then 2
            when m.periodo = 'com_torcida_depois' then 3
        end as periodo_painel_ordem,
        -- 2020 e 2021 dizem no próprio eixo se tinha torcida ("2021 sem" / "2021 com")
        case m.periodo when 'sem_torcida' then m.temporada || ' sem'
                       when 'volta_parcial' then m.temporada || ' com'
             else m.temporada::text end as bloco,
        m.temporada * 10 + (m.periodo = 'volta_parcial')::int as bloco_ordem,
        case m.periodo when 'sem_torcida' then 'sem' when 'volta_parcial' then 'volta'
             else 'com' end as bloco_tipo,
        case m.resultado when 'M' then 'Vitória do mandante' when 'E' then 'Empate'
             else 'Vitória do visitante' end as resultado_jogo,
        case m.resultado when 'M' then 1 when 'E' then 2 else 3 end as resultado_ordem
    from marts.mando_jogos as m
)
select jogo_id, temporada, rodada, data, periodo, periodo_painel, periodo_painel_ordem,
       bloco, bloco_ordem, bloco_tipo, resultado_jogo, resultado_ordem,
       mandante_id as time_id, visitante_id as adversario_id, 'Casa' as lado,
       gols_mandante as gols_pro, gols_visitante as gols_contra, pontos_mandante as pontos
from j
union all
select jogo_id, temporada, rodada, data, periodo, periodo_painel, periodo_painel_ordem,
       bloco, bloco_ordem, bloco_tipo, resultado_jogo, resultado_ordem,
       visitante_id, mandante_id, 'Fora',
       gols_visitante, gols_mandante, pontos_visitante
from j
order by temporada, data, jogo_id, lado
"""

TIMES = """select time_id, nome, uf, primeira_temporada, ultima_temporada, temporadas_na_serie_a
from marts.dim_times where temporadas_na_serie_a > 0 order by nome"""

# Clubes tradicionais (9+ temporadas na Série A desde 2003, na Série A em
# 2015-2019) que jogaram a Série B no período sem torcida. Entram na tabela do
# painel marcados com "(B)"; os números principais seguem só com a Série A.
TRADICIONAIS_B = ("Cruzeiro", "Vitoria", "Figueirense", "Ponte Preta")

JOGOS_TIME_B = f"""
select jogo_id, temporada, data, mandante_id as time_id, visitante_id as adversario_id, 'Casa' as lado,
       gols_mandante as gols_pro, gols_visitante as gols_contra, pontos_mandante as pontos
from marts.mando_jogos_serie_b
where sem_torcida_de_fato and mandante_id in {TRADICIONAIS_B}
union all
select jogo_id, temporada, data, visitante_id, mandante_id, 'Fora',
       gols_visitante, gols_mandante, pontos_visitante
from marts.mando_jogos_serie_b
where sem_torcida_de_fato and visitante_id in {TRADICIONAIS_B}
order by temporada, data, jogo_id, lado
"""


def exportar(cur, consulta: str, arquivo: str) -> int:
    cur.execute(consulta)
    cols = [c.name for c in cur.description]
    linhas = cur.fetchall()
    with (PASTA / arquivo).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(linhas)
    return len(linhas)


def anexar_escudos(arquivo: Path) -> int:
    """Acrescenta a coluna escudo (imagem PNG em data URI) a times.csv.

    O Power BI mostra a imagem na tabela quando a coluna é marcada como URL de
    imagem. Cada escudo vai sobre um círculo branco, para os escuros não sumirem
    no fundo navy. Escudos em arte/escudos (baixar_escudos.py).
    """
    import base64
    import io

    from PIL import Image, ImageDraw

    pasta = Path(__file__).resolve().parent / "arte" / "escudos"
    with arquivo.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    n = 0
    for linha in linhas:
        linha["nome_tabela"] = linha["nome"] + (" (B)" if linha["time_id"] in TRADICIONAIS_B else "")
        png = pasta / f"{linha['time_id']}.png"
        linha["escudo"] = ""
        if png.exists():
            disco = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
            ImageDraw.Draw(disco).ellipse((0, 0, 71, 71), fill=(255, 255, 255, 255))
            escudo = Image.open(png).convert("RGBA").resize((52, 52), Image.LANCZOS)
            disco.alpha_composite(escudo, (10, 10))
            buf = io.BytesIO()
            disco.save(buf, format="PNG", optimize=True)
            linha["escudo"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            n += 1
    with arquivo.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    return n


def main() -> None:
    PASTA.mkdir(exist_ok=True)
    with conectar() as con, con.cursor() as cur:
        n = exportar(cur, JOGOS_TIME, "jogos_time.csv")
        cur.execute("select count(*) from marts.fct_jogos")
        jogos = cur.fetchone()[0]
        if n != 2 * jogos:
            raise SystemExit(f"jogos_time tem {n} linhas; esperado 2 x {jogos}")
        t = exportar(cur, TIMES, "times.csv")
        b = exportar(cur, JOGOS_TIME_B, "jogos_time_b.csv")
    escudos = anexar_escudos(PASTA / "times.csv")
    print(f"jogos_time.csv: {n} linhas (2 por jogo, {jogos} jogos); times.csv: {t} times, {escudos} com escudo; jogos_time_b.csv: {b} linhas")


if __name__ == "__main__":
    main()
