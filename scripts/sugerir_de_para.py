"""Propõe o de-para de nomes de time de cada fonte para o nome da base
(adaoduque), casando jogos em vez de comparar textos.

Para cada jogo de uma fonte, procura na base os jogos da mesma temporada com o
mesmo placar e data a no máximo 1 dia (fuso UTC e horário inglês empurram
jogos noturnos para o dia seguinte). Quando há um único candidato, ele vota:
mandante da fonte -> mandante da base, visitante idem. O nome mais votado vence.

Saída: dbt/seeds/de_para_times.csv. O arquivo é revisado à mão antes de ir
para o Git; a coluna `votos`/`concordancia` mostra a força de cada proposta.

Uso: python scripts/sugerir_de_para.py
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ, conectar  # noqa: E402


def _data_br(s: str, ano_padrao: int | None = None) -> date | None:
    partes = s.split("/")
    if len(partes) == 2 and ano_padrao:
        partes.append(str(ano_padrao))
    d, m, a = (int(p) for p in partes)
    if a < 100:
        a += 2000
    return date(a, m, d)


def base(cur) -> dict[int, list[tuple]]:
    cur.execute("select data, mandante, visitante, placar_mandante, placar_visitante,"
                " temporada_arquivo from raw.adaoduque_jogos")
    por_temp: dict[int, list[tuple]] = defaultdict(list)
    for data_txt, m, v, pm, pv, temp in cur.fetchall():
        d = _data_br(data_txt, int(temp) if temp else None)
        # Única temporada que atravessa o ano entre 2003 e 2025: 2020 (até fev/2021).
        t = int(temp) if temp else (2020 if date(2021, 1, 1) <= d <= date(2021, 3, 31) else d.year)
        por_temp[t].append((d, m, v, int(pm), int(pv)))
    return por_temp


def jogos_fonte(cur, fonte: str):
    if fonte == "mendeley":
        cur.execute("select data, mandante, visitante, placar from raw.mendeley_jogos")
        for d, m, v, p in cur.fetchall():
            dd = _data_br(d)
            pm, pv = p.lower().split("x")
            yield dd.year, dd, m, v, int(pm), int(pv)
    elif fonte == "fdcouk":
        cur.execute("select season, date, home, away, hg, ag from raw.fdcouk_jogos")
        for s, d, m, v, pm, pv in cur.fetchall():
            if pm is None:
                continue
            yield int(s), _data_br(d), m, v, int(pm), int(pv)
    elif fonte in ("espn", "fdorg"):
        cur.execute(f"select temporada, data_utc, mandante, visitante, placar_mandante,"
                    f" placar_visitante from raw.{fonte}_jogos")
        for t, d, m, v, pm, pv in cur.fetchall():
            if pm is None:
                continue
            dd = datetime.fromisoformat(d.replace("Z", "+00:00")).date()
            yield int(t), dd, m, v, int(pm), int(pv)
    elif fonte == "openfootball":
        cur.execute("select temporada, data, mandante, visitante, placar_mandante,"
                    " placar_visitante from raw.openfootball_jogos")
        for t, d, m, v, pm, pv in cur.fetchall():
            if pm is None:
                continue
            yield int(t), date.fromisoformat(d), m, v, int(pm), int(pv)


def main() -> None:
    with conectar() as con, con.cursor() as cur:
        b = base(cur)
        saida = []
        nomes_base = sorted({j[1] for js in b.values() for j in js})
        for nome in nomes_base:
            saida.append({"fonte": "adaoduque", "nome_na_fonte": nome, "time_id": nome,
                          "votos": "", "concordancia": ""})
        for fonte in ("mendeley", "fdcouk", "espn", "openfootball", "fdorg"):
            votos: dict[str, Counter] = defaultdict(Counter)
            nomes = set()
            for t, d, m, v, pm, pv in jogos_fonte(cur, fonte):
                nomes.update((m, v))
                cands = [j for j in b.get(t, [])
                         if j[3] == pm and j[4] == pv and abs((j[0] - d).days) <= 1]
                if len(cands) == 1:
                    votos[m][cands[0][1]] += 1
                    votos[v][cands[0][2]] += 1
            for nome in sorted(nomes):
                c = votos.get(nome)
                if not c:
                    saida.append({"fonte": fonte, "nome_na_fonte": nome, "time_id": "",
                                  "votos": 0, "concordancia": ""})
                    continue
                alvo, n = c.most_common(1)[0]
                saida.append({"fonte": fonte, "nome_na_fonte": nome, "time_id": alvo,
                              "votos": n, "concordancia": f"{n / sum(c.values()):.2f}"})
    destino = RAIZ / "dbt" / "seeds" / "de_para_times.csv"
    with destino.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0]))
        w.writeheader()
        w.writerows(saida)
    fracos = [s for s in saida if s["fonte"] != "adaoduque"
              and (not s["time_id"] or float(s["concordancia"] or 0) < 0.9)]
    print(f"{len(saida)} nomes gravados em {destino.relative_to(RAIZ)}")
    print(f"{len(fracos)} para revisar com cuidado (sem voto ou concordância < 0,90):")
    for s in fracos:
        print("  ", s)


if __name__ == "__main__":
    main()
