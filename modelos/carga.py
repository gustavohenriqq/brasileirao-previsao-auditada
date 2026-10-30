"""Carga dos jogos da Série A a partir do banco (marts.fct_jogos).

Devolve um DataFrame em ordem de data (desempate por jogo_id), com a data em
datetime64 e as odds em float. O parâmetro `ate_temporada` corta a base já na
consulta: quem calibra hiperparâmetros (até 2011) ou valida (até 2025) nem
chega a ler as temporadas do teste final. Sem corte, ou com corte em 2026,
a carga recusa, a menos que `permitir_teste=True`.

Uso:
    from modelos.carga import carregar_jogos
    jogos = carregar_jogos(ate_temporada=2025)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import conectar  # noqa: E402

# Outro processo pode estar recriando os marts via dbt: a tabela some por
# alguns segundos. Tenta de novo antes de desistir.
TENTATIVAS = 6
PAUSA_SEGUNDOS = 10

COLUNAS = [
    "jogo_id", "temporada", "rodada", "data", "mandante_id", "visitante_id",
    "gols_mandante", "gols_visitante", "resultado",
    "odd_pinnacle_mandante", "odd_pinnacle_empate", "odd_pinnacle_visitante",
    "odd_media_mandante", "odd_media_empate", "odd_media_visitante",
]
COLUNAS_ODDS = [c for c in COLUNAS if c.startswith("odd_")]
PRIMEIRA_TESTE = 2026


def _consultar(sql: str, parametros: tuple) -> list[tuple]:
    for tentativa in range(TENTATIVAS):
        try:
            with conectar() as con, con.cursor() as cur:
                cur.execute(sql, parametros)
                return cur.fetchall()
        except psycopg2.errors.UndefinedTable:
            if tentativa == TENTATIVAS - 1:
                raise
            time.sleep(PAUSA_SEGUNDOS)
    return []


def carregar_jogos(ate_temporada: int | None = None,
                   desde_temporada: int | None = None,
                   permitir_teste: bool = False) -> pd.DataFrame:
    """Jogos disputados (com placar), ordenados por data e jogo_id."""
    if not permitir_teste and (ate_temporada is None or ate_temporada >= PRIMEIRA_TESTE):
        raise ValueError(f"{PRIMEIRA_TESTE} é o teste final: passe ate_temporada < "
                         f"{PRIMEIRA_TESTE} ou permitir_teste=True.")
    filtros, parametros = ["gols_mandante is not null"], []
    if ate_temporada is not None:
        filtros.append("temporada <= %s")
        parametros.append(ate_temporada)
    if desde_temporada is not None:
        filtros.append("temporada >= %s")
        parametros.append(desde_temporada)
    sql = (f"select {', '.join(COLUNAS)} from marts.fct_jogos "
           f"where {' and '.join(filtros)} order by data, jogo_id")
    linhas = _consultar(sql, tuple(parametros))
    jogos = pd.DataFrame(linhas, columns=COLUNAS)
    jogos["data"] = pd.to_datetime(jogos["data"])
    for c in ("temporada", "rodada", "gols_mandante", "gols_visitante"):
        jogos[c] = jogos[c].astype(int)
    for c in COLUNAS_ODDS:
        jogos[c] = pd.to_numeric(jogos[c], errors="coerce").astype(float)
    return jogos.reset_index(drop=True)
