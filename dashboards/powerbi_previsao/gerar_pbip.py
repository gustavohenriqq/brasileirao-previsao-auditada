"""Gera o projeto Power BI da previsão de 2026 (PBIP: modelo em TMDL e
relatório em PBIR).

Três páginas, 1920 x 1080, sobre os CSVs de dados/ (gerados por
exportar_dados.py):
1. Chances de cada time: classificação com pontos esperados, faixa de 90% e
   chances de título, G4, G6, Sul-Americana e Z4; ao lado, a faixa de pontos
   de cada time.
2. Posição final: mapa de calor time x posição.
3. Jogos que faltam: probabilidades jogo a jogo (filtro de time) e o teste do
   modelo em 2026 contra as referências.

Molde: dashboards/powerbi/gerar_pbip.py (painel da Fase 1, só leitura). Os
auxiliares de TMDL e PBIR, a classe Pagina, os eixos e o tema vêm de lá, com
o namespace dos lineageTag trocado para o deste painel.

Regras:
- Nenhum número do painel é digitado aqui: tudo sai de medida DAX. Os limites
  das faixas de cor (1%, 5%, 25%...) são escolha de desenho, não dado.
- Nada de dica de aposta: o mercado aparece só como referência no teste.

Uso: python dashboards/powerbi_previsao/gerar_pbip.py
     Depois, no Desktop: abrir Previsao2026.pbip (ou "Aplicar alterações externas").
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NOME = "Previsao2026"
MODELO = PASTA / f"{NOME}.SemanticModel"
RELATORIO = PASTA / f"{NOME}.Report"
ARTE = PASTA / "arte" / "png"
NS = uuid.UUID("6b1d7c3e-1f2a-4b8e-9c55-2027b0a5e002")

_spec = importlib.util.spec_from_file_location("molde_fase1", PASTA.parent / "powerbi" / "gerar_pbip.py")
molde = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(molde)
molde.NS = NS  # tag() e nome_visual() do molde passam a usar o namespace deste painel

L, txt, num, cor, props = molde.L, molde.txt, molde.num, molde.cor, molde.props
medida_ref, coluna_ref, cor_medida = molde.medida_ref, molde.coluna_ref, molde.cor_medida
proj_medida, proj_coluna, cabecalho, eixos = molde.proj_medida, molde.proj_coluna, molde.cabecalho, molde.eixos
tag = molde.tag

NAVY, PAINEL, PAINEL2, BORDA = molde.NAVY, molde.PAINEL, molde.PAINEL2, molde.BORDA
LIMAO, VIOLETA, LAVANDA, BRANCO = molde.LIMAO, molde.VIOLETA, molde.LAVANDA, molde.BRANCO
TEXTO, QUEDA, ALTA = molde.TEXTO, molde.QUEDA, molde.ALTA


# ---------------------------------------------------------------------------
# Modelo (TMDL)
# ---------------------------------------------------------------------------
S, I, D = ("string", "type text"), ("int64", "Int64.Type"), ("double", "type number")


def col(nome: str, tipo: tuple, fmt: str | None = None, ordem: str | None = None) -> tuple:
    return (nome, tipo[0], tipo[1], fmt, ordem)


COLUNAS = {
    "times": [
        col("time_id", S), col("time", S, ordem="ordem_prevista"), col("posicao_atual", I, "0"),
        col("pontos_atuais", I, "0"), col("vitorias_atuais", I, "0"), col("saldo_atual", I, "0"),
        col("gols_pro_atuais", I, "0"), col("jogos_disputados", I, "0"), col("jogos_restantes", I, "0"),
        col("pontos_esperados", D, "0.0"), col("pontos_p5", D, "0"), col("pontos_p95", D, "0"),
        col("posicao_esperada", D, "0.0"), col("p_titulo", D, "0.0%"), col("p_g4", D, "0.0%"),
        col("p_g6", D, "0.0%"), col("p_sul_americana", D, "0.0%"), col("p_z4", D, "0.0%"),
        col("ordem_prevista", I, "0"), col("escudo", S),
    ],
    "posicoes": [
        col("time_id", S), col("posicao", I, "0"), col("probabilidade", D, "0.0%"),
        col("posicao_rotulo", S, ordem="posicao"), col("zona", S, ordem="zona_ordem"), col("zona_ordem", I, "0"),
    ],
    "jogos": [
        col("id_jogo", S), col("ordem", I, "0"), col("rodada", I, "0"),
        ("data", "dateTime", "type date", "dd/mm/yyyy", None), col("quando", S, ordem="ordem"),
        col("mandante", S), col("visitante", S), col("mandante_id", S), col("visitante_id", S),
        col("p_mandante", D, "0%"), col("p_empate", D, "0%"), col("p_visitante", D, "0%"),
        col("placar_mais_provavel", S),
    ],
    "modelos": [
        col("modelo", S), col("rotulo", S, ordem="ordem"), col("papel", S), col("ordem", I, "0"),
        col("rps", D, "0.000"), col("log_loss", D, "0.000"), col("erro_pontos", D, "0.00"),
        col("erro_posicao", D, "0.00"), col("cobertura_90", D, "0%"),
    ],
    "info": [
        col("simulacoes", I, "#,0"), col("jogos_disputados", I, "0"), col("jogos_restantes", I, "0"),
        col("jogos_total", I, "0"), ("ultimo_jogo", "dateTime", "type date", "dd/mm/yyyy", None),
        col("pendentes_sem_data", I, "0"), col("incerteza", D, "0.0"), col("jogos_teste", I, "0"),
        col("cortes_replay", I, "0"), col("cortes_texto", S), col("rodada_alvo_replay", I, "0"),
        col("gerado_em", S),
    ],
}
TABELAS = {
    # tabela: arquivo, colunas que podem vir vazias, descrição
    "times": ("times.csv", [], "Um time da Série A de 2026: situação atual e resultado das simulações."),
    "posicoes": ("posicoes.csv", [], "Um time em uma posição final, com a probabilidade (20 x 20)."),
    "jogos": ("jogos.csv", ["data"], "Um jogo que falta, com as probabilidades do modelo (data vazia = a definir)."),
    "modelos": ("modelos.csv", ["erro_pontos", "erro_posicao", "cobertura_90"],
                "Um modelo no teste de 2026. O mercado é só referência e não tem replay da tabela."),
    "info": ("info.csv", [], "Uma linha com os totais da simulação e do teste."),
}

# Zonas: rótulo na tabela, coluna em times, cor da escala
ZONAS = [("Título", "p_titulo", LIMAO), ("G4", "p_g4", LIMAO), ("G6", "p_g6", LIMAO),
         ("Sul-Americana", "p_sul_americana", VIOLETA), ("Z4", "p_z4", QUEDA)]
# Cor de cada faixa exclusiva no mapa de posições
COR_ZONA = {"Título": LIMAO, "G4": LIMAO, "G6": LIMAO, "Sul-Americana": VIOLETA, "Meio": LAVANDA, "Z4": QUEDA}
# Escala de intensidade: limite superior de cada faixa de probabilidade e opacidade da cor sobre o painel
FAIXAS = [(0.05, 0.18), (0.25, 0.34), (0.5, 0.55), (0.75, 0.75), (None, 0.95)]
MINIMO = 0.001  # abaixo disso a célula fica sem cor


def _rgb(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def misturar(frente: str, alfa: float, fundo: str = PAINEL) -> str:
    f, b = _rgb(frente), _rgb(fundo)
    return "#" + "".join(f"{round(alfa * x + (1 - alfa) * y):02X}" for x, y in zip(f, b))


def letra_para(fundo: str) -> str:
    r, g, b = (c / 255 for c in _rgb(fundo))
    return NAVY if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45 else BRANCO


def dax_escala(p: str, base: str, letra: bool = False) -> str:
    """SWITCH de cor pela probabilidade p (expressão DAX): fundo ou letra."""
    ramos = []
    for lim, alfa in FAIXAS:
        fundo = misturar(base, alfa)
        valor = f'"{letra_para(fundo) if letra else fundo}"'
        ramos.append(f"p < {lim}, {valor}" if lim is not None else valor)
    vazio = f'"{BRANCO}"' if letra else "BLANK ()"
    return f"SWITCH ( TRUE (), ISBLANK ( p ) || p < {MINIMO}, {vazio}, {', '.join(ramos)} )"


def dax_texto_pct(expr: str, inteiro: bool = False) -> str:
    """Probabilidade em texto: vazio quando é zero, "<0,1%" e ">99,9%" nas
    pontas (o "0,0%" e o "100,0%" arredondados enganariam)."""
    if inteiro:
        baixo, alto, fmt = ('p < 0.005, "<1%"', 'p >= 0.995, ">99%"', '"0%"')
    else:
        baixo, alto, fmt = ('p < 0.0005, "<0,1%"', 'p >= 0.9995, ">99,9%"', '"0.0%"')
    return (f'VAR p = {expr} RETURN SWITCH ( TRUE (), ISBLANK ( p ) || p = 0, BLANK (), p = 1, "100%", '
            f"{alto}, {baixo}, FORMAT ( p, {fmt} ) )")


def medidas() -> list:
    m = [
        # nome, DAX, formato, pasta, descrição
        ("Jogos disputados", "SUM ( info[jogos_disputados] )", "#,0", "KPI", "Jogos de 2026 já jogados."),
        ("Jogos restantes", "SUM ( info[jogos_restantes] )", "#,0", "KPI", "Jogos que a simulação sorteia."),
        ("Simulações", "SUM ( info[simulacoes] )", "#,0", "KPI", "Quantas vezes o fim do campeonato foi sorteado."),
        ("Favorito ao título", "MAXX ( TOPN ( 1, ALL ( times ), times[p_titulo], DESC ), times[time] )",
         None, "KPI", "Time com a maior chance de título."),
        ("Chance do favorito", "MAXX ( ALL ( times ), times[p_titulo] )", "0.0%", "KPI",
         "Maior chance de título entre os times."),
        ("Times em risco de queda", "COUNTROWS ( FILTER ( ALL ( times ), times[p_z4] >= 0.01 ) )", "0", "KPI",
         "Times com 1% ou mais de chance de terminar no Z4."),

        ("Pontos", "SUM ( times[pontos_atuais] )", "0", "Times", "Pontos até agora."),
        ("Jogos do time", "SUM ( times[jogos_disputados] )", "0", "Times", "Jogos disputados pelo time."),
        ("Pontos esperados", "SUM ( times[pontos_esperados] )", "0.0", "Times", "Média dos pontos finais nas simulações."),
        ("Pontos p5", "SUM ( times[pontos_p5] )", "0", "Times", "5% das simulações terminam com menos pontos."),
        ("Pontos p95", "SUM ( times[pontos_p95] )", "0", "Times", "5% das simulações terminam com mais pontos."),
        ("Faixa de 90%",
         'IF ( HASONEVALUE ( times[time_id] ), FORMAT ( [Pontos p5], "0" ) & " a " & FORMAT ( [Pontos p95], "0" ) )',
         None, "Times", "Pontos finais em 90% das simulações."),
        ("Posição esperada", "SUM ( times[posicao_esperada] )", "0.0", "Times", "Média da posição final."),
        ("Posição atual", "SUM ( times[posicao_atual] )", "0", "Times", "Posição na tabela de hoje."),
        ("Posição prevista", "SUM ( times[ordem_prevista] )", "0", "Times",
         "Posição na tabela final prevista (ordem dos pontos esperados)."),
        ("Variação prevista", "[Posição atual] - [Posição prevista]", "+0;-0;0", "Times",
         "Posições que o time sobe (positivo) ou desce (negativo) até o fim, pela previsão."),
        ("Texto hoje",
         'VAR v = [Variação prevista] RETURN IF ( HASONEVALUE ( times[time_id] ), '
         'FORMAT ( [Posição atual], "0" ) & "º" & SWITCH ( TRUE (), v > 0, "  ▲" & v, v < 0, "  ▼" & -v, "" ) )',
         None, "Times", "Posição de hoje com a seta do que muda até a tabela final prevista."),

        ("Barra pontos atuais", "[Pontos]", "0", "Faixa", "Primeiro pedaço da barra: pontos que o time já tem."),
        ("Barra vão", "[Pontos p5] - [Pontos]", "0", "Faixa",
         "Pedaço sem cor, dos pontos atuais até o início da faixa."),
        ("Barra até o esperado", "MAX ( 0, [Pontos esperados] - [Pontos p5] )", "0.0", "Faixa",
         "Do início da faixa de 90% até os pontos esperados."),
        ("Barra acima do esperado", "MAX ( 0, [Pontos p95] - [Pontos esperados] )", "0.0", "Faixa",
         "Dos pontos esperados até o fim da faixa de 90%."),

        ("Chance na posição", "SUM ( posicoes[probabilidade] )", "0.0%", "Posições",
         "Probabilidade de terminar na posição."),
        ("Texto da posição", dax_texto_pct("[Chance na posição]", inteiro=True), None, "Posições",
         "Chance na posição em texto, para o mapa de calor."),

        ("Jogo no filtro",
         "VAR t = SELECTEDVALUE ( times[time_id] ) RETURN IF ( ISBLANK ( t ) || "
         "SELECTEDVALUE ( jogos[mandante_id] ) = t || SELECTEDVALUE ( jogos[visitante_id] ) = t, 1 )",
         "0", "Jogos", "1 se o jogo é do time escolhido no filtro (ou se não há time escolhido)."),
        ("Mandante vence", "IF ( [Jogo no filtro] = 1, SUM ( jogos[p_mandante] ) )", "0%", "Jogos",
         "Chance de vitória do mandante."),
        ("Empate", "IF ( [Jogo no filtro] = 1, SUM ( jogos[p_empate] ) )", "0%", "Jogos", "Chance de empate."),
        ("Visitante vence", "IF ( [Jogo no filtro] = 1, SUM ( jogos[p_visitante] ) )", "0%", "Jogos",
         "Chance de vitória do visitante."),
        ("Jogos na lista", "SUMX ( VALUES ( jogos[id_jogo] ), [Jogo no filtro] )", "0", "Jogos",
         "Jogos que aparecem na tabela com o filtro de time."),
        ("Título dos jogos",
         'IF ( ISFILTERED ( times[time] ) && HASONEVALUE ( times[time] ), '
         'FORMAT ( [Jogos na lista], "0" ) & " jogos que faltam para o " & SELECTEDVALUE ( times[time] ), '
         'FORMAT ( [Jogos na lista], "0" ) & " jogos que faltam" )',
         None, "Jogos", "Título da tabela de jogos, com a contagem."),

        ("RPS", "SUM ( modelos[rps] )", "0.000", "Teste", "Erro de probabilidade jogo a jogo (menor é melhor)."),
        ("Erro de pontos", "SUM ( modelos[erro_pontos] )", "0.0", "Teste",
         "Erro médio nos pontos finais de cada time, no replay da tabela."),
        ("Subtítulo do RPS",
         'FORMAT ( SUM ( info[jogos_teste] ), "0" ) & " jogos de 2026 · menor é melhor · mercado só como referência"',
         None, "Teste", "Subtítulo do gráfico de RPS."),
        ("Subtítulo do replay",
         '"Previsto nas rodadas " & MAX ( info[cortes_texto] ) & " · real na " '
         '& FORMAT ( SUM ( info[rodada_alvo_replay] ), "0" ) & "ª rodada"',
         None, "Teste", "Subtítulo do gráfico de erro de pontos."),
        ("Cor do modelo",
         f'SWITCH ( SELECTEDVALUE ( modelos[papel] ), "escolhido", "{LIMAO}", "referencia", "{LAVANDA}", "{VIOLETA}" )',
         None, "Cores", "Limão no modelo escolhido, lavanda no mercado."),
        ("Letra hoje",
         f'VAR v = [Variação prevista] RETURN SWITCH ( TRUE (), v > 0, "{ALTA}", v < 0, "{QUEDA}", "{LAVANDA}" )',
         None, "Cores", "Verde se o time sobe até o fim, coral se desce, lavanda se fica."),
    ]
    for rotulo, coluna, base in ZONAS:
        chance = f"Chance de {rotulo}" if rotulo != "Título" else "Chance de título"
        m += [
            (chance, f"SUM ( times[{coluna}] )", "0.0%", "Chances", f"Chance de terminar em {rotulo}."),
            (f"Texto {rotulo}", dax_texto_pct(f"[{chance}]"), None, "Chances", f"{chance} em texto, para a tabela."),
            (f"Fundo {rotulo}", f"VAR p = [{chance}] RETURN {dax_escala('p', base)}", None, "Cores",
             "Cor de fundo pela chance."),
            (f"Letra {rotulo}", f"VAR p = [{chance}] RETURN {dax_escala('p', base, letra=True)}", None, "Cores",
             "Cor da letra pelo fundo."),
        ]
    for medida in ("Mandante vence", "Empate", "Visitante vence"):
        m += [
            (f"Fundo {medida}", f"VAR p = [{medida}] RETURN {dax_escala('p', VIOLETA)}", None, "Cores",
             "Cor de fundo pela probabilidade (violeta, neutro: não é destaque de aposta)."),
            (f"Letra {medida}", f"VAR p = [{medida}] RETURN {dax_escala('p', VIOLETA, letra=True)}", None, "Cores",
             "Cor da letra pelo fundo."),
        ]
    zona = "SELECTEDVALUE ( posicoes[zona] )"
    for nome, letra in (("Fundo da posição", False), ("Letra da posição", True)):
        ramos = ", ".join(f'z = "{z}", {dax_escala("p", c, letra)}' for z, c in COR_ZONA.items())
        m.append((nome, f"VAR p = [Chance na posição] VAR z = {zona} RETURN SWITCH ( TRUE (), {ramos} )",
                  None, "Cores", "Cor da célula: tom da zona da posição, intensidade da chance."))
    return m


def tmdl_medidas() -> str:
    blocos = []
    for nome, dax, fmt, pasta, doc in medidas():
        n = f"'{nome}'" if not nome.isidentifier() else nome
        linhas = [f"\t/// {doc}", f"\tmeasure {n} = {dax}"]
        if fmt:
            linhas.append(f"\t\tformatString: {fmt}")
        linhas += [f"\t\tdisplayFolder: {pasta}", f"\t\tlineageTag: {tag('medida', nome)}", ""]
        blocos.append("\n".join(linhas))
    return ("/// Só medidas. Todo número do painel sai daqui.\ntable _Medidas\n"
            f"\tlineageTag: {tag('tabela', '_Medidas')}\n\n" + "\n".join(blocos))


def gerar_modelo() -> None:
    if MODELO.exists():
        shutil.rmtree(MODELO / "definition", ignore_errors=True)
    d = MODELO / "definition"
    (d / "tables").mkdir(parents=True)
    (MODELO / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n\n", encoding="utf-8")
    ordem = ", ".join(f'"{t}"' for t in ["PastaDados", *TABELAS])
    refs = "".join(f"ref table {t}\n" for t in [*TABELAS, "_Medidas"])
    (d / "model.tmdl").write_text(f"""model Model
\tculture: pt-BR
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: pt-BR
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0

annotation PBI_ProTooling = ["DevMode"]

annotation PBI_QueryOrder = [{ordem.replace(', ', ',')}]

{refs}""", encoding="utf-8")
    pasta_dados = str(PASTA / "dados") + "\\"
    (d / "expressions.tmdl").write_text(
        f'/// Pasta dos CSVs gerados por exportar_dados.py (caminho desta máquina).\n'
        f'expression PastaDados = "{pasta_dados}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag('expressao', 'PastaDados')}\n\n\tannotation PBI_ResultType = Text\n",
        encoding="utf-8")
    # Só posições se liga aos times: jogos usa o filtro de time por medida (o
    # time pode ser mandante ou visitante), modelos e info são soltas
    (d / "relationships.tmdl").write_text(
        f"relationship {tag('relacao', 'posicoes', 'times')}\n"
        "\tfromColumn: posicoes.time_id\n\ttoColumn: times.time_id\n", encoding="utf-8")
    for tabela, (arquivo, nulos, doc) in TABELAS.items():
        (d / "tables" / f"{tabela}.tmdl").write_text(
            molde.tmdl_tabela_csv(tabela, arquivo, COLUNAS[tabela], nulos, doc), encoding="utf-8")
    (d / "tables" / "_Medidas.tmdl").write_text(tmdl_medidas(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Relatório (PBIR)
# ---------------------------------------------------------------------------
def com_cor(medida: str, fundo: str, letra: str) -> list:
    """Fundo e letra de uma coluna-medida de tabela ou matriz, vindos de medidas."""
    alvo = {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"_Medidas.{medida}"}
    return [{"properties": {"backColor": cor_medida(fundo), "fontColor": cor_medida(letra)}, "selector": alvo}]


def largura(ref: str, px: int) -> dict:
    return {"properties": {"value": num(px)}, "selector": {"metadata": ref}}


def centro(ref: str) -> dict:
    return {"properties": {"alignment": txt("Center")}, "selector": {"metadata": ref}}


def titulo_medida(medida: str, subtitulo: str | None = None) -> dict:
    o = cabecalho("x", subtitulo)
    o["title"] = props(show=L("true"), text={"expr": medida_ref(medida)}, fontColor=cor(BRANCO),
                       fontSize=num(22), bold=L("true"))
    return o


ESTILO_TABELA = {
    "columnHeaders": props(fontColor=cor(LIMAO), backColor=cor(PAINEL2), fontSize=num(14), bold=L("true")),
    "total": props(totals=L("false")),
}
VALORES_TABELA = {"properties": {"fontColorPrimary": cor(BRANCO), "backColorPrimary": cor(PAINEL),
                                 "fontColorSecondary": cor(BRANCO), "backColorSecondary": cor("#181C45"),
                                 "fontSize": num(15)}}


class Pagina(molde.Pagina):
    def cabecalho_pagina(self, chave: str) -> None:
        if (ARTE / "logo_brasileirao.png").exists():
            self.imagem("logo", "logo_brasileirao.png", 30, 14, 108, 108)
            self.imagem("titulo", f"titulo_texto_{chave}.png", 150, 18, 700, 100)
        else:
            self.imagem("titulo", f"titulo_{chave}.png", 28, 18, 760, 100)
        self.navegador()

    def navegador(self) -> None:
        """Botões das três páginas (navegador nativo), a página aberta em limão."""
        estado = lambda id_, **kw: {"properties": kw, "selector": {"id": id_}}  # noqa: E731
        self.add("navegador", 1240, 40, 640, 64, {
            "visualType": "pageNavigator",
            "objects": {
                "fill": [estado("default", show=L("true"), fillColor=cor(PAINEL2), transparency=num(0)),
                         estado("hover", show=L("true"), fillColor=cor(BORDA), transparency=num(0)),
                         estado("selected", show=L("true"), fillColor=cor(LIMAO), transparency=num(0))],
                "text": [estado("default", fontColor=cor(BRANCO), fontSize=num(15), bold=L("true")),
                         estado("hover", fontColor=cor(BRANCO), fontSize=num(15), bold=L("true")),
                         estado("selected", fontColor=cor(NAVY), fontSize=num(15), bold=L("true"))],
                "outline": [estado("default", show=L("true"), lineColor=cor(BORDA), weight=num(1),
                                   roundEdge=num(12)),
                            estado("selected", lineColor=cor(LIMAO))],
            }}, cabecalho(None, fundo=False))

    def kpis(self, cartoes: list) -> None:
        w, gap, x0, y = 294, 15, 40, 134
        for i, (medida, rotulo, icone, c, tamanho) in enumerate(cartoes):
            x = x0 + i * (w + gap)
            self.cartao(f"kpi_{i}", medida, rotulo, x, y, w, 140, c)
            self.visuais[-1]["visual"]["objects"]["labels"][0]["properties"]["fontSize"] = num(tamanho)
            self.imagem(f"kpi_icone_{i}", icone, x + 12, y + 12, 44, 44)


def pagina_chances() -> Pagina:
    pg = Pagina(uuid.uuid5(NS, "pagina/chances").hex[:20], "Chances")
    pg.cabecalho_pagina("chances")
    pg.kpis([
        ("Jogos disputados", "Jogos disputados", "icone_jogos.png", BRANCO, 40),
        ("Jogos restantes", "Jogos que faltam", "icone_restantes.png", BRANCO, 40),
        ("Simulações", "Simulações do fim", "icone_simulacoes.png", BRANCO, 40),
        ("Favorito ao título", "Favorito ao título", "icone_titulo.png", LIMAO, 30),
        ("Chance do favorito", "Chance de título do favorito", "icone_chance.png", LIMAO, 40),
        ("Times em risco de queda", "Em risco de queda (1%+)", "icone_queda.png", QUEDA, 40),
    ])

    zonas = [r for r, _, _ in ZONAS]
    rotulo_zona = {"Sul-Americana": "Sul-Am."}
    pg.add("classificacao", 40, 290, 1180, 748, {
        "visualType": "tableEx",
        "query": {
            "queryState": {"Values": {"projections": [
                proj_coluna("times", "escudo", " "),
                proj_coluna("times", "ordem_prevista", "#"),
                proj_coluna("times", "time", "Time"),
                proj_medida("Pontos esperados", "Pts no fim"),
                proj_medida("Faixa de 90%", "Faixa 90%"),
                proj_medida("Texto hoje", "Hoje"),
                proj_medida("Pontos", "Pts hoje"),
                proj_medida("Jogos do time", "J"),
                *[proj_medida(f"Texto {z}", rotulo_zona.get(z, z)) for z in zonas],
            ]}},
            "sortDefinition": {"sort": [{"field": coluna_ref("times", "ordem_prevista"), "direction": "Ascending"}]},
        },
        "objects": {
            **ESTILO_TABELA,
            "values": [VALORES_TABELA,
                       {"properties": {"fontColor": cor_medida("Letra hoje")},
                        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                     "metadata": "_Medidas.Texto hoje"}}]
                      + [x for z in zonas for x in com_cor(f"Texto {z}", f"Fundo {z}", f"Letra {z}")],
            "grid": props(gridHorizontal=L("true"), gridHorizontalColor=cor(BORDA), rowPadding=num(1),
                          imageHeight=num(20)),
            "columnWidth": [largura("times.escudo", 40), largura("times.ordem_prevista", 44),
                            largura("times.time", 160), largura("_Medidas.Pontos esperados", 106),
                            largura("_Medidas.Faixa de 90%", 98), largura("_Medidas.Texto hoje", 86),
                            largura("_Medidas.Pontos", 90), largura("_Medidas.Jogos do time", 44)]
                           + [largura(f"_Medidas.Texto {z}", 92) for z in zonas],
            "columnFormatting": [centro(f"_Medidas.Texto {z}") for z in zonas]
                                + [centro(r) for r in ("times.ordem_prevista", "_Medidas.Pontos", "_Medidas.Jogos do time",
                                                       "_Medidas.Pontos esperados", "_Medidas.Faixa de 90%",
                                                       "_Medidas.Texto hoje")],
        }}, cabecalho("Tabela final prevista",
                      "#: ordem dos pontos no fim (média das simulações) · Hoje: posição atual, ▲ sobe e ▼ desce até o fim"))

    pg.add("faixa_pontos", 1236, 290, 644, 748, {
        "visualType": "barChart",
        "query": {
            "queryState": {
                "Category": {"projections": [proj_coluna("times", "time", "Time")]},
                "Y": {"projections": [proj_medida("Barra pontos atuais", "Pontos atuais"),
                                      proj_medida("Barra vão", "Até a faixa"),
                                      proj_medida("Barra até o esperado", "Faixa até o esperado"),
                                      proj_medida("Barra acima do esperado", "Esperado até o fim da faixa")]},
            },
            "sortDefinition": {"sort": [{"field": coluna_ref("times", "time"), "direction": "Ascending"}],
                               "isDefaultSort": True},
        },
        "objects": {
            **eixos(),
            "categoryAxis": props(labelColor=cor(BRANCO), fontSize=num(14), showAxisTitle=L("false"),
                                  gridlineShow=L("false"), innerPadding=L("28L")),
            "valueAxis": props(show=L("true"), labelColor=cor(LAVANDA), fontSize=num(14), showAxisTitle=L("false"),
                               gridlineShow=L("false")),
            "dataPoint": [
                {"properties": {"fill": cor(BORDA)}, "selector": {"metadata": "_Medidas.Barra pontos atuais"}},
                # o vão tem a cor do painel: some no fundo
                {"properties": {"fill": cor(PAINEL)}, "selector": {"metadata": "_Medidas.Barra vão"}},
                {"properties": {"fill": cor(VIOLETA)}, "selector": {"metadata": "_Medidas.Barra até o esperado"}},
                {"properties": {"fill": cor(LIMAO)}, "selector": {"metadata": "_Medidas.Barra acima do esperado"}},
            ],
            "labels": props(show=L("false")),
        }}, cabecalho("Onde cada time pode chegar",
                      "Escuro: pontos hoje · violeta e limão: faixa de 90%"))
    return pg


def pagina_posicoes() -> Pagina:
    pg = Pagina(uuid.uuid5(NS, "pagina/posicoes").hex[:20], "Posição final")
    pg.cabecalho_pagina("posicoes")
    pg.add("mapa_posicoes", 40, 134, 1840, 904, {
        "visualType": "pivotTable",
        "query": {
            "queryState": {
                "Rows": {"projections": [proj_coluna("times", "time", "Time")]},
                "Columns": {"projections": [proj_coluna("posicoes", "posicao_rotulo", "Posição")]},
                "Values": {"projections": [proj_medida("Texto da posição", "Chance")]},
            },
            "sortDefinition": {"sort": [{"field": coluna_ref("times", "time"), "direction": "Ascending"}],
                               "isDefaultSort": True},
        },
        "objects": {
            "columnHeaders": props(fontColor=cor(LIMAO), backColor=cor(PAINEL2), fontSize=num(15), bold=L("true"),
                                   alignment=txt("Center")),
            "rowHeaders": props(fontColor=cor(BRANCO), backColor=cor(PAINEL), fontSize=num(15)),
            "values": [{"properties": {"fontColorPrimary": cor(BRANCO), "backColorPrimary": cor(PAINEL),
                                       "fontColorSecondary": cor(BRANCO), "backColorSecondary": cor(PAINEL),
                                       "fontSize": num(14)}},
                       *com_cor("Texto da posição", "Fundo da posição", "Letra da posição")],
            "subTotals": props(rowSubtotals=L("false"), columnSubtotals=L("false")),
            "grid": props(gridHorizontal=L("true"), gridHorizontalColor=cor(NAVY), gridVertical=L("true"),
                          gridVerticalColor=cor(NAVY), rowPadding=num(4)),
            "columnWidth": [largura("times.time", 190), largura("_Medidas.Texto da posição", 80)],
            "columnFormatting": [centro("_Medidas.Texto da posição")],
        }}, cabecalho("Em que posição cada time termina",
                      "Chance em cada posição, em 100 mil simulações · limão: título e Libertadores (G6) · "
                      "violeta: Sul-Americana · lavanda: meio da tabela · coral: rebaixamento"))
    return pg


def pagina_jogos() -> Pagina:
    pg = Pagina(uuid.uuid5(NS, "pagina/jogos").hex[:20], "Jogos e teste")
    pg.cabecalho_pagina("jogos")
    pg.segmentacao("filtro_time", "times", "time", "TIME", "Dropdown", 40, 134, 400, 92)

    probs = ["Mandante vence", "Empate", "Visitante vence"]
    pg.add("jogos", 40, 242, 1100, 796, {
        "visualType": "tableEx",
        "query": {
            "queryState": {"Values": {"projections": [
                proj_coluna("jogos", "quando", "Data"),
                proj_coluna("jogos", "rodada", "Rodada"),
                proj_coluna("jogos", "mandante", "Mandante"),
                proj_coluna("jogos", "visitante", "Visitante"),
                *[proj_medida(p) for p in probs],
                proj_coluna("jogos", "placar_mais_provavel", "Placar mais provável"),
            ]}},
            "sortDefinition": {"sort": [{"field": coluna_ref("jogos", "quando"), "direction": "Ascending"}]},
        },
        "objects": {
            **ESTILO_TABELA,
            "values": [VALORES_TABELA] + [x for p in probs for x in com_cor(p, f"Fundo {p}", f"Letra {p}")],
            "grid": props(gridHorizontal=L("true"), gridHorizontalColor=cor(BORDA), rowPadding=num(3)),
            "columnWidth": [largura("jogos.quando", 100), largura("jogos.rodada", 80), largura("jogos.mandante", 160),
                            largura("jogos.visitante", 160)] + [largura(f"_Medidas.{p}", 130) for p in probs]
                           + [largura("jogos.placar_mais_provavel", 150)],
            "columnFormatting": [centro(f"_Medidas.{p}") for p in probs]
                                + [centro(r) for r in ("jogos.quando", "jogos.rodada", "jogos.placar_mais_provavel")],
        }}, titulo_medida("Título dos jogos",
                          "Probabilidades do modelo para cada jogo · o placar mais provável é só o mais comum"))

    def teste(chave, y, h, medida, casas, titulo, subtitulo_medida) -> None:
        pg.add(chave, 1156, y, 724, h, {
            "visualType": "clusteredBarChart",
            "query": {
                "queryState": {
                    "Category": {"projections": [proj_coluna("modelos", "rotulo", "Modelo")]},
                    "Y": {"projections": [proj_medida(medida)]},
                },
                "sortDefinition": {"sort": [{"field": coluna_ref("modelos", "rotulo"), "direction": "Ascending"}],
                                   "isDefaultSort": True},
            },
            "objects": {
                **eixos(rotulo_valor=False),
                "categoryAxis": props(labelColor=cor(BRANCO), fontSize=num(16), showAxisTitle=L("false"),
                                      gridlineShow=L("false"), innerPadding=L("24L")),
                "valueAxis": props(show=L("false"), gridlineShow=L("false"), start=num(0)),
                "dataPoint": [{"properties": {"fill": cor_medida("Cor do modelo")},
                               "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                "labels": props(show=L("true"), color=cor(BRANCO), fontSize=num(20), labelDisplayUnits=num(1),
                                labelPrecision=L(casas), labelPosition=txt("OutsideEnd")),
            }}, {**cabecalho(titulo, "x"), "subTitle": props(show=L("true"), text={"expr": medida_ref(subtitulo_medida)},
                                                           fontColor=cor(TEXTO), fontSize=num(15))})

    teste("teste_rps", 134, 440, "RPS", "3L", "Teste em 2026: erro jogo a jogo (RPS)", "Subtítulo do RPS")
    teste("teste_replay", 590, 448, "Erro de pontos", "1L",
          "Teste em 2026: erro nos pontos finais", "Subtítulo do replay")
    return pg


def gerar_relatorio() -> None:
    if RELATORIO.exists():
        shutil.rmtree(RELATORIO / "definition", ignore_errors=True)
        shutil.rmtree(RELATORIO / "StaticResources", ignore_errors=True)
    d = RELATORIO / "definition"
    rr = RELATORIO / "StaticResources" / "RegisteredResources"
    br = RELATORIO / "StaticResources" / "SharedResources" / "BaseThemes"
    for p in (d / "pages", rr, br):
        p.mkdir(parents=True, exist_ok=True)

    shutil.copy(PASTA.parent / "powerbi" / "recursos" / "Fluent2-CY26SU09.json", br / "Fluent2-CY26SU09.json")
    tema = {**molde.tema(), "name": "Previsao2026"}
    (rr / "tema-previsao.json").write_text(json.dumps(tema, ensure_ascii=False, indent=2), encoding="utf-8")
    imagens = sorted(p.name for p in ARTE.glob("*.png"))
    for nome in imagens:
        shutil.copy(ARTE / nome, rr / nome)

    (RELATORIO / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}}, indent=2),
        encoding="utf-8")
    (d / "version.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"}, indent=2), encoding="utf-8")
    versao = {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}
    (d / "report.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "Fluent2-CY26SU09", "reportVersionAtImport": versao, "type": "SharedResources"},
            "customTheme": {"name": "tema-previsao.json", "reportVersionAtImport": versao,
                            "type": "RegisteredResources"}},
        "objects": {"outspacePane": [{"properties": {"expanded": L("false")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "Fluent2-CY26SU09", "path": "BaseThemes/Fluent2-CY26SU09.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "tema-previsao.json", "path": "tema-previsao.json", "type": "CustomTheme"}]
             + [{"name": n, "path": n, "type": "Image"} for n in imagens]},
        ],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    paginas = [pagina_chances(), pagina_posicoes(), pagina_jogos()]
    for pg in paginas:
        pd = d / "pages" / pg.nome
        (pd / "visuals").mkdir(parents=True)
        (pd / "page.json").write_text(json.dumps(pg.json_pagina(), ensure_ascii=False, indent=2), encoding="utf-8")
        for v in pg.visuais:
            (pd / "visuals" / v["name"]).mkdir()
            (pd / "visuals" / v["name"] / "visual.json").write_text(
                json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [pg.nome for pg in paginas], "activePageName": paginas[0].nome}, indent=2), encoding="utf-8")


def main() -> None:
    (PASTA / f"{NOME}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NOME}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    gerar_modelo()
    gerar_relatorio()
    print(f"PBIP gerado em {PASTA / (NOME + '.pbip')}")


if __name__ == "__main__":
    main()
