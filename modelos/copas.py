"""Calendário das copas (Libertadores, Sul-Americana, Copa do Brasil) por time.

Fonte: a mesma API pública da ESPN usada na Série A (sem chave), um arquivo
por liga e ano civil em dados/brutos/espn_copas/<liga>/<ano>.json. A ESPN tem
Libertadores e Sul-Americana desde 2012 e a Copa do Brasil desde 2013.

Times: pelo id da ESPN, o mesmo nas copas e na Série A. O id vira time_id
pelos nomes da Série A (seed de_para_times, fonte espn); id que nunca jogou a
Série A (estrangeiros, times de divisões de baixo) fica de fora, o que não
muda nada: o fator só olha times da Série A.

Data: a ESPN dá a hora em UTC; o dia usado é o de Brasília, como na Série A.

Uso no teste do fator (analise/fase2_copas.py). Ainda fora do dbt: se o fator
entrar no modelo, a carga passa para ingestao/ e dbt/.
"""
from __future__ import annotations

import csv
import json

import pandas as pd

from ingestao.comum import BRUTOS, RAIZ, baixar

LIGAS = {"conmebol.libertadores": "libertadores", "conmebol.sudamericana": "sul_americana",
         "bra.copa_do_brazil": "copa_do_brasil"}
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard?dates={ano}&limit=1000"
PASTA = BRUTOS / "espn_copas"
PASTA_SERIE_A = BRUTOS / "espn"
DE_PARA = RAIZ / "dbt" / "seeds" / "de_para_times.csv"
# 2011 entra só para o descanso dos primeiros jogos de 2012
ANOS = range(2011, 2027)


def baixar_copas(anos=ANOS, refazer_ano: int | None = None) -> None:
    for liga in LIGAS:
        for ano in anos:
            baixar(URL.format(liga=liga, ano=ano), PASTA / liga / f"{ano}.json", pausa=0.5,
                   refazer=ano == refazer_ano)


def _nome_para_time() -> dict:
    """(nome na ESPN, temporada) -> time_id; temporada None = qualquer uma."""
    m = {}
    with DE_PARA.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["fonte"] != "espn":
                continue
            de = int(r["temporada_de"]) if r["temporada_de"] else None
            ate = int(r["temporada_ate"]) if r["temporada_ate"] else None
            m.setdefault(r["nome_na_fonte"], []).append((de, ate, r["time_id"]))
    return m


def id_espn_para_time() -> dict:
    """id do time na ESPN -> time_id, pelos jogos de Série A desde 2011."""
    nomes = _nome_para_time()
    ids: dict[str, set] = {}
    for arq in sorted(PASTA_SERIE_A.glob("*.json")):
        for e in json.loads(arq.read_text(encoding="utf-8")).get("events", []):
            temporada = e.get("season", {}).get("year")
            if temporada is None or temporada < 2011:
                continue
            for c in e["competitions"][0]["competitors"]:
                nome = c["team"]["displayName"]
                for de, ate, time_id in nomes.get(nome, []):
                    if (de is None or de <= temporada) and (ate is None or temporada <= ate):
                        ids.setdefault(c["team"]["id"], set()).add(time_id)
    duplos = {k: v for k, v in ids.items() if len(v) > 1}
    if duplos:
        raise ValueError(f"id da ESPN com mais de um time: {duplos}")
    return {k: v.pop() for k, v in ids.items()}


def carregar_copas(ate_ano: int) -> pd.DataFrame:
    """Um registro por (jogo de copa, time da Série A), com data até 31/12 de
    `ate_ano` (pelo dia de Brasília). Colunas: time_id, data, copa, fase,
    status, id_espn."""
    ids = id_espn_para_time()
    linhas, vistos = [], set()
    for liga, copa in LIGAS.items():
        for ano in ANOS:
            arq = PASTA / liga / f"{ano}.json"
            if ano > ate_ano or not arq.exists():
                continue
            for e in json.loads(arq.read_text(encoding="utf-8")).get("events", []):
                if (liga, e["id"]) in vistos:
                    continue
                vistos.add((liga, e["id"]))
                c = e["competitions"][0]
                for t in c["competitors"]:
                    time_id = ids.get(t["team"]["id"])
                    if time_id is not None:
                        linhas.append({"time_id": time_id, "data_utc": e["date"], "copa": copa,
                                       "fase": e.get("season", {}).get("slug"),
                                       "status": c["status"]["type"]["name"], "id_espn": e["id"]})
    df = pd.DataFrame(linhas, columns=["time_id", "data_utc", "copa", "fase", "status", "id_espn"])
    df["data"] = (pd.to_datetime(df["data_utc"], utc=True).dt.tz_convert("America/Sao_Paulo")
                  .dt.tz_localize(None).dt.normalize())
    # jogo adiado ou cancelado não cansa ninguém; agendado fica (calendário futuro)
    df = df[~df["status"].isin(["STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_ABANDONED"])]
    df = df[df["data"].dt.year <= ate_ano]
    return df.drop(columns="data_utc").sort_values(["time_id", "data"]).reset_index(drop=True)
