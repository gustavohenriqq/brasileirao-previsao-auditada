# Brasileirão: previsão auditada

Brief do projeto, escrito em 23/10/2026. Ler inteiro antes de começar.

## A ideia

Um modelo que publica as probabilidades de cada jogo do Brasileirão Série A **antes** da rodada, com registro datado no GitHub, e depois **se dá nota em público**: contra uma régua ingênua e contra o mercado (odds de fechamento só como benchmark de qualidade, nunca como dica de aposta).

O diferencial: posts de futebol com dados no LinkedIn mostram previsões, mas nenhum mostra o placar do próprio modelo ao longo da temporada. Aqui o erro fica visível e medido, rodada a rodada.

## Por que não começar ao vivo agora

Em out/2026 faltam poucas rodadas da temporada 2026. Uma auditoria com 5 ou 6 rodadas é amostra pequena demais para dizer se o modelo é bom. A temporada que vale é a de **2027 inteira**. Até lá, o trabalho é deixar tudo pronto e testado no histórico.

## Fases

**Fase 0: base histórica (começar aqui)**
- Jogos da Série A de 2003 a 2025 (resultado, mandante, visitante, data, rodada), carregados no Postgres.
- Fontes sem scraping: um CSV histórico público (verificar qual cobre 2003 a 2025 e a licença), football-data.co.uk (resultados com odds, a partir de 2012) e a API do football-data.org (rodadas e jogos da temporada corrente; conferir o que o plano gratuito cobre).
- Conferência entre fontes: mesmo jogo, mesmo placar. Divergência vira teste em aviso, não é apagada.
- Modelagem em dbt (staging, marts), com testes.

**Fase 1: primeiro post, só com o histórico**
- Pergunta: **sem torcida (2020 e 2021), o mando de campo sumiu?** Comparar a vantagem do mandante (pontos por jogo, % de vitórias, saldo) antes, durante e depois dos jogos sem público, com intervalo de confiança.
- Resultado honesto, mesmo que a resposta seja "diminuiu, mas não sumiu".

**Fase 2: modelos e backtest**
- Régua ingênua (por exemplo, frequências históricas de mandante, empate e visitante) e régua do mercado (odds de fechamento sem a margem da casa).
- Elo e Dixon-Coles.
- Backtest temporada a temporada, sempre treinando só com o passado. Métricas: RPS, log-loss e calibração.

**Fase 3: automação para 2027**
- GitHub Actions publica as probabilidades antes de cada rodada (commit datado) e a nota depois.
- Painel em Streamlit com a evolução da nota do modelo contra as réguas.
- Ensaio opcional nas últimas rodadas de 2026, sem publicar, só para testar a automação.

## Stack

Python, Postgres, dbt, GitHub Actions, Streamlit. Gratuito sempre que possível, com o limite de cada serviço documentado.

## Regras

- Português do Brasil, sem travessão longo, palavras simples.
- README descreve o que está pronto; erro corrigido fica visível.
- Nada de dica de aposta. Odds entram só como benchmark.
- Segredos (chaves de API) só em `.env`, nunca no git.
- Confirmar com o Gustavo antes de criar repositório público, conta em serviço novo ou push.
