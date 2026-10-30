"""Hiperparâmetros congelados dos modelos base.

Escolhidos por analise/fase2_hiperparametros.py: menor RPS médio nas
previsões de 2005 a 2011 (2003 e 2004 de aquecimento), sem ler nenhuma
temporada depois de 2011. A grade inteira e o RPS de cada combinação estão em
analise/resultados_fase2.json, seção "calibracao_hiperparametros".
Não mudar depois de olhar a validação.
"""

ELO = {
    "k": 10,                 # pontos por jogo (antes do multiplicador de saldo)
    "mando": 150,            # vantagem do mandante em pontos de Elo (borda da grade; curva plana)
    "regressao": 0.4,        # fração regredida à média entre temporadas
    "nota_promovido": -50,   # promovido entra com a média menos isto
}

DIXON_COLES = {
    "meia_vida": 180,        # dias: peso 0,5 para um jogo de 180 dias atrás
    "ridge": 10,             # penalização de ataque e defesa em direção ao prior
    "forca_promovido": 0.15, # prior de ataque e defesa do promovido (log de gols)
    "janela_temporadas": 3,  # treino: temporada do bloco e as 3 anteriores
}
