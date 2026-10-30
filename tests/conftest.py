"""Fábrica de jogos sintéticos para os testes da Fase 2 (sem banco)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelos.dixon_coles import simular_placares


def tabela_turno_returno(times: list[str]) -> list[list[tuple[str, str]]]:
    """Rodadas de turno e returno pelo método do círculo."""
    n = len(times)
    lista = list(times)
    turno = []
    for r in range(n - 1):
        pares = []
        for i in range(n // 2):
            a, b = lista[i], lista[n - 1 - i]
            pares.append((a, b) if r % 2 == 0 else (b, a))
        turno.append(pares)
        lista = [lista[0]] + [lista[-1]] + lista[1:-1]
    returno = [[(b, a) for a, b in rodada] for rodada in turno]
    return turno + returno


def gerar_jogos(n_times: int = 10, temporadas: int = 3, semente: int = 2027,
                mu: float = 0.1, mando: float = 0.3, rho: float = -0.1,
                ataque=None, defesa=None, inicio: str = "2010-05-01",
                trocar_times: bool = False) -> pd.DataFrame:
    """Jogos simulados de Dixon-Coles, em ordem de data. Cada rodada tem os
    jogos em dois dias seguidos e as rodadas são semanais. Com trocar_times,
    o último time de cada temporada é trocado por um novo (promovido)."""
    rng = np.random.default_rng(semente)
    times = [f"T{i:02d}" for i in range(n_times)]
    if ataque is None:
        ataque = rng.normal(0, 0.25, n_times)
    if defesa is None:
        defesa = rng.normal(0, 0.25, n_times)
    forca = {t: (ataque[i], defesa[i]) for i, t in enumerate(times)}
    linhas, data0, novo = [], pd.Timestamp(inicio), n_times
    for s in range(temporadas):
        temporada = 2010 + s
        if trocar_times and s > 0:
            saiu = times[-1]
            times = times[:-1] + [f"T{novo:02d}"]
            forca[times[-1]] = (-0.2, -0.2)
            novo += 1
            del forca[saiu]
        base = data0 + pd.Timedelta(days=365 * s)
        for r, rodada in enumerate(tabela_turno_returno(times), start=1):
            for k, (m, v) in enumerate(rodada):
                am, dm = forca[m]
                av, dv = forca[v]
                lm = np.exp(mu + mando + am - dv)
                lv = np.exp(mu + av - dm)
                gm, gv = simular_placares([lm], [lv], rho, rng)[0]
                linhas.append({
                    "jogo_id": f"{temporada}-{r:02d}-{k}", "temporada": temporada, "rodada": r,
                    "data": base + pd.Timedelta(days=7 * (r - 1) + (k % 2)),
                    "mandante_id": m, "visitante_id": v,
                    "gols_mandante": int(gm), "gols_visitante": int(gv),
                    "resultado": "M" if gm > gv else ("E" if gm == gv else "V"),
                })
    jogos = pd.DataFrame(linhas).sort_values(["data", "jogo_id"]).reset_index(drop=True)
    return jogos


@pytest.fixture
def fabrica():
    return gerar_jogos
