# Brasileirão: previsão auditada

**Sem torcida, a vantagem do mandante na Série A caiu quase pela metade, mas
não sumiu: de 0,80 ponto por jogo a mais que o visitante (2015 a 2019) para
0,44 nos 594 jogos sem público (ago/2020 a set/2021), queda de 45%.** A
vitória do mandante foi de 50,3% para 42,4%, e a tendência histórica previa
0,76, não 0,44. Com a torcida de volta (2022 a 2026), a vantagem ficou em 0,64.

![Painel](docs/img/painel_mando_de_campo.png)

No painel, a tabela por time diz "20 de 25" porque soma aos 21 clubes da
Série A 4 tradicionais que jogaram sem torcida na Série B; a análise principal
usa só a Série A, onde 17 de 21 times perderam força em casa.

A queda passa em três checagens: contra a tendência histórica, dentro do mesmo
time e reamostrando rodadas inteiras. Detalhes em
[docs/fase1-mando-de-campo.md](docs/fase1-mando-de-campo.md).

A base por trás: 9.484 jogos de 2003 a 2026 (2026 até a 32ª rodada)
conferidos contra 5 fontes independentes. Nos 17 placares em que uma fonte
discordou, a base estava certa; nas datas, quem errou foi a base, em 28 jogos.

O objetivo do projeto é publicar as probabilidades de cada jogo da Série A de
2027 **antes** da rodada, com registro datado no GitHub, e depois dar nota ao
próprio modelo em público, contra uma régua ingênua e contra o mercado (odds
de fechamento só como benchmark, nunca como dica de aposta). O plano completo
está em [BRIEF.md](BRIEF.md).

## O que está pronto

**Fase 0: base histórica** (23/10/2026)

- 9.165 jogos de 2003 a 2025 no Postgres (`marts.fct_jogos`): placar, rodada,
  data, mando, estádio, odds de fechamento de 2012 em diante e público da ESPN.
- 6 fontes carregadas sem raspagem de HTML, comparadas em
  [docs/fontes.md](docs/fontes.md) (cobertura, licença e limite de cada uma).
- Conferência entre fontes com todas as divergências registradas e explicadas
  em [docs/conferencia.md](docs/conferencia.md).
- **Atualização de 27/10/2026: 2026 em andamento.** A adaoduque ainda não tem
  2026, então a base desse ano é o football-data.org (319 jogos encerrados, até
  a 32ª rodada, com um jogo da 21ª adiado), conferido pela ESPN e pelo
  football-data.co.uk em todos os 319. Total: 9.484 jogos. Os arquivos da
  temporada em andamento são baixados de novo a cada carga.
- **Atualização de 30/10/2026:** 327 jogos de 2026 (até 29/10) e 53
  pendentes em `marts.jogos_pendentes`; total de 9.492 jogos. A Fase 1 segue
  com os números de 27/10.
- Estatísticas por jogo da ESPN (`marts.fct_estatisticas_jogo`): chutes desde
  2010, posse desde 2014, escanteios e faltas.

**Fase 1: mando de campo sem torcida** (23/10/2026)

- Períodos de torcida definidos por data (`dbt/seeds/periodos_torcida.csv`) e
  conferidos com o público da ESPN.
- `marts.mando_jogos` e `marts.mando_por_periodo` no dbt; intervalos de
  confiança e checagens em `analise/fase1_mando.py`, que confere as médias
  contra o SQL antes de gravar `analise/resultados_fase1.json` e o gráfico.
- Resultado e limites em [docs/fase1-mando-de-campo.md](docs/fase1-mando-de-campo.md),
  com a tabela de números para o post e onde conferir cada um.
- Card do post em `docs/img/fase1_card.png`, gerado por `analise/card_fase1.py`
  a partir do JSON (precisa do Edge ou do Chrome para renderizar).

**Painel Power BI** (23/10/2026): uma página gerada por script, com os
números conferidos contra o JSON da análise (a imagem está no topo). Ver
[dashboards/powerbi/README.md](dashboards/powerbi/README.md).

**Fase 2: modelos, backtest e previsão de 2026** (30/10/2026)

- Elo e Dixon-Coles com hiperparâmetros escolhidos em 2003 a 2011, validação
  em 2012 a 2025 e teste final no replay de 2026, rodado uma vez.
- 12 fatores testados (mando por time, forma, motivação, finalizações,
  cansaço, copas, troca de técnico, mistura com o mercado e outros). Entraram
  2: mando por time e força por finalizações. O conjunto é o modelo escolhido.
- Em 2026, RPS de 0,2023 contra 0,1960 do mercado e 0,2172 da régua ingênua:
  bate a ingênua, perde para o mercado, empata com o Elo.
- Simulação do fim de 2026 (100 mil temporadas) e um painel Power BI novo
  com ela, em [dashboards/powerbi_previsao/](dashboards/powerbi_previsao/README.md).
  Ensaio interno, não publicado.
- Resultados, ressalvas e onde conferir cada número em
  [docs/fase2-modelos-backtest.md](docs/fase2-modelos-backtest.md); plano em
  [docs/fase2-plano.md](docs/fase2-plano.md).

**Testes:** dbt com 134 testes de dados (127 passam, 7 avisos propositais
explicados abaixo) e 72 testes em Python (parser, estatísticas da ESPN,
modelos da Fase 2, sem vazamento de dados futuros, e painel da previsão).

A Fase 3 (automação para 2027) ainda não começou.

## Arquitetura

```
fontes (CSV, JSON, TXT, APIs)
   │  ingestao/  (Python: baixa com cache, carrega tudo em texto por COPY)
   ▼
raw.<fonte>_jogos            6 tabelas, uma por fonte
   │  dbt
   ▼
staging.stg_<fonte>__jogos   tipos e datas, uma view por fonte
intermediate.int_jogos__base     a base: adaoduque até 2025, football-data.org em 2026
intermediate.int_jogos__fontes   todas as fontes no mesmo formato, com o id do time
intermediate.int_datas__maioria  data mais apoiada pelas fontes
   ▼
marts.fct_jogos              um jogo por linha, 2003 a 2026 (2026 só jogos encerrados)
marts.dim_times / dim_temporadas
marts.conferencia_fontes     jogo da base x cada fonte, com a explicação da divergência
marts.resumo_conferencia     uma fonte por temporada
marts.mando_jogos / mando_por_periodo   Fase 1: jogo com o período de torcida
marts.fct_estatisticas_jogo  chutes, posse, escanteios e faltas por time e jogo (ESPN)
marts.jogos_pendentes        jogos de 2026 que faltam
   │  analise/fase1_mando.py (bootstrap, checagens, gráfico)
   │  modelos/ + analise/fase2_*.py (Elo, Dixon-Coles, fatores, backtest, simulação)
   ▼
analise/resultados_fase1.json, analise/resultados_fase2.json, docs/img/
```

| Fonte | Anos | Para quê |
|---|---|---|
| adaoduque/Brasileirao_Dataset | 2003 a 2025 | Espinha da base (única com tudo e com rodada) |
| Mendeley Data (CC BY 4.0) | 2003 a 2019 | Conferência, única para 2003 a 2005 |
| football-data.co.uk | 2012 a 2026 | Conferência e odds de fechamento |
| ESPN (API JSON pública) | 2006 a 2026 | Conferência, público, estatísticas por jogo; jogos de copa (Fase 2, fora do dbt) |
| openfootball (CC0) | 2018 a 2026 | Conferência de placar e rodada |
| football-data.org (plano gratuito) | 2023 a 2026 | Base de 2026 (única atualizada com rodada); conferência antes disso; rodadas de 2027 na Fase 3 |

## Como rodar

Precisa de Python 3.11, Docker e cerca de 5 minutos.

```powershell
copy .env.example .env      # a chave do football-data.org é opcional
docker compose up -d        # Postgres na porta 5433
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m ingestao.carregar
cd dbt
..\.venv\Scripts\python -m dbt.cli.main build --profiles-dir .
cd ..
.venv\Scripts\python -m pytest
.venv\Scripts\python analise\fase1_mando.py
.venv\Scripts\python analise\fase2_hiperparametros.py   # ~17 min
.venv\Scripts\python analise\fase2_backtest.py
.venv\Scripts\python analise\fase2_fatores.py           # ~20 min
.venv\Scripts\python analise\fase2_copas.py
.venv\Scripts\python analise\fase2_simular_2026.py
```

`analise\fase2_teste_2026.py` é o teste final: já rodou e recusa rodar de
novo. O dbt lê a porta do Postgres da variável `POSTGRES_PORT`, não do
`.env`; se o Postgres não estiver na 5433, defina a variável antes.

O dbt roda por `python -m dbt.cli.main` porque política de aplicativos do
Windows pode bloquear o `dbt.exe`. Os arquivos baixados ficam em
`dados/brutos/` (fora do Git: cada fonte tem sua licença).

## Testes

| O que garante | Teste |
|---|---|
| Um jogo por temporada + mandante + visitante | `combinacao_unica` no `fct_jogos`, `unique` no `jogo_id` |
| Placar não negativo | `valor_minimo` nos gols |
| Jogos por temporada (380; 552 em 2003 e 2004; 462 em 2005; 379 em 2016) | `assert_jogos_por_temporada` |
| Times por temporada (20 desde 2006) | `assert_times_por_temporada` |
| Cada time com 2 x (times - 1) jogos, metade em casa | `assert_jogos_por_time` |
| Todo nome de time de toda fonte tem de-para | `not_null` + `relationships` no `int_jogos__fontes` |
| Toda divergência tem explicação | `assert_divergencia_explicada` (aviso) |
| Odds do football-data.co.uk casam com algum jogo | `assert_odds_casam_com_jogos` |

Os 7 avisos esperados hoje:

| Aviso | Linhas | Por quê |
|---|---|---|
| `conferencia_data_diverge_mais_de_1_dia` | 66 | 56 linhas são os 28 jogos em que a base errou a data (ESPN e Mendeley apontam isso); 10 são da Mendeley sozinha |
| `conferencia_placar_ou_ausencia_diverge` | 21 | 17 placares em que a base está certa, 3 fontes que listam o jogo não disputado de 2016, 1 status parado na ESPN |
| `espn_jogo_nao_encerrado` | 2 | O jogo cancelado de 2016 e um jogo de 2021 parado em "segundo tempo" |
| `not_null_stg_fdcouk__jogos_gols_mandante` | 1 | O jogo não disputado de 2016, sem placar |
| `mando_sem_torcida_com_publico` | 1 | Chapecoense x Palmeiras, 18/09/2021, 115 pessoas, antes da liberação do público na 23ª rodada |
| `serie_b_publico_no_periodo_sem_torcida` | 20 | Série B: o público voltou antes (jul. a set. de 2021); esses jogos saem da comparação dos tradicionais |
| `estatisticas_gols_espn_diferente_do_placar` | 71 | Gols da lista de estatísticas da ESPN contra o placar da base: 60 linhas de 2010 a 2013 com gol a menos na ESPN, 8 espalhadas de 2014 a 2020, 3 de 2026 com gol a mais. O placar da base é conferido por outras fontes; os modelos usam só os chutes dessa lista. Causa não investigada |

Em 2026, jogo que a fonte ainda não atualizou fica como `pendente_na_fonte`
(42 no openfootball em 27/10) e não conta como divergência nem como aviso.

## Diário de bordo

Erros e achados, na ordem em que apareceram:

- **Temporada que atravessa o ano.** A temporada 2020 foi de agosto de 2020 a
  fevereiro de 2021. O CSV da base não tem coluna de temporada e a ESPN
  devolve ano civil; os dois casos estão tratados (data com exceção explícita
  no staging; campo `season` na ESPN). O teste de 380 jogos por temporada
  pegaria um erro aqui.
- **Mesma base, nomes diferentes.** O JSON de 2025 da base usa outros nomes
  ("EC Vitória" no lugar de "Vitoria"). O de-para por casamento de jogos
  denunciou: a concordância desses nomes caiu para 0,50 a 0,70.
- **Jogo inventado.** Mendeley e ESPN registram como 0x0 o jogo de 2016 que
  não aconteceu. Se uma delas fosse a base, teríamos um empate falso.
- **Datas da base.** 28 jogos de 2007 a 2010 com data 7 ou 14 dias antes da
  real; corrigidos por maioria, com a data original guardada.
- **Aviso que contava errado.** O primeiro teste de divergência usava
  `accepted_values`, que conta valores distintos: dizia "3" quando eram 21
  jogos divergentes. Trocado por um teste que devolve uma linha por jogo.
- **Antes de qual "antes"?** Contra 2003 a 2019, a queda sem torcida parece
  maior, mas o mando já vinha caindo devagar (0,006 ponto por ano). A
  comparação principal virou 2015 a 2019, mais a checagem contra a tendência.
- **Gráfico com rótulos sobrepostos.** A primeira versão tinha os dois pedaços
  de 2021 com rótulos encavalados e a legenda em cima de uma barra; corrigido
  olhando a imagem antes de publicar.
- **2026 entrou e quebrou cinco coisas** (27/10/2026). O `BRA.csv` novo do
  football-data.co.uk veio com colunas sem nome no cabeçalho (identificador
  vazio no Postgres); o openfootball anota jogo adiado como `[postponed]` e a
  anotação virou parte do nome do time (teste de unidade novo); a ESPN lista o
  jogo adiado e o remarcado, o que duplicava o confronto (adiados saem no
  staging); Chapecoense e Remo voltaram com nomes novos em três fontes
  (de-para); e jogos ainda não atualizados nas fontes viraram dezenas de
  avisos falsos, até ganharem a situação `pendente_na_fonte`.
- **Número que só a análise via.** Com 2026, o período "torcida voltou" passou
  de 2022 a 2025 para 2022 a 2026: 1.520 para 1.839 jogos e vantagem de 0,63
  para 0,64. O título, o card e o painel passaram a ler o período do JSON em
  vez de ter "2025" digitado.
- **Teste de vazamento que olhava pouco** (30/10/2026). O teste que garante
  que o replay não vê o futuro só checava rodadas antes do corte; a rodada do
  corte ficava de fora. Trocado para "até o corte". Também: o carregador
  recusa ler 2026 sem pedir, e o replay esconde as odds dos jogos futuros.
- **Faixa de 90% que acertava 86%.** Na simulação, as forças dos times
  ficavam congeladas. Com incerteza sorteada (escala escolhida em 2005 a
  2011), a cobertura foi para 90% a 91%.
- **Mais fatores, quase nenhum ganho.** Forma, ânimo, motivação, confronto,
  estilo, cansaço, técnico e copas não passaram. A mistura com o mercado
  escolheu peso 1: o melhor é o próprio mercado.

## Regras do projeto

- Nada de dica de aposta. Odds entram só como benchmark.
- Segredos só no `.env` (fora do Git); `.env.example` mostra o formato.
- O README descreve só o que existe; erro corrigido fica visível.
