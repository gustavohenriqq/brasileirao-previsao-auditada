"""Fase 2: backtest das réguas e dos modelos base, período de validação.

Roda, bloco a bloco (temporada, rodada) e sem vazamento, a régua ingênua, o
mercado (sem margem: proporcional e Shin), o Elo e o Dixon-Coles com os
hiperparâmetros congelados em modelos/hiperparametros.py. Reporta só a
validação (2012 a 2025): RPS, log-loss, calibração e diferença pareada contra
a ingênua e contra o mercado, por temporada e no total, com IC 95% por
bootstrap de blocos (temporada, rodada), semente 2027.

Segunda métrica da validação: replay de tabela (modelos/replay.py). Em cada
temporada, a partir das rodadas 10, 15, 20 e 25, o modelo congelado no corte
simula o resto até a rodada 33 e até a 38 (10 mil temporadas) e a projeção é
comparada com a tabela real. Entram ingênua, Elo e Dixon-Coles; o mercado não
(as odds de fechamento das rodadas futuras não existiam no corte).

O teste final (2026) não é lido do banco aqui: a função `avaliar` aceita outro
período, mas exige permitir_teste=True, e só deve ser usada depois que os
fatores estiverem escolhidos.

Grava:
- analise/resultados_fase2.json, seção "validacao"
- analise/previsoes_fase2_validacao.csv (uma linha por jogo, todas as
  probabilidades; as médias de gols e o rho do Dixon-Coles permitem refazer a
  matriz de placares com modelos.dixon_coles.matriz_placares)

Uso: python analise/fase2_backtest.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ  # noqa: E402
from modelos.backtest import probs_do_modelo, rodar_backtest  # noqa: E402
from modelos.carga import carregar_jogos  # noqa: E402
from modelos.dixon_coles import DixonColes  # noqa: E402
from modelos.elo import Elo  # noqa: E402
from modelos.hiperparametros import DIXON_COLES, ELO  # noqa: E402
from modelos.metricas import (REPETICOES, SEMENTE, calibracao, codificar,  # noqa: E402
                              diferenca_pareada, log_loss, rps)
from modelos.reguas import Ingenua, Mercado  # noqa: E402
from modelos.replay import ALVOS, CORTES, SIMULACOES, replay_tabela  # noqa: E402

VALIDACAO = (2012, 2025)
PRIMEIRA_TESTE = 2026
MODELOS_REPLAY = ("ingenua", "elo", "dc")
METRICAS_REPLAY = ("erro_pontos", "erro_posicao", "acerto_g4", "acerto_g6", "acerto_z4",
                   "cobertura_90")
REGUAS = ("ingenua", "mercado")
MODELOS = ("ingenua", "mercado", "mercado_shin", "elo", "dc")
NOMES = {"ingenua": "Ingênua", "mercado": "Mercado (proporcional)",
         "mercado_shin": "Mercado (Shin)", "elo": "Elo", "dc": "Dixon-Coles"}


def montar_modelos() -> list:
    return [Ingenua(), Mercado("proporcional"), Mercado("shin"),
            Elo(**ELO), DixonColes(**DIXON_COLES)]


def resumo(perdas: dict[str, np.ndarray], mascara: np.ndarray) -> dict:
    return {nome: {"rps": float(perdas[nome]["rps"][mascara].mean()),
                   "log_loss": float(perdas[nome]["log_loss"][mascara].mean())}
            for nome in perdas}


def diferencas(perdas, prev, mascara) -> dict:
    """Cada modelo contra cada régua (RPS do modelo menos o da régua)."""
    t, r = prev["temporada"].to_numpy()[mascara], prev["rodada"].to_numpy()[mascara]
    saida = {}
    for regua in REGUAS:
        for nome in MODELOS:
            if nome in (regua, "ingenua"):
                continue
            saida[f"{nome}_menos_{regua}"] = diferenca_pareada(
                perdas[nome]["rps"][mascara], perdas[regua]["rps"][mascara], t, r)
    saida["dc_menos_elo"] = diferenca_pareada(perdas["dc"]["rps"][mascara],
                                              perdas["elo"]["rps"][mascara], t, r)
    return saida


def avaliar(inicio: int, fim: int, permitir_teste: bool = False) -> tuple[dict, pd.DataFrame]:
    if fim >= PRIMEIRA_TESTE and not permitir_teste:
        raise SystemExit("2026 é o teste final: só com permitir_teste=True, "
                         "depois de escolher os fatores.")
    jogos = carregar_jogos(ate_temporada=fim, permitir_teste=permitir_teste)
    assert jogos["temporada"].max() <= fim
    t0 = time.time()
    # O primeiro ajuste já recebe todo o histórico desde 2003 (o Elo percorre
    # tudo; o Dixon-Coles usa a janela; a ingênua, as 5 temporadas anteriores).
    prev, _ = rodar_backtest(jogos, montar_modelos(), inicio, fim)
    segundos = time.time() - t0

    y = codificar(prev["resultado"])
    perdas = {}
    for nome in MODELOS:
        probs = probs_do_modelo(prev, nome)
        if not np.isfinite(probs).all():
            raise SystemExit(f"{nome}: jogo sem probabilidade no período {inicio}-{fim}")
        perdas[nome] = {"rps": rps(probs, y), "log_loss": log_loss(probs, y)}

    tudo = np.ones(len(prev), dtype=bool)
    por_temporada = []
    for t in sorted(prev["temporada"].unique()):
        m = (prev["temporada"] == t).to_numpy()
        por_temporada.append({"temporada": int(t), "jogos": int(m.sum()),
                              "metricas": resumo(perdas, m),
                              "diferencas_rps": diferencas(perdas, prev, m)})

    fonte = prev.groupby(["temporada", "mercado_fonte"]).size().unstack(fill_value=0)
    resultado = {
        "gerado_por": "analise/fase2_backtest.py",
        "periodo": [inicio, fim],
        "semente": SEMENTE,
        "repeticoes_bootstrap": REPETICOES,
        "bootstrap": "reamostra blocos (temporada, rodada) inteiros",
        "diferenca": "RPS do modelo menos RPS da régua; negativo = modelo melhor",
        "hiperparametros": {"elo": ELO, "dixon_coles": DIXON_COLES},
        "segundos_backtest": round(segundos, 1),
        "jogos": int(len(prev)),
        "fonte_do_mercado_por_temporada": {int(t): {k: int(v) for k, v in linha.items()}
                                           for t, linha in fonte.iterrows()},
        "total": {"metricas": resumo(perdas, tudo),
                  "diferencas_rps": diferencas(perdas, prev, tudo)},
        "calibracao": {nome: calibracao(probs_do_modelo(prev, nome), y) for nome in MODELOS},
        "por_temporada": por_temporada,
    }
    return resultado, prev


def avaliar_replay(inicio: int, fim: int, permitir_teste: bool = False) -> dict:
    """Replay de tabela em cada temporada de inicio a fim, cortes x alvos."""
    if fim >= PRIMEIRA_TESTE and not permitir_teste:
        raise SystemExit("2026 é o teste final: só com permitir_teste=True.")
    jogos = carregar_jogos(ate_temporada=fim, permitir_teste=permitir_teste)
    t0 = time.time()
    modelos = {"ingenua": Ingenua(), "elo": Elo(**ELO), "dc": DixonColes(**DIXON_COLES)}
    linhas = []
    # ordem cronológica: o Elo só avança (cada treino contém o anterior)
    for t in range(inicio, fim + 1):
        for corte in CORTES:
            for nome in MODELOS_REPLAY:
                linhas += replay_tabela(jogos, modelos[nome], t, corte, ALVOS, SIMULACOES)
    tab = pd.DataFrame(linhas)
    media = (tab.groupby(["modelo", "corte", "alvo"])[list(METRICAS_REPLAY)].mean()
             .reset_index().to_dict(orient="records"))
    geral = (tab.groupby(["modelo", "alvo"])[list(METRICAS_REPLAY)].mean()
             .reset_index().to_dict(orient="records"))
    return {"periodo": [inicio, fim], "cortes": list(CORTES), "alvos": list(ALVOS), "simulacoes": SIMULACOES,
            "semente": SEMENTE, "modelos": list(MODELOS_REPLAY),
            "segundos": round(time.time() - t0, 1),
            "media_por_modelo_e_alvo": geral, "media_por_corte": media,
            "por_temporada": linhas}


def gravar_secao(secao: str, conteudo) -> Path:
    destino = RAIZ / "analise" / "resultados_fase2.json"
    dados = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    dados[secao] = conteudo
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def imprimir(res: dict) -> None:
    tot = res["total"]
    print(f"\nValidação {res['periodo'][0]}-{res['periodo'][1]}: {res['jogos']} jogos, "
          f"backtest em {res['segundos_backtest']:.0f} s")
    print(f"{'modelo':<24}{'RPS':>9}{'log-loss':>10}")
    for nome in MODELOS:
        m = tot["metricas"][nome]
        print(f"{NOMES[nome]:<24}{m['rps']:>9.5f}{m['log_loss']:>10.5f}")
    print("\nDiferença pareada de RPS (IC 95%, bootstrap por rodada):")
    for chave, d in tot["diferencas_rps"].items():
        print(f"  {chave:<28}{d['diferenca']:>+9.5f}  [{d['ic95'][0]:+.5f}, {d['ic95'][1]:+.5f}]")
    print("\nRPS por temporada:")
    print("temporada " + "".join(f"{n:>14}" for n in MODELOS))
    for linha in res["por_temporada"]:
        print(f"{linha['temporada']:<10}" + "".join(
            f"{linha['metricas'][n]['rps']:>14.5f}" for n in MODELOS))


def imprimir_replay(rep: dict) -> None:
    print(f"\nReplay de tabela (média de {rep['periodo'][0]} a {rep['periodo'][1]}, cortes {rep['cortes']}, "
          f"{rep['simulacoes']} simulações, {rep['segundos']:.0f} s):")
    print(f"{'modelo':<10}{'alvo':>5}" + "".join(f"{m:>14}" for m in METRICAS_REPLAY))
    for r in rep["media_por_modelo_e_alvo"]:
        print(f"{r['modelo']:<10}{r['alvo']:>5}" + "".join(f"{r[m]:>14.3f}" for m in METRICAS_REPLAY))


def main() -> None:
    inicio = time.time()
    res, prev = avaliar(*VALIDACAO)
    res["replay_tabela"] = avaliar_replay(*VALIDACAO)
    res["segundos_total"] = round(time.time() - inicio, 1)
    destino = gravar_secao("validacao", res)
    csv = RAIZ / "analise" / "previsoes_fase2_validacao.csv"
    saida = prev.copy()
    saida["data"] = saida["data"].dt.strftime("%Y-%m-%d")
    saida.to_csv(csv, index=False, float_format="%.6f", encoding="utf-8")
    imprimir(res)
    imprimir_replay(res["replay_tabela"])
    print(f"\nResultados em {destino.relative_to(RAIZ)}; previsões em {csv.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
