# Conferência entre fontes

Feita em 23/10/2026 sobre a base de 9.165 jogos (2003 a 2025). A temporada
2026, em andamento, foi conferida em 27/10/2026 (ver o fim do documento).

## Como

- **Chave do jogo:** temporada + mandante + visitante. Em pontos corridos cada
  par se enfrenta uma vez com cada mando, então a chave não depende da data
  (que muda com adiamento e fuso).
- **Nomes de time:** `seeds/de_para_times.csv` (260 nomes, 46 clubes). Proposto
  por `scripts/sugerir_de_para.py`, que casa jogos (mesma temporada, mesmo
  placar, data a até 1 dia) e vota no nome da base; depois revisado à mão. A
  ESPN chama de "Gremio Barueri" o clube que a base separa em Barueri (2009) e
  Gremio Prudente (2010), por isso o de-para aceita faixa de temporada.
- **O que se compara:** placar, presença do jogo, data (mais de 1 dia de
  diferença) e rodada (onde a fonte tem rodada).
- **Divergência não é apagada.** Fica em `marts.conferencia_fontes`, os testes
  em aviso contam quantas existem, e cada uma tem explicação em
  `seeds/divergencias_explicadas.csv`. Um teste em aviso lista divergência nova
  sem explicação.

## Resultado

| Fonte | Anos | Jogos em comum | Conferem | Placar diverge | Só na fonte | Data > 1 dia | Rodada diverge |
|---|---|---|---|---|---|---|---|
| Mendeley | 2003 a 2019 | 6.885 | 6.874 (99,84%) | 11 | 1 | 38 | sem rodada |
| ESPN | 2006 a 2025 | 7.599 | 7.592 (99,91%) | 6 | 1 | 28 | sem rodada |
| football-data.co.uk | 2012 a 2025 | 5.319 | 5.319 (100%) | 0 | 1 | 0 | sem rodada |
| openfootball | 2018 a 2025 | 3.040 | 3.040 (100%) | 0 | 0 | 0 | 0 |
| football-data.org | 2023 a 2025 | 1.140 | 1.140 (100%) | 0 | 0 | 0 | 0 |

ESPN tem ainda 1 jogo de 2021 com status "segundo tempo" e placar igual ao da base.

Rodada: 4.180 comparações (openfootball e football-data.org), todas iguais.

No fato: todos os 9.165 jogos têm pelo menos uma fonte de conferência; 9.157
são confirmados por pelo menos uma fonte e 7.592 por duas ou mais. Os 8 que
nenhuma fonte confirma são os placares de 2003 e 2004 explicados abaixo,
confirmados pelo RSSSF.

## O que as divergências mostraram

### Placar: a base estava certa nos 17 casos

- **2006 a 2012 (9 jogos):** a fonte divergente (ESPN em 6, Mendeley em 3) é
  minoria; as outras fontes concordam com a base. Em quase todos a fonte tem
  um gol a menos, cara de placar remontado a partir da lista de gols.
- **2003 e 2004 (8 jogos, só Mendeley):** só a base e a Mendeley cobrem esses
  anos, então era 1 contra 1. Desempate: somei gols pró e contra de cada time
  na temporada e comparei com a tabela final do RSSSF. A base bate nos 14
  times envolvidos; a Mendeley não bate em nenhum (exemplo: Vitória 2004, base
  6x1 Paraná, Mendeley 3x1; RSSSF dá ao Paraná 52-73 de saldo, igual à base).

### Jogo não disputado de 2016

Chapecoense x Atlético-MG, da 38ª rodada, não foi disputado depois do acidente
aéreo da Chapecoense. O RSSSF marca "n/p" e dá 37 jogos aos dois times. A base
não tem o jogo (2016 tem 379 jogos, e isso está em `seeds/temporadas.csv`).
**Mendeley e ESPN registram 0x0**, o que criaria um empate que não existiu;
football-data.co.uk lista o jogo sem placar.

### Datas: aqui a base errou

Em 28 jogos de 2007 a 2010, a data da base está **7 ou 14 dias antes** da data
que ESPN e Mendeley (fontes independentes) trazem juntas. Conferido no RSSSF:
Atlético-MG x Náutico, rodada 6 de 2009, foi em 14/06, não em 31/05 como na
base. O padrão (sempre 7 ou 14 dias) sugere que a base guardou a data
original da tabela, antes de adiamentos.

Correção: `fct_jogos.data` usa a data da maioria quando duas ou mais fontes
concordam entre si e a base fica a mais de 1 dia; `data_base` guarda a
original e `data_corrigida` marca os 28 jogos. A ordem dos jogos importa para
a Fase 2 (Elo e backtest só com o passado).

As outras 10 diferenças de data são da Mendeley: 4 em que ela é minoria contra
base e ESPN, e 6 de 2003 a 2005, sem fonte de desempate, em que fica a data da
base.

### 2005 e a Máfia do Apito

Os 11 jogos anulados em 2005 foram disputados de novo. Todas as fontes que
cobrem 2005 (base e Mendeley) trazem os 462 jogos com os mesmos placares, ou
seja, as duas guardam a mesma versão. Nenhuma divergência apareceu, mas também
não há uma terceira fonte para 2005; fica registrado como limite.

## Limites

- 2003 a 2005 têm uma única fonte de conferência (Mendeley).
- A maioria entre fontes não é verdade absoluta: duas fontes podem copiar o
  mesmo erro de uma origem comum. O RSSSF foi usado para desempatar os casos
  1 contra 1 e para conferir uma amostra das datas.
- O RSSSF foi consultado à mão; não entra na ingestão.

## Adendo de 27/10/2026: temporada 2026 em andamento

A adaoduque (a base até 2025) ainda não tem 2026: o último commit do repositório
é de 05/02/2026. A base de 2026 passou a ser o football-data.org, a única fonte
atualizada que traz a rodada (modelo `int_jogos__base`). Entram só os jogos
encerrados: 319, de 28/01 a 26/10/2026, até a 32ª rodada, com um jogo da 21ª
adiado. Nessa temporada o football-data.org não entra também como conferência,
porque seria a base conferindo a si mesma.

| Fonte | Jogos da base | Conferem | Placar diverge | Pendente na fonte |
|---|---|---|---|---|
| football-data.co.uk | 319 | 319 (100%) | 0 | 0 |
| ESPN | 319 | 319 (100%) | 0 | 0 |
| openfootball | 319 | 277 | 0 | 42 |

**Pendente na fonte** é uma situação nova: o jogo já foi disputado, mas a fonte
ainda não lançou o placar (o openfootball é atualizado à mão, com atraso). Só
vale para a temporada em andamento (`var temporada_em_andamento` no
`dbt_project.yml`) e não conta como divergência. Pelo mesmo motivo, jogo
futuro que a fonte já lista sem placar não aparece como "só na fonte".

Para chegar aqui, quatro problemas de ingestão apareceram e foram corrigidos:
colunas sem nome no `BRA.csv` novo do football-data.co.uk; a anotação
`[postponed]` do openfootball entrando no nome do time; o jogo adiado e o
remarcado listados juntos na ESPN (adiados saem no staging); e os nomes novos
de Chapecoense e Remo no de-para.
