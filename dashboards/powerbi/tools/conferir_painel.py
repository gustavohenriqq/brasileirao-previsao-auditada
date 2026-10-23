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
  "sem", [Vantagem sem torcida], "variacao", [Mando sem torcida],
  "times_cairam", [Times que caíram], "times_comparados", [Times comparados])"""


def main() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
        f.write(DAX)
    saida = subprocess.run(["powershell", "-NoProfile", "-File", str(Path(__file__).parent / "consultar.ps1"),
                            "-DaxArquivo", f.name], capture_output=True, text=True, check=True).stdout
    pbi = {k.strip("[]"): v for k, v in json.loads(saida)[0].items()}
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
    falhas = 0
    for k, e in esperado.items():
        ok = abs(float(pbi[k]) - e) < 1e-9
        falhas += not ok
        print(f"{'OK     ' if ok else 'FALHOU '} {k:<18} painel={float(pbi[k]):.6f}  esperado={e:.6f}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
