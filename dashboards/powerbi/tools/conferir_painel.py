"""Confere as medidas do painel (motor do Power BI Desktop aberto) contra
analise/resultados_fase1.json e contra o SQL. Sai com código 1 se algo falhar.

Uso: python dashboards/powerbi/tools/conferir_painel.py  (com o Brasileirao.pbip aberto e atualizado)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
from ingestao.comum import conectar  # noqa: E402

DAX = """EVALUATE ROW(
  "jogos", [Jogos], "gols_por_jogo", [Gols por jogo], "vitorias_mandante", [Vitórias do mandante],
  "ppj_casa", [Pontos por jogo em casa], "ppj_fora", [Pontos por jogo fora],
  "vantagem", [Vantagem do mandante], "antes", [Vantagem com torcida 2015-2019],
  "sem", [Vantagem sem torcida], "variacao", [Variação da vantagem sem torcida],
  "times_cairam", [Times que caíram], "times_comparados", [Times comparados],
  "cairam_na_tabela", [Times que caíram na tabela], "times_na_tabela", [Times na tabela])"""

# Tradicionais da Série B: só eles têm variação na tabela sem ter na Série A
DAX_B = """EVALUATE FILTER(
  ADDCOLUMNS(VALUES(times[time_id]), "variacao", [Variação na tabela]),
  NOT ISBLANK([Variação na tabela]) && ISBLANK([Variação sem torcida]))"""


def consultar(dax: str) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
        f.write(dax)
    saida = subprocess.run(["powershell", "-NoProfile", "-File", str(Path(__file__).parent / "consultar.ps1"),
                            "-DaxArquivo", f.name], capture_output=True, text=True, check=True).stdout
    return [{k.split("[")[-1].strip("]"): v for k, v in linha.items()} for linha in json.loads(saida)]


def main() -> None:
    pbi = consultar(DAX)[0]
    pbi.update({f"B {linha['time_id']}": linha["variacao"] for linha in consultar(DAX_B)})
    r = json.loads((RAIZ / "analise" / "resultados_fase1.json").read_text(encoding="utf-8"))
    with conectar() as con, con.cursor() as cur:
        cur.execute("""select count(*), avg(gols_mandante + gols_visitante), avg((resultado = 'M')::int),
                              avg(pontos_mandante), avg(pontos_visitante) from marts.mando_jogos""")
        jogos, gpj, vm, pc, pf = (float(x) for x in cur.fetchone())
    esperado = {
        "jogos": jogos, "gols_por_jogo": gpj, "vitorias_mandante": vm, "ppj_casa": pc, "ppj_fora": pf,
        "vantagem": pc - pf,
        "antes": r["periodos"]["com_torcida_2015_2019"]["vantagem_pontos"],
        "sem": r["periodos"]["sem_torcida"]["vantagem_pontos"],
        "variacao": -r["diferencas_vantagem_pontos"]["sem_torcida_menos_2015_2019"]["queda_relativa"],
        "times_cairam": r["mesmo_time"]["times_com_queda"], "times_comparados": r["mesmo_time"]["times"],
    }
    b = r["tradicionais_serie_b"]
    esperado["cairam_na_tabela"] = esperado["times_cairam"] + sum(c["variacao"] < 0 for c in b.values())
    esperado["times_na_tabela"] = esperado["times_comparados"] + len(b)
    esperado.update({f"B {time}": c["variacao"] for time, c in b.items()})
    falhas = 0
    for k, e in esperado.items():
        ok = k in pbi and abs(float(pbi[k]) - e) < 1e-9
        falhas += not ok
        print(f"{'OK     ' if ok else 'FALHOU '} {k:<18} painel={float(pbi.get(k, 'nan')):.6f}  esperado={e:.6f}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
