"""Fase 2: teste final em 2026, com o modelo escolhido congelado.

Roda uma vez. O modelo e todos os hiperparâmetros foram escolhidos em 2005 a
2025 (analise/fase2_backtest.py, analise/fase2_fatores.py); nada aqui muda a
escolha. Se a seção "teste_2026" já existir em analise/resultados_fase2.json,
o script para (a nota do teste é a primeira que sair).

1. Jogo a jogo: cada rodada de 2026 prevista só com o que havia antes dela
   (mesmo backtest). Modelo escolhido (Dixon-Coles + mando por time +
   finalizações) contra o Dixon-Coles, o Elo, a régua ingênua e o mercado.
   Em 2026 não há Pinnacle: o mercado é a média das casas sem margem.
2. Tabela projetada: replay de 2026 a partir das rodadas 10, 15, 20 e 25 até
   a rodada 32 (a última completa na base), com a incerteza de parâmetro
   escolhida em 2005 a 2011. O adiado da rodada 21 fica fora dos dois lados
   (real e simulado).

Rodar com
    .venv\\Scripts\\python -u analise/fase2_teste_2026.py > analise/fase2_teste_2026.log 2>&1
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ  # noqa: E402
from modelos.backtest import probs_do_modelo, rodar_backtest  # noqa: E402
from modelos.carga import carregar_jogos  # noqa: E402
from modelos.dixon_coles import DixonColes  # noqa: E402
from modelos.elo import Elo  # noqa: E402
from modelos.fatores import ComFatores, Finalizacoes, MandoTime, carregar_estatisticas  # noqa: E402
from modelos.hiperparametros import DIXON_COLES, ELO  # noqa: E402
from modelos.metricas import codificar, diferenca_pareada, log_loss, rps  # noqa: E402
from modelos.reguas import Ingenua, Mercado  # noqa: E402
from modelos.replay import CORTES, replay_tabela  # noqa: E402

TEMPORADA = 2026
ALVO = 32
SIMULACOES = 10_000
ESCOLHIDO = "conjunto_dc"
# escolhidos na validação (resultados_fase2.json, seção "fatores")
RIDGE_MANDO_TIME = 100
JANELA_FINALIZACOES = 38
INCERTEZA = {"ingenua": 0.0, "elo": 0.3, "dc": 0.1, ESCOLHIDO: 0.1}
DESTINO = RAIZ / "analise" / "resultados_fase2.json"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def modelo_escolhido(times: list, estat: pd.DataFrame) -> ComFatores:
    camadas = [MandoTime(times, RIDGE_MANDO_TIME), Finalizacoes(JANELA_FINALIZACOES)]
    return ComFatores("dc", camadas, ESCOLHIDO, estat=estat)


def montar(times, estat) -> dict:
    return {"ingenua": Ingenua(), "mercado": Mercado("proporcional"),
            "elo": Elo(**ELO), "dc": DixonColes(**DIXON_COLES),
            ESCOLHIDO: modelo_escolhido(times, estat)}


def main() -> None:
    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    if "teste_2026" in dados:
        raise SystemExit("teste_2026 já existe em resultados_fase2.json: o teste final roda uma vez")
    t0 = time.time()

    jogos = carregar_jogos(permitir_teste=True)
    estat = carregar_estatisticas(TEMPORADA, permitir_teste=True)
    estat = estat[estat["jogo_id"].isin(set(jogos["jogo_id"]))]
    times = sorted(set(jogos["mandante_id"]) | set(jogos["visitante_id"]))
    t26 = jogos[jogos["temporada"] == TEMPORADA]
    log(f"base: {len(jogos)} jogos; 2026: {len(t26)} jogos, rodadas {t26['rodada'].min()} a "
        f"{t26['rodada'].max()}, última data {t26['data'].max():%d/%m/%Y}")

    # --- 1. jogo a jogo ---
    modelos = montar(times, estat)
    prev, _ = rodar_backtest(jogos, list(modelos.values()), TEMPORADA, TEMPORADA)
    y = codificar(prev["resultado"])
    perdas = {}
    for nome in modelos:
        p = probs_do_modelo(prev, nome)
        perdas[nome] = (rps(p, y), log_loss(p, y), np.isfinite(p).all(axis=1))
    ok = np.logical_and.reduce([v[2] for v in perdas.values()])
    log(f"previstos {len(prev)} jogos; com todos os modelos (mercado inclusive): {int(ok.sum())}")
    fonte = prev.loc[ok, "mercado_fonte"].value_counts().to_dict() if "mercado_fonte" in prev else {}
    t, r = prev["temporada"].to_numpy()[ok], prev["rodada"].to_numpy()[ok]
    resumo = {n: {"rps": float(v[0][ok].mean()), "log_loss": float(v[1][ok].mean())}
              for n, v in perdas.items()}
    for n, v in resumo.items():
        log(f"  {n:12s} RPS {v['rps']:.5f}  log-loss {v['log_loss']:.5f}")
    pares = {}
    for outro in modelos:
        if outro == ESCOLHIDO:
            continue
        d = diferenca_pareada(perdas[ESCOLHIDO][0][ok], perdas[outro][0][ok], t, r)
        pares[f"{ESCOLHIDO}_menos_{outro}"] = d
        log(f"  {ESCOLHIDO} - {outro}: {d['diferenca']:+.5f} [{d['ic95'][0]:+.5f}; {d['ic95'][1]:+.5f}]")
    por_rodada = (pd.DataFrame({n: v[0] for n, v in perdas.items()})
                  .assign(rodada=prev["rodada"].to_numpy())[ok]
                  .groupby("rodada").mean())
    prev.to_csv(RAIZ / "analise" / "previsoes_fase2_teste_2026.csv", index=False)
    log(f"jogo a jogo pronto ({time.time() - t0:.0f} s)")

    # --- 2. tabela projetada ---
    replay = {}
    for nome in ("ingenua", "elo", "dc", ESCOLHIDO):
        linhas = []
        for corte in CORTES:
            m = montar(times, estat)[nome]
            linhas += replay_tabela(jogos, m, TEMPORADA, corte, (ALVO,), SIMULACOES,
                                    detalhar=True, incerteza=INCERTEZA[nome])
        replay[nome] = linhas
        media = pd.DataFrame(linhas)[["erro_pontos", "erro_posicao", "acerto_g4", "acerto_g6",
                                      "acerto_z4", "cobertura_90"]].mean()
        log(f"  replay {nome:12s} " + ", ".join(f"{k} {v:.3f}" for k, v in media.items()))
    log(f"replay pronto ({time.time() - t0:.0f} s)")

    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    dados["teste_2026"] = {
        "gerado_por": "analise/fase2_teste_2026.py",
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo_escolhido": {"nome": ESCOLHIDO, "base": "dc",
                             "fatores": [["mando_time", RIDGE_MANDO_TIME],
                                         ["finalizacoes", JANELA_FINALIZACOES]],
                             "incerteza_replay": INCERTEZA[ESCOLHIDO]},
        "jogos": int(ok.sum()), "jogos_previstos": int(len(prev)), "fonte_mercado": fonte,
        "resumo": resumo, "diferencas": pares,
        "rps_por_rodada": {int(k): {n: float(v) for n, v in row.items()}
                           for k, row in por_rodada.iterrows()},
        "replay": {"alvo": ALVO, "cortes": list(CORTES), "simulacoes": SIMULACOES,
                   "incerteza": INCERTEZA, "linhas": replay},
        "segundos": time.time() - t0,
    }
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=lambda o: o.item()),
                       encoding="utf-8")
    log(f"gravado em {DESTINO}")


if __name__ == "__main__":
    main()
