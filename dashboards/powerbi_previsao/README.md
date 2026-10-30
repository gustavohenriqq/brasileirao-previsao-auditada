# Painel Power BI: previsão de 2026

Ensaio interno da Fase 2, sem publicação. Três páginas (1920 x 1080) sobre a
simulação do fim do Brasileirão 2026 feita pelo modelo escolhido
(`conjunto_dc`: Dixon-Coles com mando por time e finalizações), 100 mil
simulações dos jogos que faltam:

1. **Chances:** cartões (jogos disputados e que faltam, simulações, favorito
   ao título e a chance dele, times com 1% ou mais de risco de queda); a
   tabela final prevista (posição prevista, pontos no fim, faixa de 90%, a
   posição de hoje com ▲ ou ▼ do que muda e as chances de título, G4, G6,
   Sul-Americana e Z4); ao lado, a barra de pontos de cada time (pontos de
   hoje e a faixa de 90%, dividida nos pontos esperados).
2. **Posição final:** mapa de calor time x posição. O tom é a zona da posição
   (limão título e Libertadores, violeta Sul-Americana, lavanda meio, coral
   rebaixamento) e a intensidade é a chance.
3. **Jogos e teste:** os jogos que faltam com as probabilidades do modelo
   (filtro de time) e o teste de 2026: RPS jogo a jogo contra Elo,
   Dixon-Coles, a ingênua e o mercado, e o erro nos pontos finais no replay
   da tabela.

**Não é dica de aposta.** As odds entram só como referência no teste (o
"mercado" do gráfico de RPS); o painel não mostra odds por jogo nem compara
o modelo com elas jogo a jogo. O rodapé diz isso em todas as páginas, e os
jogos usam violeta neutro em vez do limão de destaque.

Molde: o painel da Fase 1 (`dashboards/powerbi/`, que este não altera). O
gerador importa de lá os auxiliares de TMDL e PBIR, a classe `Pagina`, os
eixos e o tema; a arte usa o mesmo fundo, a bola e o renderizador.

## Como gerar

```powershell
.venv\Scripts\python dashboards\powerbi_previsao\arte\baixar_escudos.py   # escudos (17 copiados da Fase 1, 3 da Wikipédia) e logo
.venv\Scripts\python dashboards\powerbi_previsao\exportar_dados.py        # analise\ -> dados\*.csv
.venv\Scripts\python dashboards\powerbi_previsao\arte\gerar_arte.py       # fundo, títulos e ícones (uns 4 min: Edge headless)
.venv\Scripts\python dashboards\powerbi_previsao\gerar_pbip.py            # Previsao2026.pbip
```

Não precisa do banco: o exportador lê `analise/simulacao_2026_*.csv` e as
seções `simulacao_2026` e `teste_2026` de `analise/resultados_fase2.json`.
Para uma simulação nova, rode `analise/fase2_simular_2026.py` e depois os
passos acima.

Abra `Previsao2026.pbip` no Power BI Desktop e clique em Atualizar > Dados.
Sem a interface: `tools\atualizar_modelo.ps1` faz o refresh pelo motor; depois
clique em "Atualizar agora" na barra do relatório para os visuais lerem os
dados novos. Com o arquivo aberto e atualizado, confira os números:

```powershell
.venv\Scripts\python dashboards\powerbi_previsao\tools\conferir_painel.py
```

## Decisões

- **CSV, não banco.** Os números já estão fechados na análise; o painel só
  mostra. O parâmetro `PastaDados` guarda o caminho da pasta `dados\`.
- **Ordem dos times pelos pontos esperados** (`ordem_prevista`, desempate na
  posição esperada), também no mapa de posições e na barra de pontos. Na
  tabela da página 1 essa ordem é o "#": a tabela final prevista. A posição de
  hoje fica na coluna "Hoje", em verde quando o time sobe e coral quando desce.
  É a ordem da média de pontos, não a posição mais provável de cada time: numa
  briga apertada as duas podem diferir, e o mapa da página 2 mostra isso.
- **Chance em texto na tabela.** Zero fica em branco, e as pontas viram
  "<0,1%" e ">99,9%": um "0,0%" ou "100,0%" arredondado diria que algo é
  impossível ou certo quando não é. No mapa de posições, "<1%" e ">99%".
- **Filtro de time por medida nos jogos.** O time pode ser mandante ou
  visitante, então a tabela de jogos não se liga aos times; a medida
  `Jogo no filtro` esconde a linha (todas as medidas em branco) quando o jogo
  não é do time escolhido.
- **Limites das cores são desenho, não dado:** sem cor abaixo de 0,1%, depois
  faixas até 5%, 25%, 50%, 75% e acima. Estão em `FAIXAS` no gerador.
- **O mercado não tem replay da tabela**: as odds são por jogo, não por
  campeonato. Por isso ele aparece só no gráfico de RPS.

## O que custou tempo (para não repetir)

- **`open_application` abriu uma segunda janela vazia do Desktop**, que ficou
  na frente e recebia os cliques (a tela mostrava o painel, mas o clique ia
  para a janela vazia). Para trazer o Desktop para frente, use a janela que já
  está aberta; para regerar, feche sem salvar e abra o `.pbip` de novo.
- **Refresh pelo motor não redesenha os visuais.** Depois de
  `atualizar_modelo.ps1`, os cartões ficaram "(Em branco)" até clicar em
  "Atualizar agora" na barra amarela.
- **Texto longo em cartão de 40 pt** ("327 de 380", "Flamengo") saiu cortado.
  O cartão do favorito usa 30 pt e o de jogos mostra só o número.
- **Título grande quebrava em duas linhas** a 60 px; ficou em 50 px com
  `nowrap`.
- **`wordWrap` em `columnHeaders` deixou a tabela vazia** (sem erro aparente).
  Para o cabeçalho não quebrar, alargue a coluna: cabeçalho em duas linhas
  empurra o 20º time para fora da tabela.

## Conferência

Em 30/10/2026, com o arquivo aberto e atualizado: as 63 medidas rodam sem erro
(`dashboards/powerbi/tools/testar_medidas.ps1`) e `conferir_painel.py` passou
nas 579 conferências: cartões e totais contra o JSON; os 20 times (pontos,
faixa, posição esperada, posição na tabela final prevista e o texto "Hoje",
as cinco chances e o texto delas); as chances de cada
zona recalculadas pela tabela de posições; cada time e cada posição somando
1; cada um dos 53 jogos somando 1; os jogos de cada time pelo filtro; RPS e
erro de pontos de cada modelo.
