"""Backtest por bloco (temporada, rodada), em ordem de data, sem vazamento.

Regra (docs/fase2-plano.md): para prever o bloco, o modelo treina só com os
jogos de data menor que a primeira data do bloco. Jogo adiado fica de fora do
treino até ser jogado (entra pela data em que aconteceu) e é previsto junto com
o bloco da sua rodada, com o que se sabia antes do início dessa rodada.

Um "modelo" é qualquer objeto com:
    nome: str
    ajustar(jogos_passados: DataFrame) -> None
    prever(jogos_do_bloco: DataFrame) -> Previsao
O bloco chega a `prever` sem as colunas de resultado (gols, resultado,
público): o modelo não tem como olhar o placar do jogo que está prevendo.

Uso:
    from modelos.backtest import rodar_backtest
    prev = rodar_backtest(jogos, [Ingenua(), Elo()], 2012, 2022)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd

# Informação que só existe depois do jogo: nunca chega a prever().
COLUNAS_POS_JOGO = ["gols_mandante", "gols_visitante", "resultado", "publico_espn"]
COLUNAS_ID = ["jogo_id", "temporada", "rodada", "data", "mandante_id", "visitante_id",
              "gols_mandante", "gols_visitante", "resultado"]


@dataclass
class Previsao:
    """Saída de um modelo para os jogos de um bloco, na ordem recebida."""
    probs: np.ndarray                      # (n, 3): mandante, empate, visitante
    placares: np.ndarray | None = None     # (n, G+1, G+1): [i, j] = mandante i x j visitante
    extras: dict[str, np.ndarray] = field(default_factory=dict)  # colunas extras por jogo


class Modelo(Protocol):
    nome: str

    def ajustar(self, jogos_passados: pd.DataFrame) -> None: ...

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao: ...


@dataclass
class Bloco:
    temporada: int
    rodada: int
    primeira_data: pd.Timestamp
    indices: np.ndarray  # posições no DataFrame de jogos


def montar_blocos(jogos: pd.DataFrame) -> list[Bloco]:
    """Blocos (temporada, rodada) em ordem da primeira data."""
    blocos = []
    for (t, r), g in jogos.groupby(["temporada", "rodada"], sort=False):
        blocos.append(Bloco(int(t), int(r), g["data"].min(), g.index.to_numpy()))
    blocos.sort(key=lambda b: (b.primeira_data, b.temporada, b.rodada))
    return blocos


def rodar_backtest(jogos: pd.DataFrame, modelos: list, temporada_inicio: int,
                   temporada_fim: int, guardar_placares: bool = False,
                   ao_treinar=None) -> tuple[pd.DataFrame, dict]:
    """Prevê todos os blocos de temporada_inicio a temporada_fim.

    `jogos` precisa estar em ordem de data com índice 0..n-1 (como sai de
    carga.carregar_jogos). O treino de cada bloco é o prefixo jogos[:pos], com
    pos = primeiro jogo com data >= primeira data do bloco.

    `ao_treinar(bloco, passados)` é um gancho opcional (usado nos testes de
    vazamento). Devolve (previsões por jogo, placares por modelo), em que
    placares[nome] é um dict jogo_id -> matriz quando guardar_placares=True.
    """
    jogos = jogos.reset_index(drop=True)
    datas = jogos["data"].to_numpy()
    if np.any(datas[1:] < datas[:-1]):
        raise ValueError("jogos precisa estar em ordem de data")

    linhas, placares = [], {m.nome: {} for m in modelos}
    for bloco in montar_blocos(jogos):
        if not (temporada_inicio <= bloco.temporada <= temporada_fim):
            continue
        pos = int(np.searchsorted(datas, bloco.primeira_data.to_datetime64(), side="left"))
        passados = jogos.iloc[:pos]
        alvo = jogos.iloc[bloco.indices]
        cego = alvo.drop(columns=[c for c in COLUNAS_POS_JOGO if c in alvo.columns])
        if ao_treinar is not None:
            ao_treinar(bloco, passados)

        saida = alvo[[c for c in COLUNAS_ID if c in alvo.columns]].copy()
        for m in modelos:
            m.ajustar(passados)
            p = m.prever(cego)
            saida[f"{m.nome}_m"] = p.probs[:, 0]
            saida[f"{m.nome}_e"] = p.probs[:, 1]
            saida[f"{m.nome}_v"] = p.probs[:, 2]
            for k, v in p.extras.items():
                saida[f"{m.nome}_{k}"] = v
            if guardar_placares and p.placares is not None:
                for jid, mat in zip(alvo["jogo_id"], p.placares):
                    placares[m.nome][jid] = mat
        linhas.append(saida)

    previsoes = pd.concat(linhas, ignore_index=True) if linhas else pd.DataFrame()
    return previsoes, placares


def probs_do_modelo(previsoes: pd.DataFrame, nome: str) -> np.ndarray:
    return previsoes[[f"{nome}_m", f"{nome}_e", f"{nome}_v"]].to_numpy(dtype=float)
