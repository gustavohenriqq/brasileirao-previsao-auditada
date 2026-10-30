# Trocas de técnico da Série A (2012 a 2026)

`trocas_tecnico.csv` lista as trocas de técnico dos clubes da Série A, de 2012 até 27/10/2026 (temporada 2026 em andamento). Serve para o modelo testar o efeito "técnico novo". Cada linha é uma troca: sai um técnico, entra outro. Interinos têm linha própria, na entrada e na saída.

## Colunas

| Coluna | Conteúdo |
|---|---|
| temporada | Ano da Série A cuja página citou a troca. A temporada 2020 vai até fev/2021. |
| clube | Nome como aparece na tabela da Wikipédia em português. |
| tecnico_saiu, tecnico_entrou | Nomes como na fonte. |
| motivo | Padronizado em português: Demitido, Pediu demissão, Acordo mútuo, Fim de contrato, Fim de interinidade, Remanejado, Contratado pelo X. |
| data_saida, data_entrada | AAAA-MM-DD. Vazio quando a fonte não traz a data. |
| interino | `sim` quando quem entra é interino. `nao` nos demais casos, inclusive quando um interino sai. |
| fonte_url | Página(s) usada(s) na linha. |
| time_id | Chave de `marts.dim_times`. Todas as linhas casaram. |
| obs | Avisos de qualidade: data ausente, datas divergentes, linha vinda de uma fonte só. |

As tabelas trazem trocas de antes do início do campeonato (pré-temporada). Elas ficaram no arquivo. O modelo deve filtrar por data.

## Fonte e licença

- Wikipédia em português, páginas "Campeonato Brasileiro de Futebol de AAAA - Série A", seção "Mudança de técnicos". Base das temporadas 2012 a 2019.
- Wikipédia em inglês, páginas "AAAA Campeonato Brasileiro Série A", seção "Managerial changes" ou "Coaching changes". Usada para a data de contratação e para as linhas de interinos. Base das temporadas 2020 a 2026, porque a tabela em português não traz data de contratação.
- Acesso em 29/10/2026, pela API do MediaWiki (texto wiki das páginas).
- Licença: o texto da Wikipédia é CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/deed.pt-br). Os dados são derivados dessas páginas. Cite "Wikipédia, autores das páginas citadas em fonte_url" e redistribua sob a mesma licença.

Regras de combinação:

1. O clube, o motivo e a data de saída vêm da página em português quando a linha existe nas duas. Se as datas divergem, vale a em português e o aviso vai em `obs` (34 linhas, quase sempre 1 dia).
2. A data de entrada vem da página em inglês.
3. Quando a página em inglês separa o interino (por exemplo, A sai, interino B, depois C) e a em português cita só C, a linha segue a versão em inglês (10 casos).
4. Interinos citados só em nota de rodapé da página em português, logo após a saída do técnico, ganharam duas linhas (X sai, interino entra; interino sai, Y entra), sem data. A rodada fica em `obs` (65 linhas). Interinos de uma ou duas rodadas no meio da gestão, por ausência do titular, não entraram.

## Limites conhecidos

- **2012 a 2014:** nenhuma linha tem `data_entrada`. A tabela em português não traz essa data e a inglesa também não (2012 e 2013) ou nem tem a seção (2014). Use `data_saida` como aproximação.
- **2012 a 2019:** as tabelas só listam trocas depois do início do campeonato. Quem era o técnico no jogo 1 de cada clube não está aqui. Para o efeito "técnico novo" no começo da temporada, esse dado falta.
- **2015 a 2019:** `data_entrada` vazia em 10, 8, 17, 6 e 5 linhas (2015 a 2019). 2017 é a mais fraca.
- **Interinos de nota de rodapé:** `data_saida` do interino e `data_entrada` dele vazias. A rodada está em `obs`.
- **13 linhas** com `data_entrada` anterior à `data_saida` na própria fonte (anúncio antecipado ou erro de digitação). Mantidas e marcadas em `obs`. Uma data de 2014 numa linha de 2024 foi descartada.
- **11 linhas** existem só na página em inglês (marcadas em `obs`). Exemplo: Chapecoense 2016, acidente aéreo.
- **2026:** última linha em 27/10/2026. Trocas posteriores não estão incluídas. Refaça a coleta para atualizar.
- Os nomes dos clubes na coluna `clube` vêm de modelos da Wikipédia (por exemplo, Internacional-RS, Atlético-PR até 2018 e Athletico-PR depois). Use `time_id`, não o nome.
- Nomes de técnicos mantêm a grafia da fonte (por exemplo, Arthur Neto e Artur Neto em 2012).

## Contagem por temporada

| Temporada | Linhas | Entrada de interino | Saída dentro da Série A | Saída antes do início | Sem data_saida | Sem data_entrada |
|---|---|---|---|---|---|---|
| 2012 | 28 | 11 | 21 | 0 | 7 | 28 |
| 2013 | 30 | 6 | 26 | 0 | 4 | 30 |
| 2014 | 30 | 11 | 23 | 0 | 7 | 30 |
| 2015 | 41 | 13 | 32 | 0 | 9 | 10 |
| 2016 | 36 | 11 | 30 | 0 | 6 | 8 |
| 2017 | 34 | 13 | 23 | 0 | 11 | 17 |
| 2018 | 35 | 9 | 31 | 0 | 4 | 6 |
| 2019 | 33 | 12 | 30 | 0 | 3 | 5 |
| 2020 | 58 | 14 | 35 | 20 | 3 | 3 |
| 2021 | 43 | 9 | 20 | 16 | 7 | 7 |
| 2022 | 50 | 19 | 28 | 21 | 1 | 1 |
| 2023 | 51 | 18 | 35 | 14 | 2 | 2 |
| 2024 | 40 | 14 | 27 | 12 | 1 | 2 |
| 2025 | 43 | 13 | 30 | 12 | 1 | 1 |
| 2026 | 34 | 10 | 28 | 6 | 0 | 0 |
| Total | 586 | 183 | 419 | 101 | 66 | 150 |

"Saída dentro da Série A" conta data_saida entre o primeiro e o último jogo da temporada em `marts.fct_jogos`. Linhas sem data_saida são o fim de interinidade de nota de rodapé.

## Conferência com a dimensão de times

- Todos os clubes do arquivo casaram com `marts.dim_times`. Sem clubes sem de-para.
- Todo clube citado numa temporada tem jogos como mandante em `marts.fct_jogos` naquela temporada. Sem exceções.
