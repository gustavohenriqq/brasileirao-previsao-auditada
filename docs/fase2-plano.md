# Fase 2: plano (modelos, backtest, previsão de 2026)

Plano aprovado pelo Gustavo em 29/10/2026. Os resultados ficam em
`docs/fase2-modelos-backtest.md`; este arquivo diz o que fazer e por quê.

## Objetivo

1. Backtest honesto de modelos de probabilidade (mandante, empate, visitante)
   para cada jogo da Série A, treinando só com o passado.
2. Com o melhor modelo, simular as rodadas que faltam de 2026 (ensaio interno,
   sem publicar): chance de título, Libertadores, Sul-Americana e rebaixamento,
   pontos esperados.
3. Um Power BI novo, separado do painel da Fase 1, com a previsão e a nota do
   modelo.

## Divisão do tempo (contra excesso de ajuste)

| Período | Uso |
|---|---|
| 2003 a 2011 | Calibrar hiperparâmetros dos modelos base (Elo, Dixon-Coles) |
| 2012 a 2025 | Validação: decidir quais fatores entram e o peso do mercado |
| 2026 (até a última rodada jogada) | Teste final (replay de 2026), olhado uma vez, com tudo congelado |

Mudança de 29/10/2026, a pedido do Gustavo: o teste final virou o replay de
2026 (antes era 2023 a 2026), e 2023 a 2025 passaram para a validação. O modelo
continua sendo escolhido fora de 2026: com cerca de 320 jogos, escolher pelo
2026 premiaria sorte.

Um fator só entra se melhorar o RPS médio na validação com a diferença pareada
fora de zero (bootstrap por rodada, semente 2027). No teste, a nota é a que sair.

## Regra de atualização (sem vazamento)

- Bloco = (temporada, rodada). Para prever o bloco, treina com os jogos de data
  menor que a primeira data do bloco. Adiado fica de fora até ser jogado.
- Toda variável de um jogo usa só informação de antes do jogo (forma, tabela,
  técnico, estatísticas).

## Réguas

- **Ingênua:** frequências de mandante/empate/visitante das 5 temporadas
  anteriores.
- **Mercado:** Pinnacle de fechamento sem margem (proporcional; Shin como
  sensibilidade). Sem Pinnacle (44 jogos de 2025 e 2026 inteiro): média do
  mercado sem margem, marcado no resultado.

## Modelos base

- **Elo:** placar pesa (diferença de gols), mando, regressão à média entre
  temporadas, promovido entra com nota de promovido. H/D/A por logit ordenado
  sobre a diferença de Elo.
- **Dixon-Coles:** Poisson de gols com ataque/defesa por time, mando, rho
  (correção de placares baixos), decaimento no tempo, ridge, ajuste de
  promovido.

## Fatores candidatos (camadas sobre o modelo base)

Cada um testado sozinho e depois em conjunto, na validação.

1. **Mando por time:** vantagem de casa própria de cada time, encolhida para a
   média da liga.
2. **Forma:** saldo de pontos dos últimos 5 jogos contra o esperado pelo modelo.
3. **Ânimo:** sequência atual (vitórias/derrotas seguidas).
4. **Motivação de fim de campeonato:** a partir da tabela antes da rodada,
   se o time ainda briga por título, Libertadores, Sul-Americana ou contra a
   queda, ou se não tem nada a disputar (com rodadas restantes e pontos em jogo).
5. **Confronto direto:** resultado histórico do confronto contra o esperado.
6. **Estilo de jogo (quanto cada time se expõe):** perfil por posse,
   finalizações feitas e cedidas e total de chutes nos jogos do time (aberto x
   fechado), da ESPN (chutes desde 2010, posse desde 2014; validação efetiva
   2015 a 2025), sempre com jogos anteriores. Entra no
   Dixon-Coles como termo de interação: os gols esperados de A contra B
   dependem do estilo de A cruzado com o de B (ex.: time que propõe contra time
   fechado). Medido por perfil, não por confronto (amostra pequena). Também
   testar o efeito em jogos de poucos gols e empate (dois times fechados).
7. **Força por finalizações:** ataque/defesa medidos por chutes e chutes no gol,
   não só por gols.
8. **Cansaço:** dias de descanso desde o jogo anterior (só Série A; limite
   documentado: jogos de copa não estão na base).
9. **Troca de técnico:** jogos desde a troca, efeito "técnico novo".
10. **Mistura com o mercado:** média ponderada (log-odds) do modelo com o
    mercado. Captura notícias, lesões e protestos que não têm histórico
    gratuito. Peso escolhido na validação.

## Métricas

RPS (principal), log-loss, calibração por faixa. Diferença pareada contra as
duas réguas, IC 95% por bootstrap por rodada (semente 2027).

## Replay de 2026 (teste final)

Com o modelo escolhido e congelado, e com as réguas e os modelos base ao lado
para comparação:

1. **Jogo a jogo:** cada rodada de 2026 prevista só com o que havia antes dela.
   RPS por rodada e acumulado, contra o mercado e a régua ingênua.
2. **Tabela projetada:** a partir das rodadas 10, 15, 20 e 25, simular até a
   última rodada jogada e comparar com a tabela real de hoje (pontos por time,
   erro médio de posição, acerto de G4/G6 e Z4, e se a tabela real cai dentro
   da faixa de 90% da simulação).

O replay mostra quem chegaria mais perto da tabela de hoje. Ele não muda a
escolha do modelo.

O mesmo replay de tabela roda em cada temporada da validação (2012 a 2025),
a pedido do Gustavo: a partir das rodadas 10, 15, 20 e 25, projetar até a
rodada 33 (a mesma altura de 2026 hoje) e até a 38. A média dessas
temporadas é a segunda métrica da validação, ao lado do RPS. Assim a escolha
do modelo já considera quem chega mais perto da tabela, com 14 temporadas de
amostra em vez de uma.

## Simulação de 2026

- Modelo final congelado, treinado até a última rodada jogada.
- Jogos que faltam: football-data.org (`BSA-2026.json`), incluindo o adiado.
- 100 mil temporadas simuladas (placar pelo Dixon-Coles para ter saldo e gols
  pró no desempate). Critérios de desempate do regulamento 2026.
- Saída: chance por time de cada posição, título, G4/G6 (Libertadores),
  Sul-Americana, Z4; probabilidades de cada jogo restante.

## Onde fica cada coisa

- Pacote `modelos/` (carga, réguas, Elo, Dixon-Coles, fatores, métricas,
  backtest, simulação), testes em `tests/`.
- Scripts `analise/fase2_backtest.py` e `analise/fase2_simular_2026.py`;
  números em `analise/resultados_fase2.json`.
- Dados manuais (trocas de técnico) em `dados/manuais/` com a fonte de cada
  linha.
- Power BI novo em `dashboards/powerbi_previsao/`, gerado por script como o da
  Fase 1. Não mexer em `dashboards/powerbi/`.

## Ambiente

Postgres no Docker, porta 5434 (`POSTGRES_PORT=5434`; o `.env` diz 5433).
Rodar Python pelo `.venv`.
