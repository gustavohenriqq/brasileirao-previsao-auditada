# Fase 2: modelos, backtest e previsão de 2026

**O modelo erra mais que o mercado, mas bate a régua ingênua com folga.** Em
2026 (teste final, 319 jogos), o modelo escolhido teve RPS 0,2023; o mercado,
0,1960; a régua ingênua, 0,2172. Na validação (2012 a 2025, 5.319 jogos), o
mercado venceu os modelos nas 14 temporadas. Nenhum fator testado fechou essa
distância.

RPS (ranked probability score): erro das probabilidades de mandante, empate e
visitante, na ordem. Menor é melhor; 0 é acertar com 100% de certeza.

O plano e as regras estão em [fase2-plano.md](fase2-plano.md). Este arquivo
traz os resultados. Todos os números saem de `analise/resultados_fase2.json`,
gravado pelos scripts citados em cada seção.

## Como o tempo foi dividido

| Período | Uso | Script |
|---|---|---|
| 2003 a 2011 | Hiperparâmetros do Elo e do Dixon-Coles; escala da incerteza | `analise/fase2_hiperparametros.py` |
| 2012 a 2025 | Validação: compara modelos e decide fatores | `analise/fase2_backtest.py`, `analise/fase2_fatores.py`, `analise/fase2_copas.py` |
| 2026 | Teste final, rodado uma vez com tudo congelado | `analise/fase2_teste_2026.py` |

O código só lê 2026 com `permitir_teste=True`. O script do teste recusa rodar
de novo se a seção `teste_2026` já existir no JSON.

Atualização sem vazamento: cada rodada é prevista só com jogos de data anterior
ao primeiro jogo dela.

## Modelos base

Hiperparâmetros escolhidos pelo menor RPS em 2005 a 2011 (2.742 jogos; 2003 e
2004 são aquecimento).

- **Elo:** k 10, mando 150, regressão de 40% à média entre temporadas,
  promovido entra com -50. O mando ficou na borda da grade, mas a curva é
  plana (os 5 melhores RPS vão de 0,21059 a 0,21063).
- **Dixon-Coles:** gols por Poisson com ataque e defesa por time e correção
  de placares baixos. Meia-vida de 180 dias, ridge 10, promovido 0,15, janela
  de 3 temporadas.

## Validação, 2012 a 2025

| Modelo | RPS | Log-loss |
|---|---|---|
| Mercado (Pinnacle sem margem, proporcional) | 0,2010 | 0,998 |
| Mercado (Shin) | 0,2010 | 0,998 |
| Elo | 0,2078 | 1,020 |
| Dixon-Coles | 0,2082 | 1,021 |
| Ingênua (frequências das 5 temporadas anteriores) | 0,2179 | 1,050 |

Diferença pareada de RPS, IC 95% por bootstrap de rodadas (semente 2027):

- Elo contra ingênua: -0,0101 (-0,0121 a -0,0082). O modelo ganha.
- Elo contra mercado: +0,0067 (+0,0051 a +0,0084). O mercado ganha.
- Dixon-Coles contra Elo: +0,0005 (-0,0004 a +0,0013). Empate.

Sem Pinnacle (44 jogos de 2025), o mercado é a média das casas sem margem.

**Replay de tabela.** A partir das rodadas 10, 15, 20 e 25, cada modelo
simulou o resto da temporada (10 mil vezes) e foi comparado com a tabela real
da rodada 33. Média de 2012 a 2025:

| Modelo | Erro de pontos | Erro de posição | Acerto G4 | Acerto Z4 | Cobertura da faixa de 90% |
|---|---|---|---|---|---|
| Elo | 4,58 | 2,37 | 73% | 65% | 86% |
| Dixon-Coles | 4,61 | 2,38 | 73% | 61% | 86% |
| Ingênua | 5,26 | 2,58 | 73% | 64% | 81% |

A faixa de 90% acertava só 86% das vezes: as forças dos times ficavam
congeladas na simulação, sem incerteza. Correção mais abaixo.

## Fatores

Cada fator foi testado sozinho contra o seu modelo base. Entra se o IC 95% da
diferença de RPS fica todo abaixo de zero. O hiperparâmetro de cada fator foi
escolhido antes, em 2005 a 2011 (ou 2012 a 2014 para os que dependem de
estatísticas da ESPN).

| # | Fator | Base | Período | Diferença de RPS (IC 95%) | Entra |
|---|---|---|---|---|---|
| 1 | Mando por time | DC | 2012-2025 | -0,00014 (-0,00027 a -0,00001) | sim, no limite |
| 2 | Forma (últimos 5 jogos) | Elo | 2012-2025 | +0,00007 (-0,00014 a +0,00029) | não |
| 3 | Ânimo (sequência) | Elo | 2012-2025 | -0,00009 (-0,00042 a +0,00025) | não |
| 4 | Motivação de fim de campeonato | Elo | 2012-2025 | -0,00028 (-0,00081 a +0,00027) | não |
| 5 | Confronto direto | Elo | 2012-2025 | +0,00013 (-0,00005 a +0,00032) | não |
| 6 | Estilo de jogo | DC | 2015-2025 | +0,00021 (-0,00001 a +0,00044) | não |
| 7 | Força por finalizações | DC | 2015-2025 | -0,00083 (-0,00153 a -0,00009) | sim |
| 8 | Cansaço (só Série A) | Elo | 2012-2025 | -0,00008 (-0,00020 a +0,00001) | não |
| 9 | Troca de técnico | Elo | 2015-2025 | +0,00009 (-0,00013 a +0,00030) | não |
| 11 | Cansaço com jogos de copa | DC + 1 e 7 | 2015-2025 | +0,00000 (-0,00001 a +0,00002) | não |
| 12 | Copa logo depois | DC + 1 e 7 | 2015-2025 | +0,00020 (-0,00015 a +0,00057) | não |

Os fatores 11 e 12 usam Libertadores, Sul-Americana e Copa do Brasil da ESPN
(`modelos/copas.py`, 2011 a 2026). Foram pedidos depois e testados contra o
conjunto já montado. No 11, o teto escolhido (3 dias) quase nunca é atingido
em 2015-2025, então o teste ficou quase vazio. O 12 tem o sinal esperado
(menos gols antes de jogo de copa), mas piora o RPS.

**Conjunto escolhido (`conjunto_dc`):** Dixon-Coles + mando por time +
finalizações. Validação 2015-2025 (4.179 jogos):

- RPS 0,2070, contra 0,2079 do Dixon-Coles puro: -0,0009 (-0,0016 a -0,0002).
- Contra o Elo: -0,0007 (-0,0018 a +0,0005). Empate.
- Contra o mercado: +0,0066 (+0,0049 a +0,0083). O mercado ganha.
- Replay alvo 33: erro de 4,59 pontos e 2,32 posições.

**Fator 10, mistura com o mercado.** A curva de peso caiu até 1,0: a melhor
mistura é o mercado puro. O modelo não acrescenta nada às odds. Como odds só
existem jogo a jogo, perto da rodada, a mistura não serve para simular
rodadas futuras e ficou de fora.

## Incerteza na simulação

Para a faixa de 90% acertar 90% das vezes, cada simulação sorteia a força dos
times em torno da estimada. A escala foi escolhida em 2005 a 2011: 0,3 no Elo,
0,1 no Dixon-Coles.

| Modelo | Cobertura alvo 33, antes | Depois | Alvo 38, antes | Depois |
|---|---|---|---|---|
| Elo | 0,860 | 0,906 | 0,827 | 0,888 |
| Dixon-Coles | 0,855 | 0,902 | 0,830 | 0,884 |
| Conjunto | 0,858 | 0,907 | 0,824 | 0,880 |

A escala é única para todos os cortes. Projetando da rodada 10, a cobertura
ainda fica abaixo de 90%; da rodada 25, fica acima.

## Teste final: replay de 2026

Rodado uma vez, em 30/10/2026, com os dados até 28/10 (324 jogos previstos;
319 com odds, que são a base da comparação). Sem Pinnacle em
2026, o mercado é a média das casas sem margem.

| Modelo | RPS | Log-loss |
|---|---|---|
| Mercado | 0,1960 | 0,991 |
| **Conjunto (escolhido)** | **0,2023** | **1,014** |
| Elo | 0,2032 | 1,012 |
| Dixon-Coles | 0,2043 | 1,019 |
| Ingênua | 0,2172 | 1,054 |

- Conjunto contra ingênua: -0,0149 (-0,0251 a -0,0043). O modelo ganha.
- Contra o mercado: +0,0064 (+0,0022 a +0,0109). O mercado ganha.
- Contra o Elo: -0,0009 (-0,0045 a +0,0032). Empate.
- Contra o Dixon-Coles: -0,0020 (-0,0045 a +0,0008). Empate.

Replay da tabela até a rodada 32 (última completa), média dos cortes 10, 15,
20 e 25:

| Modelo | Erro de pontos | Erro de posição | Acerto G4 | Acerto Z4 | Cobertura 90% |
|---|---|---|---|---|---|
| **Conjunto** | **4,52** | **2,37** | 63% | 56% | 0,925 |
| Elo | 4,74 | 2,49 | 63% | 50% | 0,863 |
| Dixon-Coles | 4,75 | 2,43 | 63% | 50% | 0,875 |
| Ingênua | 5,93 | 2,64 | 63% | 56% | 0,725 |

O conjunto foi o melhor dos quatro no replay de 2026. Com uma temporada só,
isso não prova que ele é melhor que o Elo; a validação já dizia empate.

## Simulação do fim de 2026

`analise/fase2_simular_2026.py`: modelo escolhido treinado com os 327 jogos
disputados até 29/10, 100 mil temporadas dos 53 jogos que faltam (inclui
Chapecoense x Vasco, adiado da 21ª rodada, sem data: entra na data do último
jogo pendente). Desempate: pontos, vitórias, saldo, gols pró, sorteio. Saídas
em `analise/simulacao_2026_{times,posicoes,jogos}.csv`.

| Time | Pontos hoje | Pontos no fim (faixa 90%) | Título | Z4 |
|---|---|---|---|---|
| Flamengo | 73 | 83,8 (80 a 88) | 86,9% | 0% |
| Palmeiras | 70 | 79,7 (75 a 85) | 13,1% | 0% |
| Corinthians | 33 | 41,2 (36 a 46) | 0% | 53,7% |
| Internacional | 35 | 42,3 (38 a 47) | 0% | 41,6% |
| Grêmio | 37 | 42,5 (38 a 47) | 0% | 40,2% |
| Coritiba | 39 | 43,8 (40 a 49) | 0% | 24,4% |
| Remo | 29 | 34,5 (30 a 39) | 0% | 99,4% |
| Chapecoense | 21 | 25,5 (21 a 31) | 0% | 100% |

Tabela completa no log `analise/fase2_simular_2026.log` e no painel.

Painel Power BI com a simulação e o teste:
[dashboards/powerbi_previsao/README.md](../dashboards/powerbi_previsao/README.md).
Ensaio interno: não foi publicado.

## Ressalvas

Do revisor independente (30/10/2026), mais as nossas:

1. **Mando por time é frágil.** Passou no limite. Com correção para muitos
   testes (Holm ou Bonferroni), não passaria. No conjunto, acrescenta só
   0,00008 de RPS.
2. **O ganho do conjunto sobre o Dixon-Coles foi medido nos mesmos jogos que
   escolheram os fatores.** É otimista. Quem mede de verdade é 2026, e lá a
   diferença ficou dentro do empate (IC cruza zero).
3. **Grades ampliadas.** Algumas grades de hiperparâmetro foram ampliadas
   depois da primeira rodada (só no período de escolha; histórico no JSON,
   em `fatores.historico_grades`). A do cansaço foi ampliada depois de ver a
   validação; o fator não entrou.
4. **Cansaço e técnico em jogos adiados.** O calendário usado no treino e na
   previsão difere para adiados. O coeficiente do cansaço no Elo (1,56 por
   dia) não faz sentido; o fator não entrou.
5. **Mistura com o mercado deixando uma temporada de fora** usa temporadas
   futuras no treino. Todas deram peso 1,0, então a conclusão não muda.
6. **Escala única de incerteza:** cobertura baixa projetando de longe (rodada
   10), alta projetando de perto (rodada 25).
7. **Cansaço com copas:** o teto de 3 dias veio da regra (menor RPS, na borda
   da grade). A sensibilidade com teto 7 não foi rodada.
8. **Rodada que se estende.** O bloco começa no jogo mais cedo da rodada; 132
   jogos foram disputados 14 dias ou mais depois desse início e são previstos
   sem os jogos do intervalo.
9. **Grêmio Barueri / Grêmio Prudente** viram promovido em 2010 (troca de
   nome tratada como time novo). Afeta só a calibração.

## Onde conferir

| Número | Onde |
|---|---|
| Hiperparâmetros | `analise/fase2_hiperparametros.log`; JSON `calibracao_hiperparametros` |
| Validação e replay de tabela | `analise/fase2_backtest.log`; JSON `validacao`; previsões em `analise/previsoes_fase2_validacao.csv` |
| Fatores 1 a 10, conjunto, incerteza | `analise/fase2_fatores.log`; JSON `fatores` |
| Fatores 11 e 12 (copas) | `analise/fase2_copas.log`; JSON `copas` |
| Teste de 2026 | `analise/fase2_teste_2026.log`; JSON `teste_2026`; previsões em `analise/previsoes_fase2_teste_2026.csv` |
| Simulação | `analise/fase2_simular_2026.log`; JSON `simulacao_2026`; `analise/simulacao_2026_*.csv` |

Código em `modelos/` (carga, réguas, Elo, Dixon-Coles, fatores, copas,
métricas, backtest, replay), testes em `tests/test_fase2_*.py`.
