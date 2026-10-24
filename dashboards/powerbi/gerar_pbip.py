"""Gera o projeto Power BI (PBIP: modelo em TMDL e relatório em PBIR).

Uma página, 1920 x 1080, sobre os CSVs de dashboards/powerbi/dados (gerados
por exportar_dados.py). Visuais nativos, tema navy/limão/violeta e a arte de
arte/png (fundo, título, adesivo, ícones).

Regras:
- Nenhum número do painel é digitado aqui: tudo sai de medida DAX.
- lineageTag e nomes de visual estáveis (uuid5), para o Desktop não perder nada
  ao regerar.

Uso: python dashboards/powerbi/gerar_pbip.py
     Depois, no Desktop: abrir Brasileirao.pbip (ou "Aplicar alterações externas").
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NOME = "Brasileirao"
MODELO = PASTA / f"{NOME}.SemanticModel"
RELATORIO = PASTA / f"{NOME}.Report"
ARTE = PASTA / "arte" / "png"
NS = uuid.UUID("6b1d7c3e-1f2a-4b8e-9c55-2027b0a5e001")

# Paleta (inspirada na transmissão do campeonato)
NAVY, PAINEL, PAINEL2, BORDA = "#0B0D26", "#14173A", "#1C2050", "#2A2E66"
LIMAO, VIOLETA, LAVANDA, BRANCO = "#C6F500", "#5D4DFF", "#8A8FB8", "#FFFFFF"
TEXTO, QUEDA, ALTA = "#D5D8F0", "#FF5C7A", "#2EE06E"


def tag(*partes: str) -> str:
    return str(uuid.uuid5(NS, "/".join(partes)))


def nome_visual(chave: str) -> str:
    return uuid.uuid5(NS, "visual/" + chave).hex[:20]


# ---------------------------------------------------------------------------
# Modelo (TMDL)
# ---------------------------------------------------------------------------
COLUNAS_JOGOS = [
    # nome, tipo TMDL, tipo M, formato, ordenar por
    ("jogo_id", "string", "type text", None, None),
    ("temporada", "int64", "Int64.Type", "0", None),
    ("rodada", "int64", "Int64.Type", "0", None),
    ("data", "dateTime", "type date", "dd/mm/yyyy", None),
    ("periodo", "string", "type text", None, None),
    ("periodo_painel", "string", "type text", None, "periodo_painel_ordem"),
    ("periodo_painel_ordem", "int64", "Int64.Type", "0", None),
    ("bloco", "string", "type text", None, "bloco_ordem"),
    ("bloco_ordem", "int64", "Int64.Type", "0", None),
    ("bloco_tipo", "string", "type text", None, None),
    ("resultado_jogo", "string", "type text", None, "resultado_ordem"),
    ("resultado_ordem", "int64", "Int64.Type", "0", None),
    ("time_id", "string", "type text", None, None),
    ("adversario_id", "string", "type text", None, None),
    ("lado", "string", "type text", None, None),
    ("gols_pro", "int64", "Int64.Type", "0", None),
    ("gols_contra", "int64", "Int64.Type", "0", None),
    ("pontos", "int64", "Int64.Type", "0", None),
]
COLUNAS_TIMES = [
    ("time_id", "string", "type text", None, None),
    ("nome", "string", "type text", None, None),
    ("uf", "string", "type text", None, None),
    ("primeira_temporada", "int64", "Int64.Type", "0", None),
    ("ultima_temporada", "int64", "Int64.Type", "0", None),
    ("temporadas_na_serie_a", "int64", "Int64.Type", "0", None),
    ("escudo", "string", "type text", None, None),
]
COLUNAS_JOGOS_B = [
    ("jogo_id", "string", "type text", None, None),
    ("temporada", "int64", "Int64.Type", "0", None),
    ("data", "dateTime", "type date", "dd/mm/yyyy", None),
    ("time_id", "string", "type text", None, None),
    ("adversario_id", "string", "type text", None, None),
    ("lado", "string", "type text", None, None),
    ("gols_pro", "int64", "Int64.Type", "0", None),
    ("gols_contra", "int64", "Int64.Type", "0", None),
    ("pontos", "int64", "Int64.Type", "0", None),
]
# Colunas e medidas que o Power BI deve desenhar como imagem
IMAGENS = {"escudo"}

# Filtros que as medidas de período removem (o slicer de temporada e o eixo
# do gráfico por temporada), mantendo o filtro de time.
SEM_TEMPORADA = ("REMOVEFILTERS ( jogos_time[temporada] ), REMOVEFILTERS ( jogos_time[bloco] ), "
                 "REMOVEFILTERS ( jogos_time[bloco_ordem] )")
SEM_PERIODO = ("REMOVEFILTERS ( jogos_time[periodo_painel] ), "
               "REMOVEFILTERS ( jogos_time[periodo_painel_ordem] )")

MEDIDAS = [
    # nome, DAX, formato, pasta, descrição
    ("Jogos", "DISTINCTCOUNT ( jogos_time[jogo_id] )", "#,0", "KPI", "Jogos distintos no filtro."),
    ("Gols por jogo", "AVERAGEX ( jogos_time, jogos_time[gols_pro] + jogos_time[gols_contra] )",
     "0.00", "KPI", "Média de gols por jogo (as duas linhas do jogo têm o mesmo total)."),
    ("Vitórias do mandante",
     'DIVIDE ( CALCULATE ( COUNTROWS ( jogos_time ), jogos_time[lado] = "Casa", jogos_time[pontos] = 3 ), '
     'CALCULATE ( COUNTROWS ( jogos_time ), jogos_time[lado] = "Casa" ) )',
     "0.0%", "KPI", "Vitórias em casa sobre jogos em casa."),
    ("Pontos por jogo em casa", 'CALCULATE ( AVERAGE ( jogos_time[pontos] ), jogos_time[lado] = "Casa" )',
     "0.00", "KPI", "Média de pontos por jogo como mandante."),
    ("Pontos por jogo fora", 'CALCULATE ( AVERAGE ( jogos_time[pontos] ), jogos_time[lado] = "Fora" )',
     "0.00", "KPI", "Média de pontos por jogo como visitante."),
    ("Vantagem do mandante", "[Pontos por jogo em casa] - [Pontos por jogo fora]",
     "0.00", "Mando", "Pontos por jogo em casa menos fora. Sem filtro de time, é a média de "
     "(pontos do mandante - pontos do visitante) por jogo."),
    ("Vantagem com torcida 2015-2019",
     f'CALCULATE ( [Vantagem do mandante], {SEM_TEMPORADA}, {SEM_PERIODO}, '
     'jogos_time[periodo_painel] = "Com torcida 2015-2019" )',
     "0.00", "Mando", "Referência: mesma época, com público. Ignora o filtro de temporada."),
    ("Vantagem sem torcida",
     f'CALCULATE ( [Vantagem do mandante], {SEM_TEMPORADA}, {SEM_PERIODO}, '
     'jogos_time[periodo_painel] = "Sem torcida 2020-2021" )',
     "0.00", "Mando", "Ago/2020 a set/2021. Ignora o filtro de temporada."),
    ("Mando sem torcida", "DIVIDE ( [Vantagem sem torcida], [Vantagem com torcida 2015-2019] ) - 1",
     "+0%;-0%;0%", "KPI", "Variação da vantagem do mandante sem torcida contra 2015 a 2019."),
    ("Vantagem por período",
     f"IF ( ISBLANK ( SELECTEDVALUE ( jogos_time[periodo_painel] ) ), BLANK (), "
     f"CALCULATE ( [Vantagem do mandante], {SEM_TEMPORADA} ) )",
     "0.00", "Mando", "Vantagem em cada período do painel; em branco fora dos três períodos."),
    ("Jogos em casa por período",
     f'IF ( ISBLANK ( SELECTEDVALUE ( jogos_time[periodo_painel] ) ), BLANK (), '
     f'CALCULATE ( COUNTROWS ( jogos_time ), jogos_time[lado] = "Casa", {SEM_TEMPORADA} ) )',
     "#,0", "Mando", "Base do gráfico de resultados (uma linha por jogo, a do mandante)."),
    ("Média com torcida 2015-2019",
     "IF ( ISBLANK ( [Vantagem do mandante] ), BLANK (), [Vantagem com torcida 2015-2019] )",
     "0.00", "Mando", "Linha de referência no gráfico por temporada."),
    ("Casa menos fora 2015-2019",
     "VAR a = [Vantagem com torcida 2015-2019] VAR s = [Vantagem sem torcida] "
     "RETURN IF ( ISBLANK ( a ) || ISBLANK ( s ), BLANK (), a )",
     "0.00", "Times", "Só para times que jogaram nos dois períodos (21 na base)."),
    ("Casa menos fora sem torcida",
     "VAR a = [Vantagem com torcida 2015-2019] VAR s = [Vantagem sem torcida] "
     "RETURN IF ( ISBLANK ( a ) || ISBLANK ( s ), BLANK (), s )",
     "0.00", "Times", "Só para times que jogaram nos dois períodos."),
    ("Variação sem torcida",
     "VAR a = [Vantagem com torcida 2015-2019] VAR s = [Vantagem sem torcida] "
     "RETURN IF ( ISBLANK ( a ) || ISBLANK ( s ), BLANK (), s - a )",
     "+0.00;-0.00;0.00", "Times", "Sem torcida menos 2015 a 2019, para o mesmo time."),
    ("Times que caíram",
     "COUNTROWS ( FILTER ( VALUES ( times[time_id] ), [Variação sem torcida] < 0 ) )",
     "0", "Times", "Times com vantagem menor sem torcida (conferência: 17 de 21)."),
    ("Times comparados",
     "COUNTROWS ( FILTER ( VALUES ( times[time_id] ), NOT ISBLANK ( [Variação sem torcida] ) ) )",
     "0", "Times", "Times que jogaram nos dois períodos."),
    ("Vantagem sem torcida Série B",
     'CALCULATE ( AVERAGE ( jogos_time_b[pontos] ), jogos_time_b[lado] = "Casa" ) '
     '- CALCULATE ( AVERAGE ( jogos_time_b[pontos] ), jogos_time_b[lado] = "Fora" )',
     "0.00", "Times", "Só os tradicionais que jogaram a Série B sem torcida."),
    ("Variação na tabela",
     "VAR a = [Vantagem com torcida 2015-2019] VAR sa = [Vantagem sem torcida] "
     "VAR sb = [Vantagem sem torcida Série B] VAR s = IF ( ISBLANK ( sa ), sb, sa ) "
     "RETURN IF ( ISBLANK ( a ) || ISBLANK ( s ), BLANK (), s - a )",
     "+0.00;-0.00;0.00", "Times",
     "Como Variação sem torcida, mas os tradicionais da Série B usam a B sem torcida. O -45% e o 0,44 não usam esta."),
    ("Times que caíram na tabela",
     "COUNTROWS ( FILTER ( VALUES ( times[time_id] ), [Variação na tabela] < 0 ) )",
     "0", "Times", "Como Times que caíram, contando também os tradicionais da Série B (conferência: 20 de 25)."),
    ("Times na tabela",
     "COUNTROWS ( FILTER ( VALUES ( times[time_id] ), NOT ISBLANK ( [Variação na tabela] ) ) )",
     "0", "Times", "Linhas da tabela por time: 21 da Série A e 4 tradicionais da Série B."),
    ("Barra da variação", "[Variação na tabela]", "+0.00;-0.00;0.00", "Times",
     "Mesma variação, só para desenhar a barra de dados (sem texto) ao lado do número."),
    ("Título dos times",
     'FORMAT ( [Times que caíram na tabela], "0" ) & " de " & FORMAT ( [Times na tabela], "0" ) '
     '& " times perderam força em casa"',
     None, "Times", "Título do gráfico por time, montado com as medidas (nenhum número digitado)."),
    ("Cor da temporada",
     f'SWITCH ( SELECTEDVALUE ( jogos_time[bloco_tipo] ), "sem", "{LIMAO}", "volta", "{LAVANDA}", "{VIOLETA}" )',
     None, "Cores", "Limão sem torcida, lavanda na volta parcial, violeta com torcida."),
    ("Cor do período",
     f'IF ( SELECTEDVALUE ( jogos_time[periodo_painel_ordem] ) = 2, "{LIMAO}", "{VIOLETA}" )',
     None, "Cores", "Limão no período sem torcida."),
    ("Cor da variação", f'IF ( [Variação na tabela] < 0, "{QUEDA}", "{ALTA}" )',
     None, "Cores", "Vermelho quando o time perdeu força em casa."),
]


def tmdl_coluna(tabela: str, nome: str, tipo: str, fmt: str | None, ordem: str | None) -> str:
    linhas = [f"\tcolumn {nome}", f"\t\tdataType: {tipo}"]
    if fmt:
        linhas.append(f"\t\tformatString: {fmt}")
    linhas += [f"\t\tlineageTag: {tag('coluna', tabela, nome)}", "\t\tsummarizeBy: none",
               f"\t\tsourceColumn: {nome}"]
    if ordem:
        linhas.append(f"\t\tsortByColumn: {ordem}")
    if nome in IMAGENS:
        linhas.append("\t\tdataCategory: ImageUrl")
    if tipo == "dateTime":
        linhas += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
    linhas += ["", "\t\tannotation SummarizationSetBy = User", ""]
    return "\n".join(linhas)


def tmdl_tabela_csv(tabela: str, arquivo: str, colunas: list, nulos: list[str], doc: str) -> str:
    tipos = ", ".join(f'{{"{c}", {m}}}' for c, _, m, _, _ in colunas)
    nulos_m = ", ".join(f'"{c}"' for c in nulos)
    passo_nulos = (f'\t\t\t\t    Nulos = Table.ReplaceValue(Cabecalho, "", null, Replacer.ReplaceValue, {{{nulos_m}}}),\n'
                   if nulos else "\t\t\t\t    Nulos = Cabecalho,\n")
    corpo = "\n".join(tmdl_coluna(tabela, c, t, f, o) for c, t, _, f, o in colunas)
    return f"""/// {doc}
table {tabela}
\tlineageTag: {tag('tabela', tabela)}

{corpo}
\tpartition {tabela} = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t    Fonte = Csv.Document(File.Contents(PastaDados & "{arquivo}"), [Delimiter = ",", Columns = {len(colunas)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
\t\t\t\t    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
{passo_nulos}\t\t\t\t    Tipos = Table.TransformColumnTypes(Nulos, {{{tipos}}}, "en-US")
\t\t\t\tin
\t\t\t\t    Tipos

\tannotation PBI_ResultType = Table
"""


def tmdl_medidas() -> str:
    blocos = []
    for nome, dax, fmt, pasta, doc in MEDIDAS:
        n = f"'{nome}'" if not nome.isidentifier() else nome
        linhas = [f"\t/// {doc}", f"\tmeasure {n} = {dax}"]
        if fmt:
            linhas.append(f"\t\tformatString: {fmt}")
        if nome in IMAGENS:
            linhas.append("\t\tdataCategory: ImageUrl")
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
    (d / "model.tmdl").write_text(f"""model Model
\tculture: pt-BR
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: pt-BR
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0

annotation PBI_ProTooling = ["DevMode"]

annotation PBI_QueryOrder = ["PastaDados","jogos_time","times","jogos_time_b"]

ref table jogos_time
ref table times
ref table jogos_time_b
ref table _Medidas
""", encoding="utf-8")
    pasta_dados = str(PASTA / "dados") + "\\"
    (d / "expressions.tmdl").write_text(
        f'/// Pasta dos CSVs gerados por exportar_dados.py (caminho desta máquina).\n'
        f'expression PastaDados = "{pasta_dados}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag('expressao', 'PastaDados')}\n\n\tannotation PBI_ResultType = Text\n",
        encoding="utf-8")
    (d / "relationships.tmdl").write_text(
        f"relationship {tag('relacao', 'jogos_time', 'times')}\n"
        "\tfromColumn: jogos_time.time_id\n\ttoColumn: times.time_id\n\n"
        f"relationship {tag('relacao', 'jogos_time_b', 'times')}\n"
        "\tfromColumn: jogos_time_b.time_id\n\ttoColumn: times.time_id\n", encoding="utf-8")
    (d / "tables" / "jogos_time.tmdl").write_text(tmdl_tabela_csv(
        "jogos_time", "jogos_time.csv", COLUNAS_JOGOS, ["periodo_painel", "periodo_painel_ordem"],
        "Um time em um jogo: cada jogo tem duas linhas (Casa e Fora)."), encoding="utf-8")
    (d / "tables" / "times.tmdl").write_text(tmdl_tabela_csv(
        "times", "times.csv", COLUNAS_TIMES, [], "Clubes da Série A de 2003 a 2025."), encoding="utf-8")
    (d / "tables" / "jogos_time_b.tmdl").write_text(tmdl_tabela_csv(
        "jogos_time_b", "jogos_time_b.csv", COLUNAS_JOGOS_B, [],
        "Série B sem torcida dos clubes tradicionais (Cruzeiro, Vitória, Figueirense, Ponte Preta)."),
        encoding="utf-8")
    (d / "tables" / "_Medidas.tmdl").write_text(tmdl_medidas(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Relatório (PBIR)
# ---------------------------------------------------------------------------
def L(v) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def txt(s: str) -> dict:
    return L("'" + s.replace("'", "''") + "'")


def num(x: float) -> dict:
    return L(f"{x}D")


def cor(hexa: str) -> dict:
    return {"solid": {"color": txt(hexa)}}


def medida_ref(nome: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": nome}}


def coluna_ref(tabela: str, col: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabela}}, "Property": col}}


def cor_medida(nome: str) -> dict:
    return {"solid": {"color": {"expr": medida_ref(nome)}}}


def proj_medida(nome: str, rotulo: str | None = None) -> dict:
    p = {"field": medida_ref(nome), "queryRef": f"_Medidas.{nome}", "nativeQueryRef": nome}
    if rotulo:
        p["displayName"] = rotulo
    return p


def proj_coluna(tabela: str, col: str, rotulo: str | None = None) -> dict:
    p = {"field": coluna_ref(tabela, col), "queryRef": f"{tabela}.{col}", "nativeQueryRef": col}
    if rotulo:
        p["displayName"] = rotulo
    return p


def props(**kw) -> list:
    return [{"properties": kw}]


def cabecalho(titulo: str | None, subtitulo: str | None = None, fundo: bool = True) -> dict:
    o: dict = {}
    if titulo:
        o["title"] = props(show=L("true"), text=txt(titulo), fontColor=cor(BRANCO),
                           fontSize=num(22), bold=L("true"))
    else:
        o["title"] = props(show=L("false"))
    if subtitulo:
        o["subTitle"] = props(show=L("true"), text=txt(subtitulo), fontColor=cor(TEXTO), fontSize=num(15))
    if not fundo:
        o["background"] = props(show=L("false"))
        o["border"] = props(show=L("false"))
        o["dropShadow"] = props(show=L("false"))
        o["padding"] = props(left=num(0), top=num(0), right=num(0), bottom=num(0))
    return o


class Pagina:
    def __init__(self, nome: str, exibicao: str):
        self.nome, self.exibicao = nome, exibicao
        self.visuais: list[dict] = []
        self.z = 1000

    def add(self, chave: str, x, y, w, h, visual: dict, container: dict) -> None:
        self.z += 100
        self.visuais.append({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json",
            "name": nome_visual(chave),
            "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z},
            "visual": {**visual, "visualContainerObjects": container, "drillFilterOtherVisuals": True},
        })

    def imagem(self, chave: str, arquivo: str, x, y, w, h) -> None:
        self.add(chave, x, y, w, h, {
            "visualType": "image",
            "objects": {
                "general": props(imageUrl={"expr": {"ResourcePackageItem": {
                    "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": arquivo}}}),
                "imageScaling": props(imageScalingType=txt("Fit")),
            }}, cabecalho(None, fundo=False))

    def cartao(self, chave: str, medida: str, rotulo: str, x, y, w, h, cor_valor: str = BRANCO) -> None:
        self.add(chave, x, y, w, h, {
            "visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj_medida(medida, rotulo)]}}},
            "objects": {
                "labels": props(color=cor(cor_valor), fontSize=num(40), labelDisplayUnits=num(1)),
                "categoryLabels": props(show=L("true"), color=cor(TEXTO), fontSize=num(15)),
            }}, cabecalho(None))

    def segmentacao(self, chave: str, tabela: str, col: str, rotulo: str, modo: str, x, y, w, h) -> None:
        self.add(chave, x, y, w, h, {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj_coluna(tabela, col, rotulo)]}}},
            "objects": {
                "data": props(mode=txt(modo)),
                "header": props(show=L("true"), fontColor=cor(LIMAO), textSize=num(15), bold=L("true")),
                "items": props(fontColor=cor(BRANCO), background=cor(PAINEL2), textSize=num(16)),
                "numericInputStyle": props(fontColor=cor(BRANCO), background=cor(PAINEL2), textSize=num(16)),
                "slider": props(color=cor(LIMAO)),
            }}, cabecalho(None))

    def json_pagina(self) -> dict:
        return {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": self.nome, "displayName": self.exibicao, "displayOption": "FitToPage",
            "height": 1080, "width": 1920,
            "objects": {
                "background": props(
                    image={"image": {
                        "name": txt("fundo.png"),
                        "url": {"expr": {"ResourcePackageItem": {
                            "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": "fundo.png"}}},
                        "scaling": txt("Fill")}},
                    color=cor(NAVY), transparency=num(0)),
                "outspace": props(color=cor(NAVY)),
            },
        }


def eixos(rotulo_valor: bool = True) -> dict:
    return {
        "categoryAxis": props(labelColor=cor(TEXTO), fontSize=num(15), showAxisTitle=L("false"),
                              gridlineShow=L("false")),
        "valueAxis": props(show=L("true" if rotulo_valor else "false"), labelColor=cor(LAVANDA), fontSize=num(15),
                           showAxisTitle=L("false"), gridlineShow=L("true"), gridlineColor=cor(BORDA),
                           secShow=L("false")),
        "legend": props(show=L("false")),
    }


def pagina_principal() -> Pagina:
    pg = Pagina(uuid.uuid5(NS, "pagina/mando").hex[:20], "Mando de campo")

    # Cabeçalho: título em imagem e filtros
    if (ARTE / "logo_brasileirao.png").exists():
        pg.imagem("logo", "logo_brasileirao.png", 30, 14, 108, 108)
        pg.imagem("titulo", "titulo_texto.png", 150, 18, 700, 100)
    else:
        pg.imagem("titulo", "titulo.png", 28, 18, 760, 100)
    pg.segmentacao("filtro_temporada", "jogos_time", "temporada", "TEMPORADA", "Between", 1170, 26, 340, 92)
    pg.segmentacao("filtro_time", "times", "nome", "TIME", "Dropdown", 1530, 26, 350, 92)

    # Cartões de KPI com ícone (nomes curtos: o cartão é estreito)
    kpis = [
        ("Jogos", "Jogos", "icone_jogos.png", BRANCO),
        ("Gols por jogo", "Gols por jogo", "icone_gols.png", BRANCO),
        ("Vitórias do mandante", "Vitórias do mandante", "icone_vitorias.png", BRANCO),
        ("Pontos por jogo em casa", "Pontos/jogo em casa", "icone_casa.png", BRANCO),
        ("Pontos por jogo fora", "Pontos/jogo fora", "icone_fora.png", BRANCO),
        ("Mando sem torcida", "Mando sem torcida", "icone_sem_torcida.png", LIMAO),
    ]
    w, gap, x0, y = 294, 15, 40, 134
    for i, (medida, rotulo, icone, c) in enumerate(kpis):
        x = x0 + i * (w + gap)
        pg.cartao(f"kpi_{i}", medida, rotulo, x, y, w, 140, c)
        pg.imagem(f"kpi_icone_{i}", icone, x + 12, y + 12, 44, 44)

    # Linha 2: por temporada (combo) e os três períodos
    pg.add("por_temporada", 40, 290, 1200, 370, {
        "visualType": "lineClusteredColumnComboChart",
        "query": {
            "queryState": {
                "Category": {"projections": [proj_coluna("jogos_time", "bloco", "Temporada")]},
                "Y": {"projections": [proj_medida("Vantagem do mandante")]},
                "Y2": {"projections": [proj_medida("Média com torcida 2015-2019")]},
            },
            "sortDefinition": {"sort": [{"field": coluna_ref("jogos_time", "bloco"), "direction": "Ascending"}],
                               "isDefaultSort": True},
        },
        "objects": {
            **eixos(),
            "valueAxis": props(show=L("false"), gridlineShow=L("false"), secShow=L("false")),
            "dataPoint": [
                # cor por medida: limão nos jogos sem torcida (sem "metadata", que o Desktop ignorou aqui)
                {"properties": {"fill": cor_medida("Cor da temporada")},
                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}},
                {"properties": {"fill": cor(BRANCO)},
                 "selector": {"metadata": "_Medidas.Média com torcida 2015-2019"}},
            ],
            "labels": [
                {"properties": {"show": L("true"), "color": cor(BRANCO), "fontSize": num(13),
                                "labelDisplayUnits": num(1), "labelPrecision": L("2L"),
                                "labelPosition": txt("OutsideEnd")}},
                {"properties": {"show": L("false")},
                 "selector": {"metadata": "_Medidas.Média com torcida 2015-2019"}},
            ],
            "lineStyles": props(strokeWidth=num(2), lineStyle=txt("dashed"), showMarker=L("false")),
        }}, cabecalho("Vantagem do mandante por temporada",
                      "Pontos por jogo em casa menos fora · em limão, os jogos sem torcida · tracejado: média 2015-2019"))

    pg.add("periodos", 40, 676, 592, 362, {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [proj_coluna("jogos_time", "periodo_painel", "Período")]},
                "Y": {"projections": [proj_medida("Vantagem por período", "Vantagem do mandante")]},
            },
            "sortDefinition": {"sort": [{"field": coluna_ref("jogos_time", "periodo_painel"), "direction": "Ascending"}],
                               "isDefaultSort": True},
        },
        "objects": {
            **eixos(rotulo_valor=False),
            "categoryAxis": props(labelColor=cor(BRANCO), fontSize=num(18), showAxisTitle=L("false"),
                                  gridlineShow=L("false"), innerPadding=L("20L")),
            "dataPoint": [{"properties": {"fill": cor_medida("Cor do período")},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
            "labels": props(show=L("true"), color=cor(BRANCO), fontSize=num(28), labelDisplayUnits=num(1),
                            labelPrecision=L("2L"), labelPosition=txt("OutsideEnd")),
        }}, cabecalho("Com torcida x sem torcida", "Pontos por jogo em casa menos fora, por período"))
    pg.imagem("adesivo", "adesivo_sem_torcida.png", 842, 388, 130, 56)  # legenda das colunas limão (2020 e 2021)

    # Coluna da direita: cada time contra ele mesmo, uma linha por time (escudo, nome, número e barra)
    titulo_times = {"expr": medida_ref("Título dos times")}
    largura = lambda ref, px: {"properties": {"value": num(px)}, "selector": {"metadata": ref}}  # noqa: E731
    pg.add("times", 1256, 290, 624, 748, {
        "visualType": "tableEx",
        "query": {
            "queryState": {"Values": {"projections": [
                proj_coluna("times", "escudo", " "),
                proj_coluna("times", "nome", "Time"),
                proj_medida("Variação na tabela", "Variação"),
                proj_medida("Barra da variação", "caiu  ◀ │ ▶  subiu"),
            ]}},
            "sortDefinition": {"sort": [{"field": medida_ref("Variação na tabela"), "direction": "Ascending"}]},
        },
        "objects": {
            "columnHeaders": props(fontColor=cor(LIMAO), backColor=cor(PAINEL2), fontSize=num(14), bold=L("true")),
            "values": [
                {"properties": {"fontColorPrimary": cor(BRANCO), "backColorPrimary": cor(PAINEL),
                                "fontColorSecondary": cor(BRANCO), "backColorSecondary": cor("#181C45"),
                                "fontSize": num(13)}},
                {"properties": {"fontColor": cor_medida("Cor da variação")},
                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                              "metadata": "_Medidas.Variação na tabela"}},
            ],
            "total": props(totals=L("false")),
            "grid": props(gridHorizontal=L("true"), gridHorizontalColor=cor(BORDA), rowPadding=num(0),
                          imageHeight=num(19)),
            "columnWidth": [largura("times.escudo", 36), largura("times.nome", 170),
                            largura("_Medidas.Variação na tabela", 90),
                            largura("_Medidas.Barra da variação", 240)],
            # Barra de dados nativa: zero no meio, vermelho à esquerda (caiu), verde à direita (subiu)
            "columnFormatting": [{
                "properties": {"dataBars": {
                    "positiveColor": cor(ALTA), "negativeColor": cor(QUEDA), "axisColor": cor(BRANCO),
                    "reverseDirection": L("false"), "hideText": L("true"), "totalMatchingOption": L("1L")}},
                "selector": {"metadata": "_Medidas.Barra da variação"}}],
        }}, {**cabecalho("x", "Clubes que jogaram com e sem torcida · sem torcida x 2015-2019"),
             "title": props(show=L("true"), text=titulo_times, fontColor=cor(BRANCO), fontSize=num(22),
                            bold=L("true"), titleWrap=L("true"))})

    serie = lambda valor, hexa: {  # noqa: E731
        "properties": {"fill": cor(hexa)},
        "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0,
                                                          "Left": coluna_ref("jogos_time", "resultado_jogo"),
                                                          "Right": {"Literal": {"Value": f"'{valor}'"}}}}}]}}
    # De pé: colunas largas deixam os percentuais grandes dentro de cada pedaço
    pg.add("resultados", 648, 676, 592, 362, {
        "visualType": "hundredPercentStackedColumnChart",
        "query": {
            "queryState": {
                "Category": {"projections": [proj_coluna("jogos_time", "periodo_painel", "Período")]},
                "Series": {"projections": [proj_coluna("jogos_time", "resultado_jogo", "Resultado")]},
                "Y": {"projections": [proj_medida("Jogos em casa por período", "Jogos")]},
            },
            "sortDefinition": {"sort": [{"field": coluna_ref("jogos_time", "periodo_painel"), "direction": "Ascending"}],
                               "isDefaultSort": True},
        },
        "objects": {
            **eixos(rotulo_valor=False),
            "categoryAxis": props(labelColor=cor(BRANCO), fontSize=num(15), showAxisTitle=L("false"),
                                  gridlineShow=L("false"), innerPadding=L("12L")),
            "valueAxis": props(show=L("false"), gridlineShow=L("false")),
            "legend": props(show=L("true"), position=txt("Top"), labelColor=cor(BRANCO), fontSize=num(15),
                            showTitle=L("false")),
            "dataPoint": [serie("Vitória do mandante", VIOLETA), serie("Empate", "#3A3F86"),
                          serie("Vitória do visitante", LAVANDA)],
            "labels": props(show=L("true"), color=cor(BRANCO), fontSize=num(22), labelPrecision=L("0L")),
        }}, cabecalho("Quem vence os jogos", "Resultado do ponto de vista do mandante"))
    return pg


def tema() -> dict:
    return {
        "name": "Brasileirao",
        "dataColors": [VIOLETA, LIMAO, LAVANDA, "#3A3F86", ALTA, QUEDA],
        "foreground": BRANCO, "foregroundNeutralSecondary": LAVANDA, "background": NAVY,
        "tableAccent": LIMAO, "good": ALTA, "bad": QUEDA, "neutral": LAVANDA,
        "textClasses": {
            "callout": {"fontSize": 44, "fontFace": "Segoe UI Black", "color": BRANCO},
            "title": {"fontSize": 22, "fontFace": "Segoe UI Bold", "color": BRANCO},
            "header": {"fontSize": 16, "fontFace": "Segoe UI Semibold", "color": BRANCO},
            "label": {"fontSize": 15, "fontFace": "Segoe UI", "color": TEXTO},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": {"solid": {"color": PAINEL}}, "transparency": 6}],
                "border": [{"show": True, "color": {"solid": {"color": BORDA}}, "radius": 16, "width": 1}],
                "dropShadow": [{"show": True, "color": {"solid": {"color": "#000000"}}, "position": "Outer",
                                "preset": "Custom", "angle": 90, "shadowDistance": 4, "shadowBlur": 18,
                                "shadowSpread": 0, "transparency": 45}],
                "padding": [{"left": 18, "top": 14, "right": 18, "bottom": 14}],
                "visualTooltip": [{"background": {"solid": {"color": PAINEL2}},
                                   "titleFontColor": {"solid": {"color": LIMAO}},
                                   "valueFontColor": {"solid": {"color": BRANCO}}}],
            }},
        },
    }


def gerar_relatorio() -> None:
    if RELATORIO.exists():
        shutil.rmtree(RELATORIO / "definition", ignore_errors=True)
        shutil.rmtree(RELATORIO / "StaticResources", ignore_errors=True)
    d = RELATORIO / "definition"
    rr = RELATORIO / "StaticResources" / "RegisteredResources"
    br = RELATORIO / "StaticResources" / "SharedResources" / "BaseThemes"
    for p in (d / "pages", rr, br):
        p.mkdir(parents=True, exist_ok=True)

    shutil.copy(PASTA / "recursos" / "Fluent2-CY26SU09.json", br / "Fluent2-CY26SU09.json")
    (rr / "tema-brasileirao.json").write_text(json.dumps(tema(), ensure_ascii=False, indent=2), encoding="utf-8")
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
            "customTheme": {"name": "tema-brasileirao.json", "reportVersionAtImport": versao,
                            "type": "RegisteredResources"}},
        "objects": {"outspacePane": [{"properties": {"expanded": L("false")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "Fluent2-CY26SU09", "path": "BaseThemes/Fluent2-CY26SU09.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "tema-brasileirao.json", "path": "tema-brasileirao.json", "type": "CustomTheme"}]
             + [{"name": n, "path": n, "type": "Image"} for n in imagens]},
        ],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    pg = pagina_principal()
    pd = d / "pages" / pg.nome
    (pd / "visuals").mkdir(parents=True)
    (pd / "page.json").write_text(json.dumps(pg.json_pagina(), ensure_ascii=False, indent=2), encoding="utf-8")
    for v in pg.visuais:
        (pd / "visuals" / v["name"]).mkdir()
        (pd / "visuals" / v["name"] / "visual.json").write_text(
            json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [pg.nome], "activePageName": pg.nome}, indent=2), encoding="utf-8")


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
