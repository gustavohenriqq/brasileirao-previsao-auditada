"""Gera dbt/seeds/divergencias_explicadas.csv a partir de marts.conferencia_fontes.

Cada divergência recebe uma explicação por regra. As regras saíram da
investigação de 23/10/2026 (ver docs/conferencia.md); o desempate externo foi
o RSSSF (tabela final com gols pró e contra de 2003 e 2004, jogo "n/p" de
2016 e datas da rodada 6 de 2009). Divergência nova, que não cai em nenhuma
regra, sai com explicação vazia e o teste em aviso continua contando.

Uso: python scripts/explicar_divergencias.py  (depois: dbt seed + dbt build)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ, conectar  # noqa: E402

CONSULTA = """
with c as (
    select * from marts.conferencia_fontes
    where situacao <> 'confere' or diferenca_dias > 1
),
votos as (
    -- quantas fontes (fora a base) concordam com o placar da base
    select temporada, mandante_id, visitante_id,
           count(*) filter (where situacao = 'confere') as fontes_com_a_base
    from marts.conferencia_fontes
    group by 1, 2, 3
)
select c.fonte, c.temporada, c.mandante_id, c.visitante_id, c.situacao,
       c.diferenca_dias, coalesce(v.fontes_com_a_base, 0),
       f.data_corrigida
from c
left join votos v using (temporada, mandante_id, visitante_id)
left join marts.fct_jogos f using (temporada, mandante_id, visitante_id)
order by c.temporada, c.mandante_id, c.visitante_id, c.fonte
"""


def explicar(fonte, temporada, situacao, dias, com_base, data_corrigida):
    if situacao == "so_na_fonte" and temporada == 2016:
        return ("ausencia", "Chapecoense x Atlético-MG não foi disputado (acidente aéreo "
                "de nov/2016); RSSSF marca n/p. A fonte lista o jogo"
                + (" com 0x0, o que criaria um empate falso" if fonte in ("mendeley", "espn")
                   else " sem placar"))
    if situacao == "nao_encerrado_na_fonte":
        return ("status", "A fonte ficou com status de segundo tempo, mas o placar confere com a base")
    if situacao == "placar_diverge":
        if temporada <= 2004:
            return ("placar", "Base confirmada pelos gols pró e contra da tabela final do RSSSF "
                    "para os dois times; a fonte tem um gol a mais ou a menos")
        return ("placar", f"Base confirmada por {com_base} outra(s) fonte(s); a fonte tem um gol "
                "a mais ou a menos, cara de placar remontado pela lista de gols")
    if dias and dias > 1:
        if data_corrigida:
            return ("data", "Data da base errada (7 ou 14 dias antes); corrigida no fct_jogos pela "
                    "maioria das fontes, conferido no RSSSF em 2009")
        if temporada <= 2005:
            return ("data", "Só a base e esta fonte cobrem o ano, sem desempate; mantida a data da base")
        return ("data", "Data desta fonte diverge; a base é confirmada por outra fonte")
    return ("", "")


def main() -> None:
    with conectar() as con, con.cursor() as cur:
        cur.execute(CONSULTA)
        linhas = cur.fetchall()
    saida, vistos = [], set()
    for fonte, temp, mand, vis, situacao, dias, com_base, corrigida in linhas:
        chave = (fonte, temp, mand, vis)
        if chave in vistos:
            continue
        vistos.add(chave)
        tipo, texto = explicar(fonte, temp, situacao, dias, com_base, corrigida)
        if dias and dias > 1 and tipo != "data":
            texto += "; a data também diverge em mais de 1 dia"
        saida.append([fonte, temp, mand, vis, tipo, texto])
    destino = RAIZ / "dbt" / "seeds" / "divergencias_explicadas.csv"
    with destino.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fonte", "temporada", "mandante_id", "visitante_id", "tipo", "explicacao"])
        w.writerows(saida)
    sem = sum(1 for s in saida if not s[5])
    print(f"{len(saida)} divergências gravadas, {sem} sem explicação")


if __name__ == "__main__":
    main()
