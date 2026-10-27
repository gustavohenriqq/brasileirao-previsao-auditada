# Fontes de dados

Pesquisa feita em 23/10/2026. Nenhuma fonte usa raspagem de HTML: são arquivos
publicados (CSV, JSON, TXT) ou APIs JSON. Cobertura e limites abaixo foram
**medidos**, não copiados da página de cada serviço, salvo onde está escrito.

## Comparação

| Fonte | O que traz | Anos (2003 a 2026) | Rodada | Licença | Limite gratuito | Papel no projeto |
|---|---|---|---|---|---|---|
| [adaoduque/Brasileirao_Dataset](https://github.com/adaoduque/Brasileirao_Dataset) (GitHub) | Placar, data, hora, rodada, estádio, UF, técnicos e formação (recentes); estatísticas, gols e cartões em arquivos à parte | 2003 a 2025 (CSV até 2024, JSON por temporada inclui 2025; sem 2026 em 27/10/2026) | Sim | **Nenhuma declarada** | Sem limite (raw.githubusercontent) | **Espinha da base** até 2025 |
| [Mendeley Data "Brazilian Championship A-Series"](https://data.mendeley.com/datasets/thsvj4sycn) | Placar, data, hora, turno | 2003 a 2019 | Só turno (1 ou 2) | CC BY 4.0 | Sem limite | Conferência, única para 2003 a 2005 |
| [football-data.co.uk](https://www.football-data.co.uk/brazil.php), arquivo `BRA.csv` | Placar, data, hora (Reino Unido), **odds de fechamento** (Pinnacle, média e máxima do mercado, Betfair, bet365) | 2012 a 2026 (2026 em andamento) | Não | Nenhuma declarada; aviso de "sem garantia de correção" | Sem limite declarado | Conferência e **odds para a régua do mercado** (Fase 2) |
| [football-data.org](https://www.football-data.org) API v4, competição BSA | Placar, data UTC, rodada, status, tabela | **2023 a 2026** no plano gratuito (testado: 2022 e antes devolvem 403) | Sim | Termos do serviço; dados atrasados no plano gratuito | 10 chamadas por minuto, 12 competições, precisa de cadastro e chave | **Base de 2026** (jogos encerrados); conferência de 2023 a 2025; **rodadas e jogos de 2027** na Fase 3 |
| ESPN, API JSON pública (`site.api.espn.com`, liga `bra.1`) | Placar, data UTC, status, estádio, **público** | 2006 a 2026 (2003 a 2005 vazios) | Não | Não documentada, sem termos de reuso; uso pessoal e de estudo | Sem chave; sem limite publicado (usamos pausa de 0,5 s) | Conferência e público para a Fase 1 (com ressalvas) |
| [openfootball/brazil](https://github.com/openfootball/brazil) | Placar, data, hora, rodada (texto Football.TXT) | 2018 a 2026 (2026 com atraso) | Sim | CC0 (domínio público) | Sem limite | Conferência de placar e de rodada |

## Recomendação e por quê

1. **Espinha: adaoduque.** É a única fonte que cobre 2003 a 2025 inteiro com
   rodada. Escolhida por cobertura, não por licença: ela não declara licença,
   então o bruto **não é redistribuído** no repositório (a ingestão baixa de
   novo, `dados/brutos/` está no `.gitignore`) e o projeto cita a fonte. Se o
   repositório virar público, vale pedir autorização ao autor (contato no
   README dele).
2. **Conferência com quatro fontes independentes**, para que cada temporada
   tenha pelo menos uma segunda opinião: Mendeley cobre 2003 a 2019 (sem ela,
   2003 a 2005 ficariam sem conferência), ESPN 2006 a 2026, football-data.co.uk
   2012 a 2026, openfootball 2018 a 2026 e football-data.org 2023 a 2025.
3. **Odds só do football-data.co.uk**, e só como régua de comparação. Em 2025 a
   Pinnacle falta em 44 jogos; a média do mercado está completa.
4. **football-data.org fica para o ao vivo.** Para o histórico ele só cobre três
   temporadas; o valor dele é a Fase 3 (calendário e rodadas de 2027). A chave
   fica no `.env`. **Atualização de 27/10/2026:** como a adaoduque ainda não
   publicou 2026, ele virou a base da temporada em andamento (só jogos
   encerrados), conferido pela ESPN e pelo football-data.co.uk.
5. **ESPN entra pelo público**, não pelo placar: é a única com público por jogo.
   Mas o público vem 0 em todos os jogos de 2006 a 2014 (dado ausente, não
   portão fechado) e tem buracos em 2016 (111 zeros) e 2018 (113 zeros). Na
   Fase 1, "sem torcida" deve vir das datas oficiais, com o público da ESPN
   só como apoio a partir de 2015.

## Descartadas

- **Kaggle** (vários CSVs do Brasileirão): exigem conta e repetem as fontes acima.
- **Base dos Dados** (BigQuery): exige conta Google Cloud e projeto de
  faturamento, para dados que já temos.
- **FBref, Soccerway, Transfermarkt**: só por raspagem de HTML, fora da regra do brief.
- **RSSSF**: usado só como **desempate manual** na investigação das
  divergências (tabela final com gols pró e contra, jogo não disputado de
  2016, datas da rodada 6 de 2009), não como fonte da ingestão.

## Pegadinhas de cada fonte

- **adaoduque:** o CSV não diz a temporada, e 2020 terminou em fevereiro de
  2021; a temporada vem da data, com essa exceção escrita no staging. O JSON
  de 2025 usa outros nomes de time ("EC Vitória", "Grêmio") e 116 datas sem
  ano ("15/10"). Em 2007 a 2010, 28 datas estão 7 ou 14 dias antes da real
  (ver [conferencia.md](conferencia.md)).
- **Mendeley:** arquivo em Latin-1, separador `;`, placar como `4x2`, nomes com
  UF (`Atlético/MG`). `ROUND` é o turno. Registra o jogo não disputado de 2016
  como 0x0.
- **football-data.co.uk:** hora do Reino Unido, então jogo noturno no Brasil
  pode cair no dia seguinte. Sem rodada.
- **ESPN:** `dates=AAAA` devolve o **ano civil**; a temporada vem do campo
  `season` de cada jogo. A resposta vem compactada (gzip). Um jogo de 2021
  ficou com status de segundo tempo.
- **openfootball:** data e hora valem para as linhas seguintes até aparecer
  outra; o ano só aparece quando muda. Parser em `ingestao/fontes.py`, com
  teste em `tests/`.
- **football-data.org:** o código da competição é `BSA`; `season=2022` ou
  antes devolve 403 no plano gratuito.
