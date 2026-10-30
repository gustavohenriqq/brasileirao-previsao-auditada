"""Métricas de previsão para três resultados ordenados (mandante, empate, visitante).

- RPS (ranked probability score): erro quadrático das probabilidades
  acumuladas. Com três resultados ordenados M < E < V:
      RPS = ((pM - oM)^2 + (pM + pE - oM - oE)^2) / 2
  Vai de 0 (acerto certeiro) a 1. Menor é melhor. Diferente do log-loss, um
  empate previsto como provável é "meio caminho" entre vitória e derrota.
- Log-loss: menos o log natural da probabilidade dada ao que aconteceu.
- Calibração por faixa: para cada resultado, agrupa as previsões em faixas de
  probabilidade e compara a média prevista com a frequência observada.
- Diferença pareada: média da perda do modelo A menos a do modelo B nos mesmos
  jogos, com IC 95% por bootstrap que reamostra blocos (temporada, rodada)
  inteiros, porque jogos da mesma rodada não são independentes.

Uso:
    from modelos.metricas import rps, log_loss, calibracao, diferenca_pareada
"""
from __future__ import annotations

import numpy as np

SEMENTE = 2027
REPETICOES = 10_000
RESULTADOS = ("M", "E", "V")
FAIXAS_CALIBRACAO = np.linspace(0.0, 1.0, 11)  # faixas de 10 pontos percentuais


def codificar(resultado) -> np.ndarray:
    """'M'/'E'/'V' para 0/1/2."""
    mapa = {r: i for i, r in enumerate(RESULTADOS)}
    return np.array([mapa[r] for r in resultado], dtype=int)


def _observado(y: np.ndarray) -> np.ndarray:
    obs = np.zeros((len(y), 3))
    obs[np.arange(len(y)), y] = 1.0
    return obs


def rps(probs: np.ndarray, y: np.ndarray) -> np.ndarray:
    """RPS por jogo. probs: (n, 3) na ordem M, E, V. y: códigos 0/1/2."""
    probs = np.asarray(probs, dtype=float)
    cum_p = np.cumsum(probs, axis=1)[:, :2]
    cum_o = np.cumsum(_observado(np.asarray(y)), axis=1)[:, :2]
    return ((cum_p - cum_o) ** 2).sum(axis=1) / 2.0


def log_loss(probs: np.ndarray, y: np.ndarray, piso: float = 1e-15) -> np.ndarray:
    """Log-loss por jogo (log natural)."""
    probs = np.asarray(probs, dtype=float)
    p = probs[np.arange(len(y)), np.asarray(y)]
    return -np.log(np.clip(p, piso, 1.0))


def calibracao(probs: np.ndarray, y: np.ndarray,
               faixas: np.ndarray = FAIXAS_CALIBRACAO) -> list[dict]:
    """Uma linha por (resultado, faixa) com jogos, média prevista e frequência."""
    probs = np.asarray(probs, dtype=float)
    obs = _observado(np.asarray(y))
    saida = []
    for k, nome in enumerate(RESULTADOS):
        # a última faixa fecha à direita para incluir probabilidade 1
        idx = np.clip(np.digitize(probs[:, k], faixas[1:-1], right=False), 0, len(faixas) - 2)
        for f in range(len(faixas) - 1):
            m = idx == f
            if not m.any():
                continue
            saida.append({
                "resultado": nome,
                "faixa": [float(faixas[f]), float(faixas[f + 1])],
                "jogos": int(m.sum()),
                "prevista_media": float(probs[m, k].mean()),
                "frequencia_observada": float(obs[m, k].mean()),
            })
    return saida


def ic(amostras: np.ndarray) -> list[float]:
    lo, hi = np.percentile(amostras, [2.5, 97.5])
    return [float(lo), float(hi)]


def diferenca_pareada(perda_a: np.ndarray, perda_b: np.ndarray, temporada, rodada,
                      repeticoes: int = REPETICOES, semente: int = SEMENTE) -> dict:
    """Média de A menos média de B (negativo: A erra menos), com IC 95% por
    bootstrap de blocos (temporada, rodada). Reamostra blocos inteiros com
    reposição e recalcula a média ponderada pelo número de jogos."""
    perda_a = np.asarray(perda_a, dtype=float)
    perda_b = np.asarray(perda_b, dtype=float)
    d = perda_a - perda_b
    chaves = np.asarray(temporada, dtype=np.int64) * 1000 + np.asarray(rodada, dtype=np.int64)
    _, grupo = np.unique(chaves, return_inverse=True)
    somas = np.bincount(grupo, weights=d)
    ns = np.bincount(grupo).astype(float)
    rng = np.random.default_rng(semente)
    idx = rng.integers(0, len(somas), size=(repeticoes, len(somas)))
    medias = somas[idx].sum(axis=1) / ns[idx].sum(axis=1)
    return {
        "jogos": int(len(d)),
        "blocos": int(len(somas)),
        "media_a": float(perda_a.mean()),
        "media_b": float(perda_b.mean()),
        "diferenca": float(d.mean()),
        "ic95": ic(medias),
    }
