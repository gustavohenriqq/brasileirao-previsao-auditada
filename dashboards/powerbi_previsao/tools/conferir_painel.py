"""Confere as medidas do painel de previsão (motor do Power BI Desktop aberto)
contra analise/resultados_fase2.json e cruza as tabelas do próprio modelo.
Sai com código 1 se algo falhar.

Três grupos:
1. Totais e cartões contra o JSON (simulação e teste de 2026).
2. Cada time contra o JSON: pontos, faixa, posição esperada, posição na tabela
   final prevista e as cinco chances.
3. Coerência interna: as chances de cada zona (tabela times) saem da
   distribuição de posições (tabela posicoes); cada time e cada posição somam
   1; cada jogo soma 1; o filtro de time acha os jogos que faltam ao time; as
   quatro partes da barra de pontos somam o fim da faixa.

Usa dashboards/powerbi/tools/consultar.ps1 (painel da Fase 1), que acha a
instância do Desktop em que a consulta roda.

Uso: python dashboards/powerbi_previsao/tools/conferir_painel.py  (com o Previsao2026.pbip aberto e atualizado)
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
CONSULTAR = RAIZ / "dashboards" / "powerbi" / "tools" / "consultar.ps1"
ZONAS = {"titulo": "Chance de título", "g4": "Chance de G4", "g6": "Chance de G6",
         "sul_americana": "Chance de Sul-Americana", "z4": "Chance de Z4"}

DAX_TOTAIS = """EVALUATE ROW(
  "disputados", [Jogos disputados], "restantes", [Jogos restantes], "simulacoes", [Simulações],
  "favorito", [Favorito ao título], "chance_favorito", [Chance do favorito], "risco_queda", [Times em risco de queda],
  "jogos_linhas", COUNTROWS ( jogos ), "jogos_na_lista", [Jogos na lista], "times", COUNTROWS ( times ),
  "posicoes", COUNTROWS ( posicoes ), "jogos_teste", SUM ( info[jogos_teste] ),
  {somas})"""

DAX_TIMES = """EVALUATE ADDCOLUMNS ( VALUES ( times[time_id] ),
  "pontos", [Pontos], "esperados", [Pontos esperados], "p5", [Pontos p5], "p95", [Pontos p95],
  "posicao_esperada", [Posição esperada], "texto_titulo", [Texto Título], "texto_z4", [Texto Z4],
  "jogos_na_lista", [Jogos na lista], "posicao_prevista", [Posição prevista], "texto_hoje", [Texto hoje],
  "barra", [Barra pontos atuais] + [Barra vão] + [Barra até o esperado] + [Barra acima do esperado],
  "soma_posicoes", CALCULATE ( SUM ( posicoes[probabilidade] ) ),
  "media_posicao", SUMX ( RELATEDTABLE ( posicoes ), posicoes[posicao] * posicoes[probabilidade] ),
  {chances})"""

DAX_POSICOES = "EVALUATE ADDCOLUMNS ( VALUES ( posicoes[posicao] ), \"soma\", [Chance na posição] )"
DAX_JOGOS = ("EVALUATE ADDCOLUMNS ( VALUES ( jogos[id_jogo] ), "
             "\"soma\", [Mandante vence] + [Empate] + [Visitante vence] )")
DAX_MODELOS = "EVALUATE ADDCOLUMNS ( VALUES ( modelos[modelo] ), \"rps\", [RPS], \"erro_pontos\", [Erro de pontos] )"


def consultar(dax: str) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
        f.write(dax)
    saida = subprocess.run(["powershell", "-NoProfile", "-File", str(CONSULTAR), "-DaxArquivo", f.name],
                           capture_output=True, text=True, check=True, encoding="utf-8").stdout
    return [{k.split("[")[-1].strip("]"): v for k, v in linha.items()} for linha in json.loads(saida)]


def texto_hoje(atual: int, prevista: int) -> str:
    """Mesma regra da medida Texto hoje."""
    v = atual - prevista
    return f"{atual}º" + (f"  ▲{v}" if v > 0 else f"  ▼{-v}" if v < 0 else "")


def texto_pct(p: float) -> str | None:
    """Mesma regra da medida (dax_texto_pct em gerar_pbip.py)."""
    if p == 0:
        return None
    if p == 1:
        return "100%"
    if p >= 0.9995:
        return ">99,9%"
    if p < 0.0005:
        return "<0,1%"
    return f"{p * 100:.1f}%".replace(".", ",")


class Conferencia:
    def __init__(self) -> None:
        self.falhas = self.total = 0

    def igual(self, nome: str, painel, esperado, tol: float = 1e-9) -> None:
        if isinstance(esperado, (int, float)) and not isinstance(esperado, bool):
            ok = painel is not None and abs(float(painel) - esperado) <= tol
        else:
            ok = painel == esperado
        self.total += 1
        self.falhas += not ok
        if not ok or nome.startswith("*"):
            print(f"{'OK     ' if ok else 'FALHOU '} {nome.lstrip('*'):<44} painel={painel!r}  esperado={esperado!r}")


def main() -> None:
    r = json.loads((RAIZ / "analise" / "resultados_fase2.json").read_text(encoding="utf-8"))
    sim, teste = r["simulacao_2026"], r["teste_2026"]
    c = Conferencia()

    # 1. Totais e cartões
    somas = ", ".join(f'"soma_{z}", [{m}]' for z, m in ZONAS.items())
    t = consultar(DAX_TOTAIS.format(somas=somas))[0]
    times_json = sim["times"]
    favorito = max(times_json, key=lambda x: x["p_titulo"])
    c.igual("*jogos disputados", t["disputados"], sim["jogos_disputados"])
    c.igual("*jogos restantes", t["restantes"], sim["jogos_pendentes"])
    c.igual("*linhas de jogos", t["jogos_linhas"], sim["jogos_pendentes"])
    c.igual("*jogos na lista (sem filtro)", t["jogos_na_lista"], sim["jogos_pendentes"])
    c.igual("*simulações", t["simulacoes"], sim["simulacoes"])
    c.igual("*favorito ao título", t["favorito"], favorito["time"])
    c.igual("*chance do favorito", t["chance_favorito"], favorito["p_titulo"])
    c.igual("*times com 1% ou mais de cair", t["risco_queda"], sum(x["p_z4"] >= 0.01 for x in times_json))
    c.igual("*times", t["times"], len(times_json))
    c.igual("*linhas de posições", t["posicoes"], len(times_json) ** 2)
    c.igual("*jogos do teste", t["jogos_teste"], teste["jogos"])
    for z in ZONAS:
        de, ate = sim["zonas"][z]
        c.igual(f"*soma das chances de {z} (vagas)", t[f"soma_{z}"], ate - de + 1, tol=1e-3)

    # 2 e 3. Cada time
    chances = ", ".join(f'"{z}", [{m}], "posicoes_{z}", CALCULATE ( SUM ( posicoes[probabilidade] ), '
                        f'posicoes[posicao] >= {sim["zonas"][z][0]}, posicoes[posicao] <= {sim["zonas"][z][1]} )'
                        for z, m in ZONAS.items())
    painel = {x["time_id"]: x for x in consultar(DAX_TIMES.format(chances=chances))}
    with (RAIZ / "analise" / "simulacao_2026_jogos.csv").open(encoding="utf-8") as f:
        jogos_csv = list(csv.DictReader(f))
    # Tabela final prevista: pontos esperados, desempate na posição esperada
    previsto = sorted(times_json, key=lambda x: (-x["pontos_esperados"], x["posicao_esperada"]))
    posicao_prevista = {x["time_id"]: i for i, x in enumerate(previsto, start=1)}
    for e in times_json:
        p, tid = painel.get(e["time_id"], {}), e["time_id"]
        c.igual(f"{tid} pontos", p.get("pontos"), e["pontos_atuais"])
        c.igual(f"{tid} pontos esperados", p.get("esperados"), e["pontos_esperados"])
        c.igual(f"{tid} p5", p.get("p5"), e["pontos_p5"])
        c.igual(f"{tid} p95", p.get("p95"), e["pontos_p95"])
        c.igual(f"{tid} barra soma o fim da faixa", p.get("barra"), e["pontos_p95"], tol=1e-6)
        c.igual(f"{tid} posição esperada", p.get("posicao_esperada"), e["posicao_esperada"])
        c.igual(f"{tid} posição esperada pela tabela de posições", p.get("media_posicao"), e["posicao_esperada"],
                tol=1e-3)
        c.igual(f"{tid} soma das posições", p.get("soma_posicoes"), 1.0, tol=1e-4)
        c.igual(f"{tid} texto do título", p.get("texto_titulo"), texto_pct(e["p_titulo"]))
        c.igual(f"{tid} posição prevista", p.get("posicao_prevista"), posicao_prevista[tid])
        c.igual(f"{tid} texto hoje", p.get("texto_hoje"), texto_hoje(e["posicao_atual"], posicao_prevista[tid]))
        c.igual(f"{tid} texto do Z4", p.get("texto_z4"), texto_pct(e["p_z4"]))
        n_jogos = sum(tid in (j["mandante_id"], j["visitante_id"]) for j in jogos_csv)
        c.igual(f"{tid} jogos que faltam no filtro", p.get("jogos_na_lista"), e["jogos_restantes"])
        c.igual(f"{tid} jogos que faltam no CSV da simulação", n_jogos, e["jogos_restantes"])
        for z in ZONAS:
            c.igual(f"{tid} chance de {z}", p.get(z), e[f"p_{z}"])
            c.igual(f"{tid} chance de {z} pela tabela de posições", p.get(f"posicoes_{z}"), e[f"p_{z}"], tol=1e-4)

    for linha in consultar(DAX_POSICOES):
        c.igual(f"posição {linha['posicao']} soma 1", linha["soma"], 1.0, tol=1e-4)
    for linha in consultar(DAX_JOGOS):
        c.igual(f"jogo {linha['id_jogo']} soma 1", linha["soma"], 1.0, tol=1e-9)

    # Teste de 2026
    replay = teste["replay"]["linhas"]
    for linha in consultar(DAX_MODELOS):
        m = linha["modelo"]
        c.igual(f"*RPS {m}", linha["rps"], teste["resumo"][m]["rps"])
        if m in replay:
            media = sum(x["erro_pontos"] for x in replay[m]) / len(replay[m])
            c.igual(f"*erro de pontos {m}", linha["erro_pontos"], media)
        else:
            c.igual(f"*erro de pontos {m} (sem replay)", linha["erro_pontos"], None)

    print(f"\n{c.total - c.falhas} de {c.total} conferências passaram"
          + ("" if not c.falhas else f"; {c.falhas} falharam"))
    sys.exit(1 if c.falhas else 0)


if __name__ == "__main__":
    main()
