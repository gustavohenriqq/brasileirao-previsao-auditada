"""Fase 2: modelos de probabilidade (mandante, empate, visitante) e backtest.

Módulos:
- carga: lê os jogos do banco (marts.fct_jogos), em ordem de data.
- metricas: RPS, log-loss, calibração e diferença pareada com bootstrap por bloco.
- reguas: régua ingênua (frequências) e régua do mercado (odds sem margem).
- elo: Elo com placar, mando, regressão à média e logit ordenado.
- dixon_coles: Poisson bivariado com rho, decaimento, ridge e covariáveis.
- backtest: loop por bloco (temporada, rodada) sem vazamento.
- hiperparametros: valores congelados, escolhidos só com 2005 a 2011.
"""
