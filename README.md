# Brasileirão: previsão auditada

**Sem torcida, a vantagem do mandante na Série A caiu quase pela metade, mas
não sumiu: de 0,80 ponto por jogo a mais que o visitante (2015 a 2019) para
0,44 nos 594 jogos sem público de 2020 e 2021.** A queda passa em três
checagens: contra a tendência histórica, dentro do mesmo time (17 de 21 times
caíram) e reamostrando rodadas inteiras. Detalhes em
[docs/fase1-mando-de-campo.md](docs/fase1-mando-de-campo.md).

A base por trás: 9.165 jogos de 2003 a 2025 conferidos contra 5 fontes
independentes. Nos 17 placares em que uma fonte discordou, a base estava
certa; nas datas, quem errou foi a base, em 28 jogos.

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

**Testes:** dbt com 76 testes de dados (71 passam, 5 avisos propositais
explicados abaixo) e 3 testes de unidade do parser.

Fases 2 (modelos e backtest) e 3 (automação para 2027) ainda não começaram.

## Arquitetura

```
fontes (CSV, JSON, TXT, APIs)
   │  ingestao/  (Python: baixa com cache, carrega tudo em texto por COPY)
   ▼
raw.<fonte>_jogos            6 tabelas, uma por fonte
   │  dbt
   ▼
staging.stg_<fonte>__jogos   tipos e datas, uma view por fonte
intermediate.int_jogos__fontes   todas as fontes no mesmo formato, com o id do time
intermediate.int_datas__maioria  data mais apoiada pelas fontes
   ▼
marts.fct_jogos              um jogo por linha, 2003 a 2025
marts.dim_times / dim_temporadas
marts.conferencia_fontes     jogo da base x cada fonte, com a explicação da divergência
marts.resumo_conferencia     uma fonte por temporada
marts.mando_jogos / mando_por_periodo   Fase 1: jogo com o período de torcida
   │  analise/fase1_mando.py (bootstrap, checagens, gráfico)
   ▼
analise/resultados_fase1.json + docs/img/fase1_vantagem_por_temporada.png
```

| Fonte | Anos | Para quê |
|---|---|---|
| adaoduque/Brasileirao_Dataset | 2003 a 2025 | Espinha da base (única com tudo e com rodada) |
| Mendeley Data (CC BY 4.0) | 2003 a 2019 | Conferência, única para 2003 a 2005 |
| football-data.co.uk | 2012 a 2025 | Conferência e odds de fechamento |
| ESPN (API JSON pública) | 2006 a 2025 | Conferência e público |
| openfootball (CC0) | 2018 a 2025 | Conferência de placar e rodada |
| football-data.org (plano gratuito) | 2023 a 2025 | Conferência; rodadas de 2027 na Fase 3 |

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
```

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

Os 5 avisos esperados hoje:

| Aviso | Linhas | Por quê |
|---|---|---|
| `conferencia_data_diverge_mais_de_1_dia` | 66 | 56 linhas são os 28 jogos em que a base errou a data (ESPN e Mendeley apontam isso); 10 são da Mendeley sozinha |
| `conferencia_placar_ou_ausencia_diverge` | 21 | 17 placares em que a base está certa, 3 fontes que listam o jogo não disputado de 2016, 1 status parado na ESPN |
| `espn_jogo_nao_encerrado` | 2 | O jogo cancelado de 2016 e um jogo de 2021 parado em "segundo tempo" |
| `not_null_stg_fdcouk__jogos_gols_mandante` | 1 | O jogo não disputado de 2016, sem placar |
| `mando_sem_torcida_com_publico` | 1 | Chapecoense x Palmeiras, 18/09/2021, 115 pessoas, antes da liberação do público na 23ª rodada |

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

## Regras do projeto

- Nada de dica de aposta. Odds entram só como benchmark.
- Segredos só no `.env` (fora do Git); `.env.example` mostra o formato.
- O README descreve só o que existe; erro corrigido fica visível.
