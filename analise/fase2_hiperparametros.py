"""Fase 2: escolha dos hiperparâmetros do Elo e do Dixon-Coles (só 2003 a 2011).

Lê do banco só as temporadas até 2011 (o resto nem é carregado), roda o
backtest por bloco com 2003 e 2004 de aquecimento e mede o RPS médio das
previsões de 2005 a 2011 para cada combinação da grade. O vencedor é o de
menor RPS. Grava a grade inteira e o vencedor em
analise/resultados_fase2.json, seção "calibracao_hiperparametros".

Os valores escolhidos são copiados à mão para modelos/hiperparametros.py,
onde ficam congelados para a validação e o teste.

Uso: python analise/fase2_hiperparametros.py
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestao.comum import RAIZ  # noqa: E402
from modelos.backtest import probs_do_modelo, rodar_backtest  # noqa: E402
from modelos.carga import carregar_jogos  # noqa: E402
from modelos.dixon_coles import DixonColes  # noqa: E402
from modelos.elo import Elo  # noqa: E402
from modelos.metricas import codificar, log_loss, rps  # noqa: E402

SEMENTE = 2027  # nada aleatório aqui; fica para manter o padrão do projeto
ULTIMA_TEMPORADA_CALIBRACAO = 2011
PREVER_DE, PREVER_ATE = 2005, 2011   # 2003 e 2004 são aquecimento

# A primeira grade do Elo (k 10 a 40, mando 30 a 90) deu vencedor na borda
# (k = 10, mando = 90): a grade foi ampliada para os dois lados que faltavam.
GRADE_ELO = {
    "k": [5, 7.5, 10, 15, 20, 30, 40],
    "mando": [30, 60, 90, 120, 150],
    "regressao": [0.1, 0.25, 0.4, 0.6],
    "nota_promovido": [0, -50, -100, -150],
}
GRADE_DC = {
    "meia_vida": [90, 180, 365, 730],
    "ridge": [0.3, 1, 3, 10, 30],
    "forca_promovido": [0.0, 0.15, 0.3],
}
JANELA_DC = 3

_JOGOS = None


def _iniciar(jogos) -> None:
    global _JOGOS
    _JOGOS = jogos


def _avaliar(args) -> dict:
    tipo, params = args
    modelo = Elo(**params) if tipo == "elo" else DixonColes(janela_temporadas=JANELA_DC, **params)
    prev, _ = rodar_backtest(_JOGOS, [modelo], PREVER_DE, PREVER_ATE)
    y = codificar(prev["resultado"])
    probs = probs_do_modelo(prev, modelo.nome)
    return {**params, "jogos": int(len(y)), "rps": float(rps(probs, y).mean()),
            "log_loss": float(log_loss(probs, y).mean())}


def combinacoes(grade: dict) -> list[dict]:
    chaves = list(grade)
    return [dict(zip(chaves, v)) for v in itertools.product(*(grade[c] for c in chaves))]


def gravar_secao(secao: str, conteudo) -> Path:
    destino = RAIZ / "analise" / "resultados_fase2.json"
    dados = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    dados[secao] = conteudo
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def main() -> None:
    jogos = carregar_jogos(ate_temporada=ULTIMA_TEMPORADA_CALIBRACAO)
    assert jogos["temporada"].max() <= ULTIMA_TEMPORADA_CALIBRACAO
    tarefas = [("elo", p) for p in combinacoes(GRADE_ELO)] + \
              [("dc", p) for p in combinacoes(GRADE_DC)]
    inicio = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count(), initializer=_iniciar,
                             initargs=(jogos,)) as ex:
        # progresso por combinação (para acompanhar pelo log)
        futuros = {ex.submit(_avaliar, tarefa): i for i, tarefa in enumerate(tarefas)}
        resultados = [None] * len(tarefas)
        for feitos, fut in enumerate(as_completed(futuros), start=1):
            i = futuros[fut]
            resultados[i] = fut.result()
            print(f"[{feitos}/{len(tarefas)}] {tarefas[i][0]} {tarefas[i][1]} "
                  f"rps={resultados[i]['rps']:.5f} ({time.time() - inicio:.0f} s)", flush=True)
    segundos = time.time() - inicio

    saida = {"gerado_por": "analise/fase2_hiperparametros.py",
             "temporadas_lidas": [int(jogos["temporada"].min()), ULTIMA_TEMPORADA_CALIBRACAO],
             "aquecimento": [2003, 2004], "previsoes_avaliadas": [PREVER_DE, PREVER_ATE],
             "criterio": "menor RPS médio por jogo", "segundos": round(segundos, 1),
             "historico": "1a rodada da grade do Elo (k 10-40, mando 30-90) deu vencedor na "
                          "borda (k=10, mando=90, RPS 0,21062); grade ampliada e rodada de novo."}
    for tipo, grade in (("elo", GRADE_ELO), ("dixon_coles", GRADE_DC)):
        chave = "elo" if tipo == "elo" else "dc"
        linhas = [r for (t, _), r in zip(tarefas, resultados) if t == chave]
        linhas.sort(key=lambda r: r["rps"])
        vencedor = linhas[0]
        # aviso se o vencedor ficou na borda da grade (a grade deveria ser ampliada)
        borda = [c for c in grade if len(grade[c]) > 1 and vencedor[c] in (grade[c][0], grade[c][-1])]
        saida[tipo] = {"grade": grade, "vencedor": vencedor, "na_borda_da_grade": borda,
                       "resultados": linhas}
        if tipo == "dixon_coles":
            saida[tipo]["janela_temporadas"] = JANELA_DC
        print(f"{tipo}: vencedor {vencedor} (borda: {borda or 'nenhuma'})")
        print("  5 melhores RPS:", [round(r["rps"], 5) for r in linhas[:5]],
              " pior:", round(linhas[-1]["rps"], 5))
    destino = gravar_secao("calibracao_hiperparametros", saida)
    print(f"{len(tarefas)} combinações em {segundos:.0f} s. Resultados em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
