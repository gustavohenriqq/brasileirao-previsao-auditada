"""Réguas de comparação: ingênua e mercado.

- Ingênua: frequências de mandante, empate e visitante nas 5 temporadas
  anteriores à do bloco. Nos primeiros anos usa as temporadas que houver; sem
  nenhuma temporada anterior (2003), usa os jogos já disputados da própria
  temporada (antes do bloco), e sem nenhum jogo, 1/3 para cada.
- Mercado: odds sem a margem da casa, por dois métodos:
  * proporcional: divide cada 1/odd pela soma das três;
  * Shin (1993): supõe uma fração z de apostadores com informação privilegiada
    e tira mais margem das zebras do que dos favoritos.
  Usa a Pinnacle quando há as três odds; senão, a média do mercado. A coluna
  extra `fonte` diz qual foi usada (pinnacle, media ou sem_odds).

Uso:
    from modelos.reguas import Ingenua, Mercado, sem_margem_proporcional, sem_margem_shin
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from modelos.backtest import Previsao

TEMPORADAS_INGENUA = 5
ODDS_PINNACLE = ["odd_pinnacle_mandante", "odd_pinnacle_empate", "odd_pinnacle_visitante"]
ODDS_MEDIA = ["odd_media_mandante", "odd_media_empate", "odd_media_visitante"]


# ---------------------------------------------------------------------------
# Ingênua
# ---------------------------------------------------------------------------
class Ingenua:
    nome = "ingenua"

    def __init__(self, temporadas: int = TEMPORADAS_INGENUA):
        self.temporadas = temporadas
        self.passados = None

    def ajustar(self, jogos_passados: pd.DataFrame) -> None:
        self.passados = jogos_passados

    def frequencias(self, temporada: int) -> np.ndarray:
        p = self.passados
        if p is None or len(p) == 0:
            return np.full(3, 1 / 3)
        janela = p[(p["temporada"] >= temporada - self.temporadas) & (p["temporada"] < temporada)]
        if len(janela) == 0:  # primeira temporada da base: o que houver dela
            janela = p[p["temporada"] == temporada]
        if len(janela) == 0:
            return np.full(3, 1 / 3)
        cont = janela["resultado"].value_counts()
        f = np.array([cont.get(r, 0) for r in ("M", "E", "V")], dtype=float)
        return f / f.sum()

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao:
        ts = jogos_do_bloco["temporada"].astype(int).to_numpy()
        freq = {t: self.frequencias(int(t)) for t in np.unique(ts)}
        return Previsao(np.vstack([freq[t] for t in ts]))


# ---------------------------------------------------------------------------
# Mercado
# ---------------------------------------------------------------------------
def sem_margem_proporcional(odds) -> np.ndarray:
    """odds: (3,) ou (n, 3). Cada 1/odd dividido pela soma (overround)."""
    inv = 1.0 / np.asarray(odds, dtype=float)
    return inv / inv.sum(axis=-1, keepdims=True)


def _shin_um(odds: np.ndarray) -> np.ndarray:
    pi = 1.0 / odds
    soma = pi.sum()
    if soma <= 1.0:  # sem margem (ou arbitragem): Shin não se aplica
        return pi / soma

    def probs(z):
        return (np.sqrt(z ** 2 + 4 * (1 - z) * pi ** 2 / soma) - z) / (2 * (1 - z))

    # em z = 0 a soma das probabilidades é sqrt(soma) > 1; cai com z
    z = brentq(lambda z: probs(z).sum() - 1.0, 0.0, 0.999, xtol=1e-12)
    p = probs(z)
    return p / p.sum()  # tira o resíduo numérico


def sem_margem_shin(odds) -> np.ndarray:
    """Probabilidades de Shin. odds: (3,) ou (n, 3)."""
    arr = np.asarray(odds, dtype=float)
    if arr.ndim == 1:
        return _shin_um(arr)
    return np.vstack([_shin_um(o) for o in arr])


class Mercado:
    """Régua do mercado. metodo: 'proporcional' ou 'shin'."""

    def __init__(self, metodo: str = "proporcional", nome: str | None = None):
        if metodo not in ("proporcional", "shin"):
            raise ValueError(metodo)
        self.metodo = metodo
        self.nome = nome or ("mercado" if metodo == "proporcional" else "mercado_shin")

    def ajustar(self, jogos_passados: pd.DataFrame) -> None:
        pass  # as odds de fechamento já trazem tudo o que o mercado sabia

    def prever(self, jogos_do_bloco: pd.DataFrame) -> Previsao:
        conv = sem_margem_proporcional if self.metodo == "proporcional" else sem_margem_shin
        n = len(jogos_do_bloco)
        probs = np.full((n, 3), np.nan)
        fonte = np.array(["sem_odds"] * n, dtype=object)
        pin = jogos_do_bloco[ODDS_PINNACLE].to_numpy(dtype=float)
        med = jogos_do_bloco[ODDS_MEDIA].to_numpy(dtype=float)
        tem_pin = np.isfinite(pin).all(axis=1) & (pin > 1).all(axis=1)
        tem_med = np.isfinite(med).all(axis=1) & (med > 1).all(axis=1) & ~tem_pin
        if tem_pin.any():
            probs[tem_pin] = conv(pin[tem_pin])
            fonte[tem_pin] = "pinnacle"
        if tem_med.any():
            probs[tem_med] = conv(med[tem_med])
            fonte[tem_med] = "media"
        return Previsao(probs, extras={"fonte": fonte})
